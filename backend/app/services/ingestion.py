import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import AuditLog, SensorReading
from app.schemas.sensor import IngestResult, SensorReadingIn
from app.services.aqi import compute_aqi
from app.services.alerts import evaluate_alerts
from app.services.live import publish_readings
from app.services.providers import build_providers

log = logging.getLogger(__name__)

_POLLUTANTS = ("pm25", "pm10", "no2", "co")
_UPDATE_COLS = ("city", "latitude", "longitude", "aqi", "pm25", "pm10", "no2", "co",
                "temperature", "humidity", "source", "quality_flag", "raw")


def assess_quality(r: SensorReadingIn) -> int:
    """0 ok, 1 suspect, 2 failed. Deeper checks belong to the Data Integrity Agent (Phase 3)."""
    if all(getattr(r, p) is None for p in _POLLUTANTS):
        return 2
    if r.pm25 is not None and r.pm10 is not None and r.pm25 > r.pm10 * 1.05:
        return 1  # PM2.5 is a subset of PM10
    if r.time > datetime.now(timezone.utc) + timedelta(minutes=5):
        return 1  # timestamp from the future
    return 0


async def store_readings(session: AsyncSession, readings: list[SensorReadingIn]) -> IngestResult:
    rows, flags = [], []
    for r in readings:
        flag = assess_quality(r)
        flags.append(flag)
        data = r.model_dump()
        if data["aqi"] is None:
            data["aqi"] = compute_aqi(r.pm25, r.pm10)
        data["quality_flag"] = flag
        rows.append(data)

    stmt = insert(SensorReading).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["station_id", "time"], set_={c: stmt.excluded[c] for c in _UPDATE_COLS}
    )
    await session.execute(stmt)
    session.add(AuditLog(actor="ingestion", actor_type="system", action="ingest_readings",
                         entity_type="sensor_readings",
                         details={"count": len(rows), "suspect": flags.count(1), "failed": flags.count(2)}))
    await session.commit()
    try:
        await evaluate_alerts(session, rows)
    except Exception as exc:  # noqa: BLE001 - alerting must never break ingestion
        log.warning("alert evaluation failed: %r", exc)
    await publish_readings(rows)  # best-effort push to WebSocket clients
    return IngestResult(received=len(readings), stored=len(rows), suspect=flags.count(1), failed=flags.count(2))


async def fetch_live(settings: Settings) -> list[SensorReadingIn]:
    """Poll every provider for every station; one failure never blocks the rest."""
    providers = build_providers(settings)
    jobs = [(p, s) for p in providers for s in settings.stations]
    async with httpx.AsyncClient(timeout=15) as client:
        results = await asyncio.gather(*(p.fetch(client, s) for p, s in jobs), return_exceptions=True)
    out: list[SensorReadingIn] = []
    for (p, s), res in zip(jobs, results):
        if isinstance(res, BaseException):
            log.warning("provider %s failed for %s: %r", p.name, s.id, res)
        elif res is not None:
            out.append(res)
    return out
