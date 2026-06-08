"""Dense retrieval over the ChromaDB collection."""
from typing import Callable, List
from rag.embed import embed_texts
from rag.store import get_collection, PERSIST_DIR


def retrieve(query: str, k: int = 5, embedder: Callable = embed_texts,
             persist_dir=PERSIST_DIR) -> List[dict]:
    """Return up to k chunks most similar to query, ranked by score (1 - cosine distance)."""
    col = get_collection(persist_dir=persist_dir)
    q_emb = embedder([query])[0].tolist()
    res = col.query(query_embeddings=[q_emb], n_results=k,
                    include=["documents", "metadatas", "distances"])
    hits = []
    for doc, md, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        hit = dict(md)
        hit["text"] = doc
        hit["score"] = 1.0 - dist
        hits.append(hit)
    return hits
