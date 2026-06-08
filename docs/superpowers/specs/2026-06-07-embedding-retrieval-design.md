# Design: Milestone 4 — Embedding & Retrieval

> ASU Freshman Unofficial Guide RAG pipeline. Covers M4 only (embedding + retrieval).
> Canonical project context: [CLAUDE.md](../../../CLAUDE.md) · spec: [planning.md](../../../planning.md).
> Builds on M3 output `data/chunks.jsonl` (150 chunks). Status: approved 2026-06-07.

## Goal

Embed the M3 chunks with BGE-M3, store them in a persistent ChromaDB collection with
their metadata, and expose `retrieve(query, k=5)` returning ranked chunks (text + score +
`source_type`/`source_url`) so M5 can build a source-aware prompt. Verify by running the 5
eval questions as a retrieval smoke test.

## Decisions (resolved with user, 2026-06-07)

1. **Embedding model: `BAAI/bge-m3`** as specced in CLAUDE.md (honor the decided config), even
   though the corpus (max chunk ~180 tokens) would fit MiniLM's 256-token window. 1024-dim,
   `normalize_embeddings=True`. No deviation, no doc change.
2. **Scope: full build + verify this session** — install deps, download the model, embed all
   150 chunks, build the ChromaDB index, run the 5 eval questions end-to-end (retrieval-only).
3. **Unit tests inject a fake embedder** so the test suite stays light; the real 1.2 GB model
   only runs in the `eval_retrieval` verification script.
4. **ChromaDB can't store `None`/nested values** → null metadata keys are dropped (not stored as
   empty strings) when indexing.

## Environment notes (from probe)

- Python 3.9.6, CPU. torch / sentence-transformers / chromadb not yet installed → `pip install`.
- 150 chunks, max 715 chars (~180 tokens), p95 ~614 → no truncation risk for BGE-M3 (8192 window).

## Data flow

```
data/chunks.jsonl
      │  embed (BGE-M3, normalize=True, 1024-dim)
      ▼
ChromaDB persistent collection "asu_chunks" (vectors + sanitized metadata + chunk text)
      │  retrieve(query, k): encode query → cosine search
      ▼
ranked chunks: [{text, score, source_type, source_url, source_id, section_title, ...}]
```

## Modules (extend `rag/`)

- `rag/embed.py` — `get_model()` lazy singleton loads `BAAI/bge-m3`; `embed_texts(texts) ->
  np.ndarray` with `normalize_embeddings=True`. `EMBED_MODEL_NAME` and `EMBED_DIM = 1024`
  module constants. The encoder is the same for documents and queries.
- `rag/store.py` — `get_client()` → `chromadb.PersistentClient("chroma_db")`; `COLLECTION =
  "asu_chunks"`; `get_collection(create=False)` with `metadata={"hnsw:space": "cosine"}`;
  `sanitize_metadata(chunk)` drops the `text` key and any `None` values, keeping str/int/
  float/bool only; `build_index(chunks, embedder=embed_texts)` (re)creates the collection and
  adds ids/documents/embeddings/metadatas in batches.
- `rag/retrieve.py` — `retrieve(query, k=5, embedder=embed_texts) -> list[dict]`: encodes the
  query, calls `collection.query(n_results=k)`, maps each hit to `{text, score, ...metadata}`
  where `score = 1 - distance`.
- `scripts/build_index.py` — load `chunks.jsonl` → `build_index` → print chunk count + dim.
- `scripts/eval_retrieval.py` — the 5 eval questions, each with an `expected_source_id`; print
  rank at which the expected source first appears in top-k and the top hit's snippet.

## Eval verification (the 5 questions → expected source)

| # | Question (abbrev) | Expected source_id |
|---|-------------------|--------------------|
| 1 | study session length before a break | asuonline_finals and/or heysunny |
| 2 | what makes William Martin popular | myprofreviews |
| 3 | transportation between campuses | weebly (getting-around / homepage) |
| 4 | library resources during finals week | weebly (homepage) |
| 5 | common exam mistakes & how to avoid | asunews_miceli |

Pass = expected source appears within top-k (k=5). Record rank for the top-k tuning note.

## Testing

- **Unit (no model):** `sanitize_metadata` drops `None` + `text`; `retrieve` result mapping
  (distance→score, metadata passthrough) using an injected fake embedder + a temp Chroma
  collection; `chunks.jsonl` round-trips.
- **Integration (real model):** `scripts/eval_retrieval.py` asserts `EMBED_DIM == 1024`, builds
  the index, and checks each eval question's expected source is in top-k.

## Out of scope

- M5: Groq generation, source-aware prompt, Gradio UI.
- Stretch: hybrid (BM25) retrieval, cross-encoder reranker.
