import asyncio
from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

T = TypeVar("T")


@asynccontextmanager
async def worker_session() -> AsyncIterator[AsyncSession]:
    """Fresh engine per Celery task run (each task uses its own event loop)."""
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            yield session
    finally:
        await engine.dispose()


def run_async(coro: Awaitable[T]) -> T:
    return asyncio.run(coro)  # type: ignore[arg-type]
