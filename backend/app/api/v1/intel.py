import json
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import rate_limit, require_api_key
from app.db.session import get_session
from app.ml import forecaster
from app.services import intel
from app.workers.tasks import run_backtest_task

router = APIRouter(prefix="/intel", tags=["intelligence"])


@router.get("/backtest")
async def latest_backtest() -> dict:
    p = Path(get_settings().artifacts_dir) / "backtest" / "latest.json"
    if not p.is_file():
        raise HTTPException(404, "no backtest yet (needs ~4 days of hourly history; POST /intel/backtest/run)")
    return json.loads(p.read_text())


@router.post("/backtest/run", status_code=202, dependencies=[Depends(require_api_key)])
async def run_backtest() -> dict[str, str]:
    return {"task_id": run_backtest_task.delay().id}


@router.get("/anomalies", dependencies=[Depends(rate_limit("anomaly", 20))])
async def anomalies(station_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    return {"station_id": station_id, "window_hours": 48, "anomalies": await intel.anomalies(session, station_id)}


@router.get("/explain", dependencies=[Depends(rate_limit("explain", 20))])
async def explain(station_id: str, pollutant: Literal["pm25", "pm10", "no2"] = "pm25", horizon: int = 24,
                  session: AsyncSession = Depends(get_session)) -> dict:
    import asyncio

    s = await intel.hourly(session, station_id, pollutant)
    res = await asyncio.to_thread(forecaster.explain, s, min(max(horizon, 1), 72)) if len(s) else None
    if res is None:
        raise HTTPException(404, "need at least 72 hourly points for an explanation")
    return {"station_id": station_id, "pollutant": pollutant, **res}
