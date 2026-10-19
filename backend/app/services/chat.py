"""Context-aware chat: hybrid RAG (guidelines) + live sensors + forecast + satellite, with Redis memory."""
import asyncio
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from redis.asyncio import from_url
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm import SYSTEM_GUARD, get_llm
from app.agents.nodes import _advice
from app.agents.thresholds import CATEGORY_TO_LEVEL
from app.agents.tools import ToolBox
from app.core.config import get_settings
from app.models import SensorReading
from app.services.aqi import aqi_category

log = logging.getLogger(__name__)
HISTORY_TURNS = 8
HISTORY_TTL = 24 * 3600

CHAT_RULES = (
    "Answer the user's air-quality and health question using ONLY the facts in the <data> block. "
    "Cite guideline sources inline as [S1], [S2]. If live data for the user's location is missing, say so plainly "
    "instead of guessing. The forecast has coarse horizons (+6/12/24/48/72 h); do not invent hour-by-hour values - "
    "give practical timing guidance and say what the data does and does not show. You are not a doctor: for "
    "personal medical decisions advise consulting a clinician, and for severe breathlessness or chest pain advise "
    "urgent care. Keep answers under 180 words."
)

QUICK_ACTIONS = [
    {"label": "Is it safe to exercise outside?", "prompt": "Is it safe to exercise outdoors right now? I have asthma."},
    {"label": "Best time to go out today", "prompt": "What is the best time of day to be outdoors based on the forecast?"},
    {"label": "Mask advice", "prompt": "Do I need a mask today, and which type works for PM2.5?"},
    {"label": "Explain the AQI", "prompt": "What does the current AQI mean and how does it compare with WHO guidelines?"},
    {"label": "What is the city doing?", "prompt": "What measures are recommended to reduce pollution right now?"},
]


@dataclass
class ChatContext:
    city: str | None
    text: str
    sources: list[dict] = field(default_factory=list)
    level: str = "low"
    has_live: bool = False


async def resolve_city(session: AsyncSession, message: str, city: str | None) -> str | None:
    if city:
        return city
    known = {s.city for s in get_settings().stations}
    known |= set((await session.execute(select(SensorReading.city).distinct().limit(200))).scalars().all())
    low = message.lower()
    return next((c for c in known if c and c.lower() in low), None)


async def build_context(session: AsyncSession, message: str, city: str | None) -> ChatContext:
    tb = ToolBox(session)
    city = await resolve_city(session, message, city)
    parts: list[str] = []
    level, has_live = "low", False

    readings = [r for r in await tb.latest_readings(city=city) if r.quality_flag < 2] if city else []
    if readings:
        has_live = True
        worst = max(readings, key=lambda r: r.aqi or 0)
        aqi = worst.aqi
        cat = aqi_category(aqi) if aqi is not None else None
        level = CATEGORY_TO_LEVEL.get(cat or "", "low")
        parts.append(f"LIVE ({city}, as of {worst.time.isoformat()}): worst station {worst.station_id}: AQI {aqi} ({cat}), "
                     f"PM2.5 {worst.pm25}, PM10 {worst.pm10}, NO2 {worst.no2}, temp {worst.temperature} C "
                     f"[{len(readings)} station(s)]")
        fc = await tb.forecast(worst.station_id, "pm25")
        if fc:
            parts.append(f"FORECAST PM2.5 ug/m3 ({fc.model}): " +
                         ", ".join(f"+{p.horizon_hours}h {p.predicted} ({p.lower}-{p.upper})" for p in fc.points))
        sat = await tb.satellite_context(city)
        if sat:
            parts.append(f"SATELLITE ({sat.captured_at.date()}): smog index {sat.smog_severity_index}, "
                         f"canopy {sat.green_canopy_density}")
    else:
        parts.append(f"LIVE: no station data available for {city or 'the requested location'}.")

    sources: list[dict] = []
    try:
        for i, h in enumerate(await tb.guidelines(message), 1):
            sources.append({"ref": f"S{i}", "source": h.source, "title": h.doc_title})
            parts.append(f"[S{i}] {h.source} - {h.doc_title}: {h.content}")
    except Exception as exc:  # noqa: BLE001
        log.warning("chat retrieval failed: %r", exc)
    return ChatContext(city, "\n".join(parts), sources, level, has_live)


async def load_history(session_id: str) -> list[tuple[str, str]]:
    try:
        r = from_url(get_settings().redis_url)
        raw = await r.lrange(f"chat:{session_id}", 0, -1)
        await r.aclose()
        return [tuple(json.loads(x)) for x in raw]  # type: ignore[misc]
    except Exception:  # noqa: BLE001
        return []


async def save_turn(session_id: str, user: str, assistant: str) -> None:
    try:
        r = from_url(get_settings().redis_url)
        key = f"chat:{session_id}"
        await r.rpush(key, json.dumps(["human", user]), json.dumps(["ai", assistant]))
        await r.ltrim(key, -2 * HISTORY_TURNS, -1)
        await r.expire(key, HISTORY_TTL)
        await r.aclose()
    except Exception as exc:  # noqa: BLE001
        log.warning("chat history save failed: %r", exc)


def _text(chunk_content: object) -> str:
    if isinstance(chunk_content, str):
        return chunk_content
    if isinstance(chunk_content, list):
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in chunk_content)
    return ""


def fallback_answer(ctx: ChatContext) -> str:
    if not ctx.has_live:
        return ("I don't have live station data for that location yet, so I can't give a current reading. "
                "General guidance: on poor-air days sensitive groups should avoid outdoor exercise.")
    adv = " ".join(_advice(ctx.level))
    return (f"Based on the latest data for {ctx.city} (risk level: {ctx.level.replace('_', ' ')}): {adv} "
            "Check the forecast before choosing a time; urban particulate levels often peak in morning and evening "
            "traffic hours. This is general guidance, not medical advice. (LLM not configured - template answer.)")


async def stream_answer(ctx: ChatContext, message: str, history: list[tuple[str, str]]) -> AsyncIterator[str]:
    llm = get_llm("groq")
    if llm is None:
        text = fallback_answer(ctx)
        for word in text.split(" "):
            yield word + " "
            await asyncio.sleep(0.02)
        return
    msgs = [("system", f"{SYSTEM_GUARD} {CHAT_RULES}"), *history,
            ("human", f"<data>\n{ctx.text}\n</data>\n\nQuestion: {message}")]
    async for chunk in llm.astream(msgs):
        t = _text(chunk.content)
        if t:
            yield t
