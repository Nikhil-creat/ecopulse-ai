import asyncio
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml import embeddings
from app.models import KnowledgeEmbedding as KE
from app.services.rag.chunking import chunk_text


@dataclass
class Hit:
    id: int
    source: str
    doc_title: str
    doc_type: str
    content: str
    score: float


async def ingest_document(session: AsyncSession, *, source: str, title: str, doc_type: str, text: str,
                          meta: dict[str, Any] | None = None) -> int:
    """Idempotent: replaces all chunks of (source, title)."""
    chunks = chunk_text(text)
    if not chunks:
        return 0
    vectors = await asyncio.to_thread(embeddings.encode, chunks)
    await session.execute(delete(KE).where(KE.source == source, KE.doc_title == title))
    session.add_all(
        KE(source=source, doc_title=title, doc_type=doc_type, chunk_index=i, content=c, meta=meta, embedding=v)
        for i, (c, v) in enumerate(zip(chunks, vectors))
    )
    await session.commit()
    return len(chunks)


async def hybrid_search(session: AsyncSession, query: str, k: int = 4, doc_type: str | None = None) -> list[Hit]:
    """Reciprocal-rank fusion of pgvector cosine search and Postgres full-text search."""
    qvec = (await asyncio.to_thread(embeddings.encode, [query]))[0]
    pool = k * 4
    tsq = func.websearch_to_tsquery("english", query)

    vec = select(KE.id).order_by(KE.embedding.cosine_distance(qvec)).limit(pool)
    fts = (select(KE.id).where(KE.content_tsv.op("@@")(tsq))
           .order_by(func.ts_rank_cd(KE.content_tsv, tsq).desc()).limit(pool))
    if doc_type:
        vec, fts = vec.where(KE.doc_type == doc_type), fts.where(KE.doc_type == doc_type)

    scores: dict[int, float] = {}
    for ranked in ((await session.execute(vec)).scalars().all(), (await session.execute(fts)).scalars().all()):
        for rank, row_id in enumerate(ranked):
            scores[row_id] = scores.get(row_id, 0.0) + 1.0 / (60 + rank)
    if not scores:
        return []
    top = sorted(scores, key=scores.get, reverse=True)[:k]  # type: ignore[arg-type]
    rows = {r.id: r for r in (await session.execute(select(KE).where(KE.id.in_(top)))).scalars()}
    return [Hit(i, rows[i].source, rows[i].doc_title, rows[i].doc_type, rows[i].content, round(scores[i], 5))
            for i in top if i in rows]
