"""Persistent ChromaDB store for chunk embeddings + metadata."""
import pathlib
from typing import Callable, List
import chromadb

PERSIST_DIR = pathlib.Path("chroma_db")
COLLECTION = "asu_chunks"
_SCALAR = (str, int, float, bool)


def get_client(persist_dir=PERSIST_DIR):
    return chromadb.PersistentClient(path=str(persist_dir))


def get_collection(persist_dir=PERSIST_DIR, create: bool = False):
    client = get_client(persist_dir)
    if create:
        return client.get_or_create_collection(
            COLLECTION, metadata={"hnsw:space": "cosine"})
    return client.get_collection(COLLECTION)


def sanitize_metadata(chunk: dict) -> dict:
    """Chroma metadata must be flat scalars; drop `text` and any None values."""
    md = {}
    for k, v in chunk.items():
        if k == "text":
            continue
        if isinstance(v, bool) or (v is not None and isinstance(v, _SCALAR)):
            md[k] = v
    return md


def build_index(chunks: List[dict], embedder: Callable, persist_dir=PERSIST_DIR,
                batch_size: int = 64) -> int:
    """(Re)create the collection and add every chunk. Returns count added."""
    client = get_client(persist_dir)
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    col = client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        embs = embedder([c["text"] for c in batch])
        col.add(
            ids=[c["chunk_id"] for c in batch],
            documents=[c["text"] for c in batch],
            embeddings=[e.tolist() for e in embs],
            metadatas=[sanitize_metadata(c) for c in batch],
        )
    return col.count()
