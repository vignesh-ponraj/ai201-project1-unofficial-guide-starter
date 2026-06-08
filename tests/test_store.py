import numpy as np
from rag.store import sanitize_metadata, build_index, get_collection


def test_sanitize_drops_none_and_text():
    chunk = {"chunk_id": "a::0", "text": "body", "source_type": "official",
             "author": None, "date": None, "chunk_index": 3, "commercial_bias": False}
    md = sanitize_metadata(chunk)
    assert "text" not in md            # text is the document, not metadata
    assert "author" not in md          # None dropped
    assert md["source_type"] == "official"
    assert md["chunk_index"] == 3
    assert md["commercial_bias"] is False


def _fake_embedder(texts):
    out = []
    for t in texts:
        v = np.zeros(1024, dtype="float32")
        v[0] = 1.0 if "alpha" in t else 0.0
        v[1] = 1.0 if "beta" in t else 0.0
        out.append(v)
    return np.array(out)


def test_build_index_adds_all_chunks(tmp_path):
    chunks = [{"chunk_id": "a::0", "text": "alpha topic", "source_type": "official", "author": None},
              {"chunk_id": "a::1", "text": "beta topic", "source_type": "editorial", "author": None}]
    build_index(chunks, embedder=_fake_embedder, persist_dir=tmp_path)
    col = get_collection(persist_dir=tmp_path)
    assert col.count() == 2
