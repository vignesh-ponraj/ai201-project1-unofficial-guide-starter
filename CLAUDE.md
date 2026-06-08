# CLAUDE.md — RAG Pipeline: ASU Student Knowledge Base

> This file is the canonical project context. Read it before answering questions or doing
> tasks on this repo. When we change config or make architecture decisions, update this file.
> Companion docs: [planning.md](planning.md) (assignment spec), [README.md](README.md) (submission writeup).

---

## Project Overview

A RAG pipeline over multiple ASU-related web sources. Domain: **"Thriving at ASU as a freshman"** —
ASU is the largest US university by intake, and relevant freshman info is scattered across blogs,
forums, and posts rather than official pages.

Topic coverage:
- Professor reviews (RateMyProfessors, MyProfReviews, Quora)
- Study tips and finals advice (ASU Online, Hey Sunny, ASU News)
- Student survival guides (Plexuss, Weebly Downtown Devils)
- Freshman housing (Rambler Tempe)
- Student discussion threads (Reddit r/ASU)

**Flow:** Web sources → Preprocessing → Chunking → Embedding → Vector Store → Retrieval → LLM → Answer

---

## Decided Config (MVP) — and Stretch Direction

The context spec and the pinned dependencies disagreed on the vector store; **decision made:
ship the MVP on ChromaDB (dense-only), add hybrid retrieval as a stretch feature after the MVP
is built and tested.**

| Concern | MVP decision | Stretch / future |
|---------|--------------|------------------|
| Vector store | **ChromaDB** (`chromadb>=0.6.0`), dense-only retrieval | Hybrid (dense + sparse BM25): add a separate BM25 index + manual score fusion, or swap to Qdrant/Weaviate/Milvus for native hybrid |
| Retrieval | Dense top-k (no reranker) | Add `cross-encoder/ms-marco-MiniLM-L-6-v2` reranker (retrieve top-20 → rerank to top-5) |
| LLM | **Groq** (`groq==0.15.0`, `GROQ_API_KEY`) | — |
| Embeddings | **BGE-M3** via `sentence-transformers==3.4.1` | — |

**Build order:** dense-only MVP first → run the 5 eval questions → only then layer in hybrid +
reranker as a stretch feature. The "Hybrid / reranker" parts of the Retrieval section below are
**stretch**, not MVP.

---

## Sources & Access Notes

**Accessible (web fetch works):**
- Rambler Tempe freshman housing guide — https://ramblertempe.com/resources/a-freshmans-guide-to-student-housing-at-arizona-state-university/
- MyProfReviews — https://www.myprofreviews.com/r/2467-arizona-state-university-professor
- Hey Sunny finals advice — https://heysunny.asu.edu/blog/finals-advice-you-can-actually-use
- ASU Online survive finals week — https://asuonline.asu.edu/newsroom/online-learning-tips/survive-finals-week/
- ASU News tested exam tips — https://news.asu.edu/20250414-sun-devil-community-tested-tips-taking-exams
- Plexuss survival guide — https://plexuss.com/n/arizona-state-university-survival-guide
- ASU Online first-year checklist — https://asuonline.asu.edu/newsroom/online-learning-tips/prepare-first-year-college-student-checklist/
- Weebly ASU Survival Guide — https://asusurvivalguide.weebly.com/ (+ sub-pages: `/food-and-fun`, `/housing`, `/resources`, `/getting-around`)

**Blocked (require alternative access):**
- RateMyProfessors — robots disallowed; use manual export or RMP API
- Quora — robots disallowed; use manual export or Quora API
- Reddit r/ASU — blocked; use Reddit API (PRAW) or pushshift/arctic_shift

---

## Preprocessing (before chunking)

**All sources:**
- Strip nav bars, footers, cookie banners, social share buttons, ads
- Remove boilerplate (headers, "Apply Now" buttons, sidebar links)
- Add source metadata to every chunk: `source_url`, `source_title`, `source_type`, `author` (if known), `date` (if known)

**`source_type` values:**
- `official` → ASU Online, ASU News, Hey Sunny (ASU-published)
- `editorial` → MyProfReviews, Rambler Tempe, Plexuss (third-party editorial, may be biased)
- `user_opinion` → RateMyProfessors, Quora, Reddit (anonymous, unverified)

**Special cases:**
- **Rambler Tempe:** flag as commercial/biased (written by an apartment complex with financial stake)
- **Weebly:** fetch each sub-page separately. **Update (2026-06-07):** the homepage is now
  **semantically chunked**, not skipped — the finals "Stress Relief Stations" content (eval Q4)
  exists *only* in the homepage blob, so it is split into ~500-char chunks with the TOC nav
  fragments dropped. (Originally: "treat homepage as a table of contents only.") See
  [planning.md](planning.md) Anticipated Challenge #1 for rationale.
- **Quora:** prepend the original question to each answer chunk
- **Reddit:** keep top-level comments only; ignore nested reply chains; group short comments (under ~50 chars) into thematic pairs

---

## Chunking Strategy

**Split method:** Recursive semantic splitting — paragraph boundary → sentence boundary → character count (last resort)

