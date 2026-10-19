import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import current_user
from app.db.session import get_session
from app.models import UserAlert

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertIn(BaseModel):
    city: str = Field(min_length=1, max_length=80)
    pollutant: Literal["aqi", "pm25", "pm10", "no2"]
    threshold: float = Field(gt=0, le=5000)
    severity: Literal["info", "warning", "critical"] = "warning"


class AlertOut(AlertIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    message: str | None
    triggered_at: datetime | None


async def _mine(session: AsyncSession, alert_id: uuid.UUID, user: dict[str, Any]) -> UserAlert:
    a = (await session.execute(select(UserAlert).where(UserAlert.id == alert_id,
                                                       UserAlert.user_ref == user["sub"]))).scalars().first()
    if not a:
        raise HTTPException(404, "alert not found")
    return a


@router.get("", response_model=list[AlertOut])
async def list_alerts(user: dict[str, Any] = Depends(current_user), session: AsyncSession = Depends(get_session)):
    rows = await session.execute(select(UserAlert).where(UserAlert.user_ref == user["sub"]).order_by(UserAlert.created_at.desc()))
    return rows.scalars().all()


@router.post("", response_model=AlertOut, status_code=201)
async def create_alert(body: AlertIn, user: dict[str, Any] = Depends(current_user),
                       session: AsyncSession = Depends(get_session)) -> UserAlert:
    count = len((await session.execute(select(UserAlert.id).where(UserAlert.user_ref == user["sub"]))).all())
    if count >= 25:
        raise HTTPException(429, "alert limit reached (25)")
    a = UserAlert(user_ref=user["sub"], **body.model_dump())
    session.add(a)
    await session.commit()
    await session.refresh(a)
    return a


@router.post("/{alert_id}/rearm", response_model=AlertOut)
async def rearm(alert_id: uuid.UUID, user: dict[str, Any] = Depends(current_user),
                session: AsyncSession = Depends(get_session)) -> UserAlert:
    a = await _mine(session, alert_id, user)
    a.status, a.triggered_at, a.message = "active", None, None
    await session.commit()
    return a


@router.delete("/{alert_id}", status_code=204)
async def delete_alert(alert_id: uuid.UUID, user: dict[str, Any] = Depends(current_user),
                       session: AsyncSession = Depends(get_session)) -> None:
    await _mine(session, alert_id, user)
    await session.execute(delete(UserAlert).where(UserAlert.id == alert_id))
    await session.commit()
