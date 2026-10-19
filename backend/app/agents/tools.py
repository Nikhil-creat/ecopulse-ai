"""Strict, typed tool interface the agents use to reach TimescaleDB metrics and vectorised guidelines.
Agents never touch SQL directly."""
from datetime import datetime, timedelta, timezone
from typing import Literal

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.schemas import ForecastPoint, ForecastSummary
from app.core.config import get_settings
from app.models import Forecast, SatelliteAnalysis, SensorReading
from app.schemas.sensor import ReadingOut
from app.services.rag.store import Hit, hybrid_search

Pollutant = Literal["pm25", "pm10", "no2", "co", "aqi", "temperature"]
HORIZONS = (6, 12, 24, 48, 72)


def hourly_means(readings: list[ReadingOut], field: str) -> list[float]:
    buckets: dict[datetime, list[float]] = {}
    for r in readings:
        v = getattr(r, field)
        if v is not None:
            buckets.setdefault(r.time.replace(minute=0, second=0, microsecond=0), []).append(v)
    return [float(np.mean(buckets[h])) for h in sorted(buckets)]


def baseline_forecast(station_id: str, pollutant: str, values: list[float]) -> ForecastSummary | None:
    """Damped-trend baseline (EWMA level + damped linear slope). NOT a trained forecaster; it exists so the
    agents have a labelled fallback until Prophet/LSTM models are trained."""
    if len(values) < 12:
        return None
    y = np.asarray(values[-24:], dtype=float)
    slope = float(np.polyfit(np.arange(len(y)), y, 1)[0])
    level = y[0]
    for v in y[1:]:
        level = 0.3 * v + 0.7 * level
    resid = float(np.std(y - np.convolve(y, np.ones(3) / 3, mode="same"))) or 1.0
    phi = 0.97
    pts = []
    for h in HORIZONS:
        pred = max(0.0, level + slope * phi * (1 - phi**h) / (1 - phi))
        band = 1.28 * resid * (1 + h / 24)
        pts.append(ForecastPoint(horizon_hours=h, predicted=round(pred, 2),
                                 lower=round(max(0.0, pred - band), 2), upper=round(pred + band, 2)))
    return ForecastSummary(station_id=station_id, pollutant=pollutant, model="baseline-damped-trend",
                           points=pts, peak_value=max(p.predicted for p in pts))


class ToolBox:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def latest_readings(self, city: str | None = None, station_id: str | None = None) -> list[ReadingOut]:
        stmt = select(SensorReading).distinct(SensorReading.station_id).order_by(
            SensorReading.station_id, SensorReading.time.desc())
        if station_id:
            stmt = stmt.where(SensorReading.station_id == station_id)
        if city:
            stmt = stmt.where(SensorReading.city.ilike(city))
        return [ReadingOut.model_validate(r) for r in (await self.session.execute(stmt)).scalars()]

    async def recent_series(self, station_id: str, hours: int = 24) -> list[ReadingOut]:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        stmt = select(SensorReading).where(SensorReading.station_id == station_id,
                                           SensorReading.time >= since).order_by(SensorReading.time)
        return [ReadingOut.model_validate(r) for r in (await self.session.execute(stmt)).scalars()]

    async def forecast(self, station_id: str, pollutant: Pollutant = "pm25") -> ForecastSummary | None:
        now = datetime.now(timezone.utc)
        stmt = (select(Forecast).where(Forecast.station_id == station_id, Forecast.pollutant == pollutant,
                                       Forecast.target_time > now)
                .order_by(Forecast.issued_at.desc(), Forecast.horizon_hours))
        rows = list((await self.session.execute(stmt)).scalars())
        if rows:
            latest = [r for r in rows if r.issued_at == rows[0].issued_at and r.horizon_hours in HORIZONS]
            if latest:
                pts = [ForecastPoint(horizon_hours=r.horizon_hours, predicted=r.predicted,
                                     lower=r.lower_bound if r.lower_bound is not None else r.predicted,
                                     upper=r.upper_bound if r.upper_bound is not None else r.predicted)
                       for r in latest]
                return ForecastSummary(station_id=station_id, pollutant=pollutant, model=latest[0].model_name,
                                       points=pts, peak_value=max(p.predicted for p in pts))
        series = await self.recent_series(station_id, hours=48)
        return baseline_forecast(station_id, pollutant, hourly_means(series, pollutant))

    async def satellite_context(self, region: str) -> SatelliteAnalysis | None:
        stmt = (select(SatelliteAnalysis).where(SatelliteAnalysis.region.ilike(region))
                .order_by(SatelliteAnalysis.captured_at.desc()).limit(1))
        return (await self.session.execute(stmt)).scalars().first()

    async def guidelines(self, query: str, doc_type: str | None = None, k: int | None = None) -> list[Hit]:
        return await hybrid_search(self.session, query, k or get_settings().rag_top_k, doc_type)
