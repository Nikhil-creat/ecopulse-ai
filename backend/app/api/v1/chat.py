import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import rate_limit
from app.db.session import get_session
from app.services.chat import QUICK_ACTIONS, build_context, load_history, save_turn, stream_answer

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    city: str | None = None
    session_id: str | None = Field(None, max_length=64)


def sse(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/quick-actions")
async def quick_actions() -> list[dict]:
    return QUICK_ACTIONS


@router.post("", dependencies=[Depends(rate_limit("chat", 20))])
async def chat(req: ChatRequest, session: AsyncSession = Depends(get_session)) -> StreamingResponse:
    """SSE stream. Events: meta (session, city, sources) -> token* -> done | error."""
    sid = req.session_id or uuid.uuid4().hex
    # All DB work happens before streaming starts, so the DB session is not held open during generation.
    ctx = await build_context(session, req.message, req.city)
    history = await load_history(sid)

    async def events() -> AsyncIterator[str]:
        yield sse("meta", {"session_id": sid, "city": ctx.city, "live_data": ctx.has_live, "sources": ctx.sources})
        answer = ""
        try:
            async for tok in stream_answer(ctx, req.message, history):
                answer += tok
                yield sse("token", tok)
            await save_turn(sid, req.message, answer)
            yield sse("done", {"chars": len(answer)})
        except Exception as exc:  # noqa: BLE001
            yield sse("error", {"message": f"generation failed: {exc.__class__.__name__}"})

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
