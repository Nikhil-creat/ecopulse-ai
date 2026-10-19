import hmac
import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import Header, HTTPException, Request
from redis.asyncio import Redis, from_url

from app.core.config import get_settings

log = logging.getLogger(__name__)
_redis: Redis | None = None


async def require_api_key(request: Request, x_api_key: str | None = Header(None)) -> None:
    """Protects write/admin endpoints: valid API key (machines) OR logged-in analyst/admin (people).
    Open only when no API keys are configured and AUTH_REQUIRED is false (development)."""
    from app.core.auth import ROLES, claims_from_request

    cfg = get_settings()
    if not cfg.api_key_list and not cfg.auth_required:
        return
    if x_api_key and any(hmac.compare_digest(x_api_key, k) for k in cfg.api_key_list):
        return
    claims = claims_from_request(request)
    if claims and ROLES.get(claims.get("role", ""), -1) >= ROLES["analyst"]:
        return
    raise HTTPException(401, "authentication required (X-API-Key or analyst/admin login)")


def rate_limit(name: str, limit: int, window: int = 60) -> Callable[[Request], Awaitable[None]]:
    """Fixed-window per-IP limiter backed by Redis. Fails open if Redis is unavailable."""

    async def dep(request: Request) -> None:
        global _redis
        ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "?")
        key = f"rl:{name}:{ip}:{int(time.time() // window)}"
        try:
            _redis = _redis or from_url(get_settings().redis_url)
            n = await _redis.incr(key)
            if n == 1:
                await _redis.expire(key, window * 2)
        except Exception as exc:  # noqa: BLE001
            log.warning("rate limiter unavailable: %r", exc)
            return
        if n > limit:
            raise HTTPException(429, "rate limit exceeded", headers={"Retry-After": str(window)})

    return dep
