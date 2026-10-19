import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UserAlert

log = logging.getLogger(__name__)


async def evaluate_alerts(session: AsyncSession, rows: list[dict[str, Any]]) -> int:
    """Marks active alerts as triggered when a freshly ingested reading crosses the user's threshold."""
    active = (await session.execute(select(UserAlert).where(UserAlert.status == "active"))).scalars().all()
    fired = 0
    for a in active:
        vals = [r[a.pollutant] for r in rows if (r.get("city") or "").lower() == a.city.lower() and r.get(a.pollutant) is not None]
        if vals and max(vals) >= a.threshold:
            a.status, a.triggered_at = "triggered", datetime.now(timezone.utc)
            a.message = f"{a.pollutant.upper()} reached {max(vals):.0f} in {a.city} (threshold {a.threshold:g})"
            fired += 1
    if fired:
        await session.commit()
    return fired
