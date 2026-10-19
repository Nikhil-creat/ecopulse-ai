from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.rag.ingest_cli import seed
from app.services.rag.loaders import read_file_text
from app.services.rag.store import hybrid_search, ingest_document

router = APIRouter(prefix="/knowledge", tags=["rag"])


@router.post("/seed")
async def seed_knowledge() -> dict[str, int]:
    """Embed and store the bundled WHO / CPCB / advisory / playbook documents (idempotent)."""
    return await seed()


@router.post("/upload")
async def upload(file: UploadFile = File(...), source: str = Form(...), doc_type: str = Form("guideline"),
                 session: AsyncSession = Depends(get_session)) -> dict[str, int]:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".md", ".txt", ".pdf"}:
        raise HTTPException(415, "use .md, .txt or .pdf")
    with NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
        tmp.write(await file.read())
        tmp.flush()
        text = read_file_text(Path(tmp.name))
    n = await ingest_document(session, source=source, title=file.filename or source, doc_type=doc_type, text=text)
    return {"chunks": n}


@router.get("/search")
async def search(q: str, k: int = Query(4, ge=1, le=10), doc_type: str | None = None,
                 session: AsyncSession = Depends(get_session)) -> list[dict]:
    hits = await hybrid_search(session, q, k, doc_type)
    return [{"source": h.source, "title": h.doc_title, "score": h.score, "content": h.content} for h in hits]
