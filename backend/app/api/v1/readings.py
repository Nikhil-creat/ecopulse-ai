from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models import SensorReading
from app.schemas.sensor import ReadingOut

router = APIRouter(prefix="/readings", tags=["readings"])


@router.get("/latest", response_model=list[ReadingOut])
async def latest_per_station(city: str | None = None, session: AsyncSession = Depends(get_session)) -> list[SensorReading]:
    stmt = select(SensorReading).distinct(SensorReading.station_id).order_by(
        SensorReading.station_id, SensorReading.time.desc())
    if city:
        stmt = stmt.where(SensorReading.city == city)
    return list((await session.execute(stmt)).scalars())


@router.get("/history", response_model=list[ReadingOut])
async def history(station_id: str, limit: int = Query(168, ge=1, le=5000),
                  session: AsyncSession = Depends(get_session)) -> list[SensorReading]:
    stmt = select(SensorReading).where(SensorReading.station_id == station_id).order_by(
        SensorReading.time.desc()).limit(limit)
    return list((await session.execute(stmt)).scalars())
