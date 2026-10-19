from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.schemas import ForecastSummary
from app.agents.tools import ToolBox
from app.db.session import get_session
from app.models import SensorReading
from app.services.aqi import aqi_category

router = APIRouter(tags=["stats"])
Field = Literal["aqi", "pm25", "pm10", "no2", "co", "temperature", "humidity"]


@router.get("/stats/summary")
async def summary(city: str | None = None, session: AsyncSession = Depends(get_session)) -> dict:
    tb = ToolBox(session)
    readings = [r for r in await tb.latest_readings(city=city) if r.quality_flag < 2]
    if not readings:
        raise HTTPException(404, "no readings found")
    aqis = [r.aqi for r in readings if r.aqi is not None]
    worst = max(readings, key=lambda r: r.aqi or 0)
    mean_aqi = round(sum(aqis) / len(aqis), 1) if aqis else None
    return {
        "city": city, "stations": len(readings), "mean_aqi": mean_aqi,
        "category": aqi_category(mean_aqi) if mean_aqi is not None else None,
        "worst_station": {"station_id": worst.station_id, "aqi": worst.aqi, "city": worst.city},
        "latest": [r.model_dump(mode="json") for r in readings],
        "as_of": max(r.time for r in readings).isoformat(),
    }


@router.get("/stats/timeseries")
async def timeseries(station_id: str, field: Field = "pm25", hours: int = Query(48, ge=1, le=720),
                     session: AsyncSession = Depends(get_session)) -> dict:
    col = getattr(SensorReading, field)
    bucket = func.time_bucket(literal_column("interval '1 hour'"), SensorReading.time).label("bucket")
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    stmt = (select(bucket, func.avg(col)).where(SensorReading.station_id == station_id,
                                                SensorReading.time >= since, SensorReading.quality_flag < 2)
            .group_by(bucket).order_by(bucket))
    rows = (await session.execute(stmt)).all()
    return {"station_id": station_id, "field": field,
            "points": [{"time": b.isoformat(), "value": round(float(v), 2)} for b, v in rows if v is not None]}


@router.get("/forecasts", response_model=ForecastSummary)
async def forecasts(station_id: str, pollutant: Literal["pm25", "pm10", "no2", "co", "aqi", "temperature"] = "pm25",
                    session: AsyncSession = Depends(get_session)) -> ForecastSummary:
    fc = await ToolBox(session).forecast(station_id, pollutant)
    if fc is None:
        raise HTTPException(404, "not enough history to forecast yet (need >= 12 hourly points)")
    return fc
