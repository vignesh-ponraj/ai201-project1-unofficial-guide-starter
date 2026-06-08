# M4 Embedding & Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Embed the 150 M3 chunks with BGE-M3, store them in a persistent ChromaDB collection with metadata, and expose `retrieve(query, k=5)`; verify by retrieving the 5 eval questions.

**Architecture:** Three small `rag/` modules — `embed` (BGE-M3 encoder), `store` (ChromaDB persistence + metadata sanitization), `retrieve` (query → ranked chunks) — plus two scripts (`build_index`, `eval_retrieval`). Unit tests inject a fake embedder so the suite stays light; the real 1.2 GB model runs only in the eval script.

**Tech Stack:** Python 3.9, `sentence-transformers==3.4.1` + `torch` (BGE-M3), `chromadb>=0.6.0`, `numpy`, `pytest`.

---

## File Structure

- `rag/embed.py` — `EMBED_MODEL_NAME`, `EMBED_DIM=1024`, `get_model()` lazy singleton, `embed_texts(texts)`.
- `rag/store.py` — `COLLECTION`, `get_client`, `get_collection`, `sanitize_metadata`, `build_index`.
- `rag/retrieve.py` — `retrieve(query, k=5, embedder=...)`.
- `rag/corpus.py` — `load_chunks(path)` shared jsonl loader.
- `scripts/build_index.py`, `scripts/eval_retrieval.py` — CLI entry points.
- `tests/test_corpus.py`, `tests/test_store.py`, `tests/test_retrieve.py` — unit tests (fake embedder).
- `requirements.txt` — add `numpy` (torch comes via sentence-transformers).

---

### Task 1: Install M4 dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add numpy to `requirements.txt`**

Under the `# Ingestion & chunking (Milestone 3):` block, add a new block:

```
# Embedding & retrieval (Milestone 4):
numpy==1.26.4
```

(`sentence-transformers==3.4.1`, `chromadb>=0.6.0` are already pinned in requirements.txt; they pull in torch.)

- [ ] **Step 2: Install**

Run: `python3 -m pip install "sentence-transformers==3.4.1" "chromadb>=0.6.0" numpy==1.26.4`
Expected: completes; this downloads torch (~200 MB) and may take several minutes.

- [ ] **Step 3: Verify imports**

Run: `python3 -c "import sentence_transformers, chromadb, numpy; print('ok', chromadb.__version__)"`
Expected: prints `ok <version>` with no ImportError.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "Add M4 embedding/retrieval dependencies"
```

---

### Task 2: Shared chunk loader (`rag/corpus.py`)

**Files:**
- Create: `rag/corpus.py`
- Test: `tests/test_corpus.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_corpus.py
import json
from rag.corpus import load_chunks

def test_load_chunks_reads_jsonl(tmp_path):
    p = tmp_path / "c.jsonl"
    rows = [{"chunk_id": "a::0", "text": "hello"}, {"chunk_id": "a::1", "text": "world"}]
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    out = load_chunks(p)
    assert [c["chunk_id"] for c in out] == ["a::0", "a::1"]
    assert out[0]["text"] == "hello"

def test_load_chunks_skips_blank_lines(tmp_path):
    p = tmp_path / "c.jsonl"
    p.write_text('{"chunk_id":"a::0","text":"x"}\n\n', encoding="utf-8")
    assert len(load_chunks(p)) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_corpus.py -q`
Expected: FAIL with "No module named 'rag.corpus'".

- [ ] **Step 3: Write `rag/corpus.py`**

```python
# rag/corpus.py
"""Load the M3 chunk corpus from JSONL."""
import json
import pathlib
from typing import List

CHUNKS_PATH = pathlib.Path("data/chunks.jsonl")


def load_chunks(path=CHUNKS_PATH) -> List[dict]:
    path = pathlib.Path(path)
    chunks = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_corpus.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add rag/corpus.py tests/test_corpus.py
git commit -m "Add shared JSONL chunk loader"
```

---

### Task 3: Embedder (`rag/embed.py`)

**Files:**
- Create: `rag/embed.py`
- Test: none (real model is heavy; exercised in eval script). Smoke-checked in Step 4.

- [ ] **Step 1: Write `rag/embed.py`**

```python
# rag/embed.py
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
```

- [ ] **Step 2: Lint-import (no model download)**

Run: `python3 -c "import rag.embed as e; print(e.EMBED_MODEL_NAME, e.EMBED_DIM)"`
Expected: prints `BAAI/bge-m3 1024` (no model download — `get_model` not called).

- [ ] **Step 3: Commit**

```bash
git add rag/embed.py
git commit -m "Add BGE-M3 embedder (lazy singleton, normalized)"
```

---

### Task 4: Store + metadata sanitization (`rag/store.py`)

**Files:**
- Create: `rag/store.py`
- Test: `tests/test_store.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_store.py
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
    # deterministic 1024-d vectors: 'a' -> all 1s, others -> all 0s but slot 1
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_store.py -q`
Expected: FAIL with "No module named 'rag.store'".

- [ ] **Step 3: Write `rag/store.py`**

```python
# rag/store.py
"""Persistent ChromaDB store for chunk embeddings + metadata."""
import pathlib
from typing import Callable, List, Optional
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_store.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add rag/store.py tests/test_store.py
git commit -m "Add ChromaDB store with metadata sanitization"
```

---

### Task 5: Retrieve (`rag/retrieve.py`)

**Files:**
- Create: `rag/retrieve.py`
- Test: `tests/test_retrieve.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_retrieve.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_retrieve.py -q`
Expected: FAIL with "No module named 'rag.retrieve'".

- [ ] **Step 3: Write `rag/retrieve.py`**

```python
# rag/retrieve.py
"""Dense retrieval over the ChromaDB collection."""
from typing import Callable, List, Optional
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_retrieve.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add rag/retrieve.py tests/test_retrieve.py
git commit -m "Add dense retrieval returning ranked chunks with metadata"
```

---

### Task 6: Build-index CLI (`scripts/build_index.py`)

**Files:**
- Create: `scripts/build_index.py`

- [ ] **Step 1: Write `scripts/build_index.py`**

```python
# scripts/build_index.py
"""Embed all M3 chunks with BGE-M3 and build the persistent ChromaDB index.

Usage: python3 -m scripts.build_index
"""
from rag.corpus import load_chunks
from rag.embed import embed_texts, EMBED_DIM
from rag.store import build_index, PERSIST_DIR


