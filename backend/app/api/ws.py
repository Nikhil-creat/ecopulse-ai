import asyncio
import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from redis.asyncio import from_url
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import SensorReading
from app.services.live import CHANNEL, serialize

log = logging.getLogger(__name__)
ws_router = APIRouter()


async def _snapshot(city: str | None) -> list[dict]:
    stmt = select(SensorReading).distinct(SensorReading.station_id).order_by(
        SensorReading.station_id, SensorReading.time.desc())
    if city:
        stmt = stmt.where(SensorReading.city.ilike(city))
    async with SessionLocal() as s:
        rows = (await s.execute(stmt)).scalars().all()
    return [serialize({c.name: getattr(r, c.name) for c in SensorReading.__table__.columns}) for r in rows]


@ws_router.websocket("/ws/live-metrics")
async def live_metrics(ws: WebSocket, city: str | None = Query(None)) -> None:
    """Push live readings. On connect: a snapshot of the latest reading per station, then every new batch."""
    await ws.accept()
    redis = from_url(get_settings().redis_url)
    pubsub = redis.pubsub()
    try:
        await ws.send_json({"type": "snapshot", "data": await _snapshot(city)})
        await pubsub.subscribe(CHANNEL)
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=15)
            if msg is None:
                await ws.send_json({"type": "ping"})  # keep-alive; also surfaces dead connections
                continue
            payload = json.loads(msg["data"])
            if city:
                payload["data"] = [r for r in payload["data"] if (r.get("city") or "").lower() == city.lower()]
            if payload["data"]:
                await ws.send_json(payload)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception as exc:  # noqa: BLE001
        log.warning("ws error: %r", exc)
    finally:
        await pubsub.unsubscribe(CHANNEL)
        await pubsub.aclose()
        await redis.aclose()
