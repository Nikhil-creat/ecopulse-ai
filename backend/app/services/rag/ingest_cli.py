"""Seed the knowledge base:  python -m app.services.rag.ingest_cli [extra_dir]"""
import asyncio
import sys
from pathlib import Path

from app.db.worker_session import worker_session
from app.services.rag.loaders import KNOWLEDGE_DIR, parse_front_matter, read_file_text
from app.services.rag.store import ingest_document


async def seed(extra: Path | None = None) -> dict[str, int]:
    out: dict[str, int] = {}
    dirs = [KNOWLEDGE_DIR] + ([extra] if extra else [])
    async with worker_session() as session:
        for d in dirs:
            for path in sorted(d.glob("*")):
                if path.suffix.lower() not in {".md", ".txt", ".pdf"}:
                    continue
                meta, body = parse_front_matter(read_file_text(path))
                n = await ingest_document(
                    session, source=meta.get("source", path.stem.upper()),
                    title=meta.get("title", path.stem), doc_type=meta.get("doc_type", "guideline"), text=body)
                out[path.name] = n
    return out


if __name__ == "__main__":
    print(asyncio.run(seed(Path(sys.argv[1]) if len(sys.argv) > 1 else None)))
