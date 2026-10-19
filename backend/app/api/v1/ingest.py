from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.sensor import IngestBatch, IngestResult
from app.services.ingestion import store_readings
from app.workers.tasks import fetch_sensor_data

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post("/readings", response_model=IngestResult)
async def ingest_readings(batch: IngestBatch, session: AsyncSession = Depends(get_session)) -> IngestResult:
    """Push validated sensor readings (idempotent upsert on station_id + time)."""
    return await store_readings(session, batch.readings)


@router.post("/fetch", status_code=202)
async def trigger_fetch() -> dict[str, str]:
    """Queue an immediate poll of the configured providers."""
    return {"task_id": fetch_sensor_data.delay().id}
