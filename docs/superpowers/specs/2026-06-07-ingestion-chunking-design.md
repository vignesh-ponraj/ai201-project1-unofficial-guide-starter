# Design: Milestone 3 — Ingestion & Chunking

> ASU Freshman Unofficial Guide RAG pipeline. Covers M3 only (ingestion + chunking).
> Canonical project context: [CLAUDE.md](../../../CLAUDE.md) · assignment spec: [planning.md](../../../planning.md).
> Status: approved 2026-06-07.

## Goal

Load the project's web sources, save a reproducible raw-text snapshot, clean each
source down to substantive content, and produce chunks that match the per-source
size/overlap targets in CLAUDE.md's Chunking Strategy table — each chunk a complete,
retrievable thought, tagged with the 9 metadata fields. Output: `data/chunks.jsonl`.

## Decisions (resolved with user, 2026-06-07)

1. **Data acquisition:** fetcher script pulls the live accessible URLs and commits a raw
   snapshot (`documents/raw/<id>.html` + `<id>.txt`) so the pipeline is reproducible offline.
2. **Blocked sources** (RateMyProfessors / Quora / Reddit): build the per-source preprocessors,
   but only run them when an export file is present in `documents/exports/`. If absent, log a
   warning and skip. None of the 5 eval questions require these sources, so MVP still works.
3. **HTML parser:** add `beautifulsoup4` + `lxml` and `requests` to `requirements.txt`.
4. **Chunk-size spec:** CLAUDE.md's per-source table is authoritative; it refines planning.md's
   "200–600 chars" summary. A note is added to planning.md's Chunking Strategy explaining why
   review sources go below 200 (atomic reviews must stay one self-contained thought).

## Environment notes (from connectivity probe)

- 6 of 7 accessible sources return `200` with a `User-Agent` header.
- **Rambler Tempe returns `403`** (bot blocker). Handled via the `snapshot` fetch strategy:
  the raw file is fetched once (via the assistant's WebFetch tool) and committed; the fetcher
  reads the saved snapshot instead of hitting the network.
- `bs4` not yet installed locally → `pip install` after editing requirements.

## Data flow

```
URLs ──fetch──▶ documents/raw/<id>.html + <id>.txt   (committed; reproducible)
                       │
                    clean (bs4: strip nav/footer/script/style/ads/share/cookie/boilerplate;
                       │        decode HTML entities; collapse whitespace)
                  preprocess (per-source special cases)
                       │
                    chunk (recursive semantic split + per-source size range / overlap)
                       │
                  tag metadata (9 fields) ──▶ data/chunks.jsonl
```

## Modules (`rag/` package)

- `rag/sources.py` — `SOURCE_REGISTRY`. One entry per source: `id`, `url`, `title`,
  `source_type` (`official|editorial|user_opinion`), `author`, `date`, `fetch` strategy
  (`live|snapshot|export`), chunk params (`size_min`, `size_max`, `overlap`, `boundary`,
  `apply_overlap`), and flags (`commercial_bias`, `weebly_subpages`).
- `rag/fetch.py` — `fetch_source(entry)`: `requests` + UA; writes raw HTML and a normalized
  `.txt` to `documents/raw/`. `snapshot` reads a pre-saved file; `export` reads
  `documents/exports/<id>.*` if present, else warns and returns nothing.
- `rag/clean.py` — `html_to_text(html)` via BeautifulSoup: drop `script/style/nav/footer/header/
  aside`, ad/share/cookie/"Read more" elements by tag and class heuristics; decode entities;
  collapse whitespace. Returns clean text (and section headings where detectable).
- `rag/chunking.py` — `recursive_split(text, size_min, size_max, separators)` greedily packs
  semantic units (`\n\n → \n → ". " → " " → char`) into the size range; `chunk_document(...)`
  dispatches per source. Reviews/comments: 1 boundary unit = 1 chunk, no overlap. Prose: overlap
  carried (last `overlap` chars of the previous chunk prepended to the next).
- `rag/preprocess.py` — Weebly (fetch sub-pages `/food-and-fun`, `/housing`, `/resources`,
  `/getting-around`; homepage = TOC, **never chunked**), Quora (prepend question to each answer),
  Reddit (top-level comments only; group comments under ~50 chars thematically), Rambler
  (set `commercial_bias`).
- `rag/metadata.py` — builds the 9 fields: `chunk_id`, `source_url`, `source_title`,
  `source_type`, `author`, `date`, `chunk_index`, `section_title`, plus `source_id`.
  `chunk_id = "{source_id}::{chunk_index}"`.
- `rag/ingest.py` + `scripts/run_ingest.py` — orchestrate all sources → `data/chunks.jsonl`,
  then print the verification report.

## Per-source chunking (from CLAUDE.md table — authoritative)

| Source | Boundary | Size (ch) | Overlap |
|--------|----------|-----------|---------|
| RateMyProfessors | 1 review = 1 chunk | 50–200 | none |
| MyProfReviews | 1 professor entry = 1 chunk | 100–200 | none |
| Quora | 1 answer = 1 chunk | 100–600 | none |
| Reddit r/ASU | 1 top-level comment | 50–400 | none |
| ASU Online (finals tips) | 1 numbered tip + body | 150–400 | ~40 |
| ASU Online (first-year checklist) | 1 checklist item + body | 200–400 | ~40 |
| ASU News Miceli Q&A | 1 Q+A pair | 300–600 | ~60 |
| Hey Sunny blog | `##` section header | 400–700 | ~80 |
| Rambler Tempe | section/header | 300–500 | ~60 |
| Plexuss | section/topic paragraph | 200–500 | ~50 |
| Weebly (each sub-page) | paragraph break | 200–500 | ~50 |

## Testing (TDD for pure-logic modules)

Unit tests written first for `chunking`, `clean`, `preprocess` (deterministic, no network);
`fetch` exercised against saved HTML fixtures. Key cases:

- `recursive_split` keeps chunks within `[size_min, size_max]`; trailing small chunk merged.
- Prose sources carry overlap; review/comment sources have **zero** overlap.
- `clean` removes HTML tags/entities/nav/footer (no `<div>`, no `&#39;` artifacts).
- Weebly homepage produces **no chunks**; sub-pages do.
- A William-Martin-style single review stays one intact chunk.
- A Q+A pair stays in one chunk.

## Verification report (`run_ingest`, against planning.md M3 verify list)

- Per-source chunk-size distribution lands in the target ranges.
- Review sources have zero overlap.
- No chunk originates from the Weebly homepage blob.
- The William Martin review is one intact chunk; the Miceli Q&A stays together.
- Every chunk has all 9 metadata fields populated (or explicit `null`) and a valid `source_type`.

## Out of scope (later milestones)

- M4: BGE-M3 embedding, ChromaDB collection, `retrieve(query, k=5)`.
- M5: Groq generation, source-aware prompt, Gradio UI.
- Stretch: hybrid (BM25) retrieval, cross-encoder reranker.
