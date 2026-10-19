import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import require_api_key

from app.core.config import get_settings
from app.workers.tasks import drift_monitor

router = APIRouter(prefix="/mlops", tags=["mlops"])


@router.get("/drift")
async def latest_drift() -> dict[str, Any]:
    path = Path(get_settings().artifacts_dir) / "drift" / "latest.json"
    if not path.is_file():
        raise HTTPException(404, "no drift report yet - POST /mlops/drift/run")
    return json.loads(path.read_text())


@router.post("/drift/run", status_code=202, dependencies=[Depends(require_api_key)])
async def run_drift() -> dict[str, str]:
    return {"task_id": drift_monitor.delay().id}
