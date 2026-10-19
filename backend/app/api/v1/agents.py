from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import run_pipeline
from app.agents.schemas import AgentRequest, AgentRunResult
from app.core.security import rate_limit
from app.db.session import get_session

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/run", response_model=AgentRunResult, dependencies=[Depends(rate_limit("agents", 10))])
async def run_agents(req: AgentRequest, session: AsyncSession = Depends(get_session)) -> AgentRunResult:
    """Data Integrity -> Forecast & Health Risk -> Policy & Mitigation (LangGraph)."""
    return await run_pipeline(session, req)
