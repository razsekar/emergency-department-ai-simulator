"""Local sentence-transformers embedder (lazy-loaded singleton). No remote API is called at query time."""
import threading

from app.modules.rag.application import config


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str = config.EMBEDDING_MODEL) -> None:
        self.model_name = model_name
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        with self._lock:
            if self._model is None:
                from sentence_transformers import SentenceTransformer  # heavy import, deferred

                self._model = SentenceTransformer(self.model_name)
                get_dim = getattr(self._model, "get_embedding_dimension", None) or self._model.get_sentence_embedding_dimension
                dim = get_dim()
                if dim != config.EMBEDDING_DIM:
                    raise RuntimeError(f"Model dimension {dim} != schema dimension {config.EMBEDDING_DIM}")
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """L2-normalized embeddings, so cosine similarity equals the dot product."""
        vectors = self._load().encode(texts, normalize_embeddings=True, show_progress_bar=False, batch_size=32)
        return [v.tolist() for v in vectors]


_default: SentenceTransformerEmbedder | None = None


def get_default_embedder() -> SentenceTransformerEmbedder:
    global _default
    if _default is None:
        _default = SentenceTransformerEmbedder()
    return _default


def set_default_embedder(embedder) -> None:
    """Swap the process-wide embedder (used by tests); pass None to restore lazy default loading."""
    global _default
    _default = embedder
