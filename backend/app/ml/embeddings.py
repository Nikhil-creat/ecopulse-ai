import threading

from app.core.config import get_settings

_lock = threading.Lock()
_model = None


def encode(texts: list[str]) -> list[list[float]]:
    """all-MiniLM-L6-v2 (384-d), L2-normalised. Blocking: call via asyncio.to_thread in async code."""
    global _model
    with _lock:
        if _model is None:
            from sentence_transformers import SentenceTransformer

            _model = SentenceTransformer(get_settings().embedding_model)
    return _model.encode(texts, normalize_embeddings=True, batch_size=32).tolist()
