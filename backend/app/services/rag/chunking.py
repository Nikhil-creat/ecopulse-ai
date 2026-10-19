import re


def _tail(text: str, overlap: int) -> str:
    if overlap <= 0 or len(text) <= overlap:
        return text if overlap > 0 else ""
    tail = text[-overlap:]
    cut = tail.find(" ")
    return tail[cut + 1 :] if cut != -1 else tail


def chunk_text(text: str, max_chars: int = 1200, overlap: int = 150) -> list[str]:
    """Paragraph-aware splitter with sentence fallback and character overlap between chunks."""
    pieces: list[str] = []
    for para in (p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()):
        if len(para) <= max_chars:
            pieces.append(para)
        else:
            pieces.extend(s for s in re.split(r"(?<=[.!?])\s+", para) if s)

    chunks: list[str] = []
    cur = ""
    for piece in pieces:
        if cur and len(cur) + len(piece) + 2 > max_chars:
            chunks.append(cur.strip())
            cur = (_tail(cur, overlap) + "\n\n" + piece).strip()
        else:
            cur = f"{cur}\n\n{piece}".strip() if cur else piece
    if cur.strip():
        chunks.append(cur.strip())
    return chunks
