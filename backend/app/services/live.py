"""Redis pub/sub bridge: ingestion publishes, WebSocket handlers subscribe."""
import json
import logging
from typing import Any

from redis.asyncio import from_url

from app.core.config import get_settings

log = logging.getLogger(__name__)
CHANNEL = "ecopulse:live-metrics"
FIELDS = ("station_id", "city", "latitude", "longitude", "aqi", "pm25", "pm10", "no2", "co",
          "temperature", "humidity", "source", "quality_flag")


def serialize(row: dict[str, Any]) -> dict[str, Any]:
    out = {k: row.get(k) for k in FIELDS}
    t = row["time"]
    out["time"] = t.isoformat() if hasattr(t, "isoformat") else str(t)
    return out


async def publish_readings(rows: list[dict[str, Any]]) -> None:
    try:
        r = from_url(get_settings().redis_url)
        await r.publish(CHANNEL, json.dumps({"type": "readings", "data": [serialize(x) for x in rows]}))
        await r.aclose()
    except Exception as exc:  # noqa: BLE001 - live push must never break ingestion
        log.warning("live publish failed: %r", exc)
