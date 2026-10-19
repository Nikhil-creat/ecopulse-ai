import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.ws import ws_router
from app.core.config import get_settings
from app.db.session import engine

settings = get_settings()
logging.basicConfig(level=settings.log_level)


async def bootstrap_admin() -> None:
    """Create the first admin from ADMIN_EMAIL / ADMIN_PASSWORD when no users exist."""
    from sqlalchemy import select

    from app.core.auth import hash_password
    from app.db.session import SessionLocal
    from app.models import User

    if not (settings.admin_email and settings.admin_password):
        return
    try:
        async with SessionLocal() as s:
            if (await s.execute(select(User.id).limit(1))).first() is None:
                s.add(User(email=settings.admin_email.lower(), password_hash=hash_password(settings.admin_password), role="admin"))
                await s.commit()
    except Exception as exc:  # noqa: BLE001 - e.g. users table not migrated yet (run make migrate)
        logging.getLogger(__name__).warning("admin bootstrap skipped: %r", exc)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await bootstrap_admin()
    yield
    await engine.dispose()


app = FastAPI(
    title=f"{settings.app_name} - Autonomous Urban Climate Intelligence & Decision Engine",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)  # scraped internally; not routed by Nginx

app.include_router(api_router)
app.include_router(ws_router)
