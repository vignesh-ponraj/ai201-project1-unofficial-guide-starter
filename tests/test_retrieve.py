import numpy as np
from rag.store import build_index
from rag.retrieve import retrieve


def _fake_embedder(texts):
    out = []
    for t in texts:
        v = np.zeros(1024, dtype="float32")
        v[0] = 1.0 if "alpha" in t else 0.0
        v[1] = 1.0 if "beta" in t else 0.0
        out.append(v)
    return np.array(out)


def test_retrieve_returns_ranked_metadata(tmp_path):
    chunks = [{"chunk_id": "a::0", "text": "alpha topic here", "source_type": "official",
               "source_url": "http://a", "author": None},
              {"chunk_id": "b::0", "text": "beta topic here", "source_type": "editorial",
               "source_url": "http://b", "author": None}]
    build_index(chunks, embedder=_fake_embedder, persist_dir=tmp_path)
    hits = retrieve("alpha please", k=2, embedder=_fake_embedder, persist_dir=tmp_path)
    assert hits[0]["chunk_id"] == "a::0"          # alpha query -> alpha chunk first
    assert hits[0]["source_type"] == "official"
    assert hits[0]["source_url"] == "http://a"
    assert "alpha" in hits[0]["text"]
    assert hits[0]["score"] >= hits[1]["score"]    # ranked by score desc
