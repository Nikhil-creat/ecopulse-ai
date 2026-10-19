import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import rate_limit
from app.db.session import get_session
from app.models import SatelliteAnalysis
from app.schemas.sensor import SatelliteOut
from app.workers.tasks import run_cnn_analysis

router = APIRouter(prefix="/satellite", tags=["satellite"])
ALLOWED = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
MAX_BYTES = 50 * 1024 * 1024


@router.post("/analyze", status_code=202, dependencies=[Depends(rate_limit("sat", 5))])
async def analyze(
    file: UploadFile = File(...),
    region: str = Form(...),
    image_type: Literal["satellite", "aerial", "thermal"] = Form("satellite"),
) -> dict[str, str]:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(415, f"unsupported image type; use one of {sorted(ALLOWED)}")
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "image too large (max 50 MB)")
    dest = Path(get_settings().artifacts_dir) / "images"
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"{uuid.uuid4().hex}{ext}"
    path.write_bytes(data)
    task = run_cnn_analysis.delay(str(path), region, image_type)
    return {"task_id": task.id, "image": path.name}


@router.get("/latest", response_model=list[SatelliteOut])
async def latest(region: str | None = None, limit: int = 10,
                 session: AsyncSession = Depends(get_session)) -> list[SatelliteOut]:
    stmt = select(SatelliteAnalysis).order_by(SatelliteAnalysis.captured_at.desc()).limit(min(limit, 100))
    if region:
        stmt = stmt.where(SatelliteAnalysis.region == region)
    rows = (await session.execute(stmt)).scalars()
    return [SatelliteOut(id=str(r.id), captured_at=r.captured_at, region=r.region, image_type=r.image_type,
                         smog_severity_index=r.smog_severity_index, green_canopy_density=r.green_canopy_density,
                         heat_island_intensity=r.heat_island_intensity, model_version=r.model_version,
                         heatmap=r.heatmap) for r in rows]
