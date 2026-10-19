from fastapi import APIRouter, Depends
from redis.asyncio import from_url as redis_from_url
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_session

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    checks: dict[str, str] = {}

    try:
        await session.execute(text("SELECT 1"))
        ext = await session.execute(
            text("SELECT extname FROM pg_extension WHERE extname IN ('timescaledb','vector')")
        )
        checks["postgres"] = "ok"
        checks["extensions"] = ",".join(sorted(r[0] for r in ext))
    except Exception as exc:  # noqa: BLE001
        checks["postgres"] = f"error: {exc.__class__.__name__}"

    try:
        r = redis_from_url(get_settings().redis_url)
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {exc.__class__.__name__}"

    ok = checks.get("postgres") == "ok" and checks.get("redis") == "ok"
    return {"status": "ok" if ok else "degraded", "checks": checks}
