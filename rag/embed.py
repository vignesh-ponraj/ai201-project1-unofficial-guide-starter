"""BGE-M3 dense embeddings via sentence-transformers.

Lazy singleton so importing this module is cheap; the 1.2 GB model only loads on
first embed call. Embeddings are L2-normalized so cosine == dot product downstream.
"""
import numpy as np

EMBED_MODEL_NAME = "BAAI/bge-m3"
EMBED_DIM = 1024

_model = None


def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(EMBED_MODEL_NAME)
    return _model


def embed_texts(texts, batch_size: int = 16) -> np.ndarray:
    """Encode a list of strings to normalized (n, 1024) float32 vectors."""
    model = get_model()
    vecs = model.encode(list(texts), normalize_embeddings=True,
                        batch_size=batch_size, show_progress_bar=False)
    return np.asarray(vecs, dtype="float32")