def main():
    chunks = load_chunks()
    print(f"Loaded {len(chunks)} chunks. Embedding with BGE-M3 (dim={EMBED_DIM})...")
    n = build_index(chunks, embedder=embed_texts)
    print(f"Indexed {n} chunks into ChromaDB at {PERSIST_DIR}/")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it (downloads the model, builds the index)**

Run: `python3 -m scripts.build_index`
Expected: downloads BGE-M3 on first run (slow), then prints `Indexed 150 chunks ...`.

- [ ] **Step 3: Commit**

```bash
git add scripts/build_index.py
git commit -m "Add build-index script (BGE-M3 -> ChromaDB)"
```

---

### Task 7: Eval-retrieval smoke test (`scripts/eval_retrieval.py`)

**Files:**
- Create: `scripts/eval_retrieval.py`

- [ ] **Step 1: Write `scripts/eval_retrieval.py`**

```python
# scripts/eval_retrieval.py
"""Run the 5 eval questions through retrieval and report whether the expected
source lands in top-k, and at what rank. Verifies embedding dim + retrieval quality.

Usage: python3 -m scripts.eval_retrieval
"""
from rag.embed import embed_texts, EMBED_DIM
from rag.retrieve import retrieve

# (question, set of acceptable expected source_ids)
EVAL = [
    ("How long should a single study session be before a break?",
     {"asuonline_finals", "heysunny"}),
    ("What makes William Martin a popular professor?",
     {"myprofreviews"}),
    ("What transportation options does ASU provide between campuses?",
     {"weebly"}),
    ("What resources are at ASU libraries during finals week?",
     {"weebly"}),
    ("What common mistakes do students make on exams and how to avoid them?",
     {"asunews_miceli"}),
]


def main():
    assert embed_texts(["dim check"]).shape[1] == EMBED_DIM, "unexpected embedding dim"
    passed = 0
    for q, expected in EVAL:
        hits = retrieve(q, k=5)
        ranks = [i + 1 for i, h in enumerate(hits) if h["source_id"] in expected]
        ok = bool(ranks)
        passed += ok
        rank = ranks[0] if ranks else "—"
        top = hits[0]
        print(f"[{'PASS' if ok else 'MISS'}] rank={rank} | {q[:48]!r}")
        print(f"        top: ({top['source_id']}, score={top['score']:.3f}) {top['text'][:70]!r}")
    print(f"\n{passed}/{len(EVAL)} eval questions retrieved their expected source in top-5")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

Run: `python3 -m scripts.eval_retrieval`
Expected: prints PASS/MISS per question and a `X/5` summary. Target: 5/5 (record any MISS rank as top-k tuning evidence).

- [ ] **Step 3: If any question MISSes**, note its rank. If the expected source consistently lands at rank 6–7, that is the documented evidence to raise k or pursue the reranker stretch — record it in planning.md's Retrieval Approach reflection. (No code change required to pass this milestone; record the observation.)

- [ ] **Step 4: Commit**

```bash
git add scripts/eval_retrieval.py
git commit -m "Add eval-retrieval smoke test for the 5 questions"
```

---

### Task 8: Full suite + README/doc note

**Files:**
- Modify: `planning.md` (Retrieval Approach reflection — fill in observed top-k results)

- [ ] **Step 1: Run the full unit suite**

Run: `python3 -m pytest -q`
Expected: all M3 + M4 unit tests PASS (fake-embedder tests; no model download).

- [ ] **Step 2: Record the eval-retrieval result in `planning.md`**

Under **Retrieval Approach → Production tradeoff reflection** in `planning.md`, append a line
with the actual observed result, e.g.:

```markdown
> **M4 retrieval smoke test (2026-06-07):** All 5 eval questions retrieved their expected
> source within top-5 at k=5 [or: "Q_N's source landed at rank R — see eval_retrieval output"].
> This confirms k=5 is adequate for the current corpus; the reranker stretch is deferred.
```

(Use the actual numbers from the Task 7 run.)

- [ ] **Step 3: Commit**

```bash
git add planning.md
git commit -m "Record M4 retrieval smoke-test results"
```

---

## Self-Review notes

- **Spec coverage:** embedder BGE-M3 normalized 1024-d (T3) · persistent Chroma cosine collection (T4) · metadata sanitization drops None+text (T4) · retrieve(query,k=5) with score+metadata (T5) · build_index script (T6) · eval_retrieval over 5 questions w/ expected sources + dim assert (T7) · fake-embedder unit tests (T2/T4/T5) · install deps (T1). All spec items covered.
- **Type consistency:** `embed_texts(texts)->ndarray`, `build_index(chunks, embedder, persist_dir)`, `get_collection(persist_dir, create)`, `retrieve(query, k, embedder, persist_dir)`, `sanitize_metadata(chunk)`, `load_chunks(path)` consistent across tasks. `persist_dir` param threaded through store + retrieve so tests use tmp_path.
- **Note:** `chroma_db/` is already gitignored (M3 .gitignore) — the index is not committed; it is rebuilt via `scripts/build_index`.
