from fastapi import APIRouter, Depends

from app.api.v1 import agents, alerts, auth, chat, intel, health, ingest, knowledge, mlops, readings, reports, satellite, stats
from app.core.security import require_api_key

api_router = APIRouter(prefix="/api/v1")
for r in (health.router, readings.router, satellite.router, mlops.router, agents.router, stats.router,
          reports.router, chat.router, auth.router, alerts.router, intel.router):
    api_router.include_router(r)
for r in (ingest.router, knowledge.router):  # write/admin surfaces
    api_router.include_router(r, dependencies=[Depends(require_api_key)])