**Overlap:** 15–20% of chunk size, applied **only to prose articles** (not reviews/comments)

| Source | Chunk boundary | Size target | Overlap |
|--------|----------------|-------------|---------|
| RateMyProfessors | 1 review = 1 chunk | 50–200 ch | none |
| MyProfReviews | 1 professor entry = 1 chunk | 100–200 ch | none |
| Quora | 1 answer = 1 chunk | 100–600 ch | none |
| Reddit r/ASU | 1 top-level comment | 50–400 ch | none |
| ASU Online (finals tips) | 1 numbered tip + explanation | 150–400 ch | ~40 ch |
| ASU Online (first-year checklist) | 1 checklist item + body | 200–400 ch | ~40 ch |
| ASU News Miceli Q&A | 1 Q+A pair | 300–600 ch | ~60 ch |
| Hey Sunny blog | `##` section header boundary | 400–700 ch | ~80 ch |
| Rambler Tempe housing guide | section/header boundary | 300–500 ch | ~60 ch |
| Plexuss survival guide | section/topic paragraph | 200–500 ch | ~50 ch |
| Weebly (each sub-page) | paragraph break | 200–500 ch | ~50 ch |

**Chunk metadata fields (every chunk):** `chunk_id`, `source_url`, `source_title`,
`source_type` (official|editorial|user_opinion), `author`, `date`, `chunk_index`
(position within document), `section_title` (nearest heading, if any).

---

## Embedding Model

**Primary: `BAAI/bge-m3`** (via sentence-transformers)
- MTEB retrieval ~72%, context window 8192 tokens, 1024 dims, ~1.2GB disk
- Natively supports dense + sparse vectors (hybrid retrieval)
```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("BAAI/bge-m3")
embeddings = model.encode(chunks, normalize_embeddings=True)
```
- Hybrid mode: call with `return_sparse=True`; combine `final_score = 0.7*dense + 0.3*sparse`

**Fallback: `sentence-transformers/all-MiniLM-L6-v2`**
- Prototyping / low-resource only. **Hard 256-token context limit — silently truncates long chunks.**

---

## Retrieval Approach

**MVP (ChromaDB):** dense-only retrieval — encode query with BGE-M3, retrieve top-k by cosine, pass to LLM. No reranker.

**Stretch (after MVP tested — see Decided Config section):**
- Hybrid retrieval (dense vector + sparse BM25)
- Retrieve top-20 → rerank to top-5 → pass top-5 to LLM
- Reranker: `cross-encoder/ms-marco-MiniLM-L-6-v2` (score all 20 candidates, keep top-5)

**Top-k tuning guidance:**
- `k=5` → default; factual single-topic queries
- `k=8` → synthesis queries ("what do students generally say about X?")
- `k=3` → narrow factual lookups ("what are ASU library hours?")

> Per [planning.md](planning.md): k=5 is a starting point. Run the 5 test questions, count how
> often the correct source lands in position 6–7, and raise k or add reranking if consistently missed.

---

## Generation

- LLM via **Groq** (`groq==0.15.0`, key in `GROQ_API_KEY` / `.env`)
- Prompt inputs: top-5 chunks (text + `source_type` + `source_url`)
- Instruction: cite sources and **flag `source_type` in answer confidence** (signal lower
  confidence for `user_opinion` / commercially-biased `editorial` sources)

---

## Production Tradeoff Notes

- **Context length:** BGE-M3 handles 8192 tokens; all-MiniLM truncates at 256 silently → corrupted embeddings.
- **Multilingual:** not needed now (English sources). BGE-M3 supports it; lightweight models (nomic, mxbai) score near zero cross-lingual.
- **Domain accuracy:** BGE-M3 is general-purpose. Fine-tune on 50–200 labeled ASU query–chunk pairs after baseline + eval gaps identified.
- **Latency:** BGE-M3 (1.2GB) fits GPU VRAM → 5–30× faster than RAM-spill. API alternatives: OpenAI `text-embedding-3-large`, Voyage `voyage-3-large`.
- **Source quality risk:** mix of official / biased editorial / anonymous opinion → propagate `source_type` through to the prompt.

---

## Known Failure Modes

1. Weebly homepage blob → **semantically chunk** it (split into ~500-char pieces, drop TOC nav
   fragments); do not embed the 4,500-char blob as a single chunk. *Updated 2026-06-07: the Q4
   stress-relief detail lives only on the homepage, so it can't be skipped — see planning.md
   Anticipated Challenge #1.*
2. Rambler Tempe commercial bias → flag in metadata; LLM should signal financial-stake
3. Review chunks split mid-opinion → enforce review-boundary chunking, not char count
4. Q+A pairs split apart (Miceli interview) → keep question + answer in same chunk
5. Reddit/Quora anonymous content mixed with expert content → `source_type` metadata critical
6. Shared vocabulary across topics ("finals" in study tips AND bar-exam content) → reranker filters; consider topic tags in metadata
7. Short one-liner Reddit comments embedded alone → group thematically if under ~50 chars

---

## Evaluation — 5 Test Questions

> Ordering and framing match [planning.md](planning.md) (the authored submission doc = source of truth).

