import asyncio

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import run_pipeline
from app.agents.schemas import AgentRequest
from app.core.security import rate_limit
from app.db.session import get_session
from app.services.report_pdf import build_report_pdf

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/executive", dependencies=[Depends(rate_limit("report", 5))])
async def executive_report(city: str | None = None, station_id: str | None = None,
                           session: AsyncSession = Depends(get_session)) -> Response:
    """Runs the agent pipeline and returns the Executive Health & Policy Report as a PDF."""
    if not (city or station_id):
        raise HTTPException(422, "provide city or station_id")
    result = await run_pipeline(session, AgentRequest(city=city, station_id=station_id))
    pdf = await asyncio.to_thread(build_report_pdf, result)
    name = f"ecopulse-report-{(station_id or city or 'scope').lower().replace(' ', '-')}.pdf"
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}"'})