1. **How long should a single study session be before a break?** → 25 min (Pomodoro, ASU Online — 25 on / 5-min break ×4 then a 15–30 min break) AND 30 min (Hey Sunny) — both numbers should appear. *Tests cross-source retrieval, numeric precision.*
2. **What makes William Martin a popular professor (MyProfReviews)?** → passion for his work, easy grading, presence, shows up on time, makes courses interesting. *Tests review-boundary chunking integrity.*
3. **What transportation options does ASU provide between campuses?** → free intercampus shuttle (every 30 min; Tempe/Downtown/West), Valley Metro light rail (discounted student passes), rentable campus bikes, parking structures at each campus. *Tests Weebly sub-page preprocessing, 4-item completeness.*
4. **What resources are at ASU libraries specifically during finals week (Weebly)?** → "Stress Relief Stations" with free food, puzzles, coloring books, stress balls. *Tests Weebly homepage blob NOT chunked; detail in sub-page.*
5. **What common mistakes do students make on exams, and how to avoid them?** → Source: Toni Miceli interview (ASU News). Mistake = too much time on flashcards / passive memorization (California bar exam). Fix = timed practice + writing summaries/essays from memory (Missouri/Illinois); success is about *how* you study, not how much. *Tests Q+A pair chunking kept intact.*

---

## Architecture Components

**Ingestion:** `[Web Sources] → [Scraper / Manual Export] → [HTML Cleaner] → [Chunker] → [Metadata Tagger]`

**Embedding:** `[Chunks + Metadata] → [BGE-M3 Encoder] → [Dense Vectors] (+ [Sparse/BM25] if hybrid)`

**Storage:** **ChromaDB** holding dense vectors + metadata per chunk (MVP).
*Stretch: add sparse/BM25 or swap to Qdrant/Weaviate/Milvus for native hybrid — see Decided Config.*

**Query (MVP):** `[User Query] → [BGE-M3 Encoder] → [ChromaDB dense top-k] → [LLM (Groq), source-aware prompt] → [Answer]`

**Query (stretch):** `… → [Hybrid Retriever] → [Top-20] → [Cross-Encoder Reranker] → [Top-5] → [LLM] → [Answer]`

---

## Repo Layout & Setup

- [planning.md](planning.md) — assignment planning doc (spec to direct AI codegen)
- [README.md](README.md) — submission writeup template (fill **after** each part is built/tested)
- [requirements.txt](requirements.txt) — `sentence-transformers`, `chromadb`, `groq`, `python-dotenv`; optional `gradio`/`streamlit` (Milestone 5 UI), `pdfplumber` (PDF ingestion)
- [.env.example](.env.example) — copy to `.env`, set `GROQ_API_KEY` (free at https://console.groq.com); `.env` is gitignored
- `documents/` — local source documents (manual exports for blocked sources)

**Milestones:** M3 = ingestion + chunking · M4 = embedding + retrieval · M5 = generation + interface

### Git / Commit Conventions

- **Do NOT attribute commits to Claude.** No `Co-Authored-By: Claude ...` trailer and no
  "Generated with Claude Code" footer on commits or PRs. Commits are authored solely by the user
  (Vignesh Ponraj). This is a hard rule for this repo.

---

## AI Usage — Override Log

> Running log of where the user directed/overrode AI-generated output, captured live so it can
> feed [README.md](README.md)'s **AI Usage** section (which requires concrete override examples,
> not "I used AI to code"). Each entry: date · what AI produced · what was changed/overridden · why.

| Date | Stage | What AI produced | What was overridden / directed | Why |
|------|-------|------------------|--------------------------------|-----|
| 2026-06-07 | Architecture | Context spec recommended Qdrant/Weaviate/Milvus for native hybrid retrieval | Kept ChromaDB dense-only for MVP; hybrid demoted to stretch | Get a working baseline first before adding hybrid complexity ([[vectorstore-decision]]) |
| 2026-06-07 | Chunking | Per-source chunker honoring CLAUDE.md size table | Refined planning.md's flat "200–600" range; let review sources go below 200 and keep over-long single reviews whole; no overlap for atomic units | Atomic reviews must stay one intact thought, not be padded/split to hit a size target |
| 2026-06-07 | Preprocessing | Plan said skip the Weebly homepage ("TOC only") | Switched to semantically chunking the homepage (drop TOC nav fragments) | Live site: the Q4 "Stress Relief Stations" content exists *only* on the homepage; skipping it makes Q4 unanswerable |
| 2026-06-07 | Cleaning | Generic boilerplate stripper dropped `<form>` and substring-matched class hints | Kept `<form>` (ASP.NET wraps whole page); switched class-hint matching to sub-token + negation guard | Blanket rules nuked real content: MyProfReviews (whole page in one `<form>`) and Weebly (`id="wsite-content" class="wsite-not-footer"` matched "footer") |
| 2026-06-07 | Fetching | `requests` decoded pages as ISO-8859-1 when charset header absent | Force `apparent_encoding`/UTF-8 | Mis-decoding mangled UTF-8 punctuation (’ — “) across every source, corrupting text and embeddings |
| _add as we go_ | | | | |
