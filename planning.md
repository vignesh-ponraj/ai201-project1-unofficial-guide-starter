# Project 1 Planning: The Unofficial Guide

> Write this document before you write any pipeline code.
> Your spec and architecture diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Update the Retrieval Approach and Chunking Strategy sections if you change your approach during implementation.
> Update this file before starting any stretch features.

---

## Domain

The domain is about "Thriving at ASU for freshman". For a university which is the largest in the US by intake, it is hard to find relevant information for freshmen. There's very few official pages so I had to search and find blogs, forums and facebook posts.

---

## Documents

<!-- List your specific sources: URLs, subreddit names, forum threads, or file descriptions.
     Aim for at least 10 sources that together cover different subtopics or perspectives within your domain. -->

| # | Source | Description | URL or location |
|---|--------|-------------|-----------------|
| 1 | RateMyProfessors | Professors are rated on multiple criterias so you know what to expect for the courses | https://www.ratemyprofessors.com/search/professors/15723?q=*&did=11 |
| 2 | Quora | Crowd-sourced info on Professor recommendations | https://www.quora.com/Which-professors-at-Arizona-State-University-would-you-recommend-that-people-take-classes-from-and-why |
| 3 | MyProfReviews | Anonymous reviews of Professors | https://www.myprofreviews.com/r/2467-arizona-state-university-professor |
| 4 | RamblerTemple Blog | A guide for freshman for student housing at ASU | https://ramblertempe.com/resources/a-freshmans-guide-to-student-housing-at-arizona-state-university/ |
| 5 | ASU Online | Official page for online course tips | https://asuonline.asu.edu/newsroom/online-learning-tips/survive-finals-week/ |
| 6 | HeySunny Blog | Blog post on advice for surviving finals at ASU | https://heysunny.asu.edu/blog/finals-advice-you-can-actually-use |
| 7 | ASU News | Official news post on finals advice | https://news.asu.edu/20250414-sun-devil-community-tested-tips-taking-exams |
| 8 | Reddit | Post on overall ASU tips for freshman | https://www.reddit.com/r/ASU/comments/seracn/hey_devils_what_are_the_best_tips_youve_ever/ |
| 9 | ASU Online | Official post on freshman checklist | https://asuonline.asu.edu/newsroom/online-learning-tips/prepare-first-year-college-student-checklist/ |
| 10 | ASU Survival Guide | Blog post on survival guide for freshman | https://asusurvivalguide.weebly.com/ |
| 11 | Plexuss | Blog post on survival guide for getting into ASU | https://plexuss.com/n/arizona-state-university-survival-guide |

---

## Chunking Strategy

<!-- How will you split documents into chunks?
     State your chunk size (in tokens or characters), overlap size, and explain why those
     numbers fit the structure of your documents.
     A review-heavy corpus warrants different chunking than a long FAQ. -->

**Chunk size:**

- 200–600 chars, source-dependent

**Overlap:**

- 15–20% of chunk size per source

**Reasoning:**

- The sources span 4 distinct formats: atomic reviews, Q&A pairs, listicles, and unstructured prose. A single fixed chunk size would either split review opinions mid-thought or merge unrelated tips. Semantic-first splitting (paragraph to sentence to char fallback) preserves meaning boundaries. Overlap is skipped for review/comment sources because each unit is already self-contained; it's applied only to prose articles where context can bleed across section edges.

> **Per-source refinement (update 1):** The "200–600 chars" above is a
> summary range. The implemented chunker uses a per-source size/overlap table as authoritative.
> Review/comment sources (RateMyProfessors 50–200, MyProfReviews 100–200, Reddit 50–400)
> intentionally fall **below** the 200 floor: an atomic review is one self-contained thought and
> must not be padded or merged with another review just to clear a minimum. Long single reviews
> are likewise kept whole even if they exceed the per-source max (e.g. one MyProfReviews entry at
> ~395 chars) — boundary integrity beats hitting a size target. Prose sources keep the 15–20%
> overlap; review/comment sources use none.

**Per-source table (as implemented in `rag/sources.py`):**

| Source | Mode | Chunk boundary | Size (chars) | Overlap |
|--------|------|----------------|--------------|---------|
| RateMyProfessors | atomic | 1 review = 1 chunk | 50–200 | none |
| MyProfReviews | atomic | 1 professor entry = 1 chunk | 100–200 | none |
| Quora | atomic | 1 answer = 1 chunk | 100–600 | none |
| Reddit r/ASU | atomic | 1 top-level comment | 50–400 | none |
| ASU Online (finals tips) | prose | 1 numbered tip + body | 150–400 | ~40 |
| ASU Online (first-year checklist) | prose | 1 checklist item + body | 200–400 | ~40 |
| ASU News (Miceli Q&A) | prose | 1 Q+A pair | 300–600 | ~60 |
| Hey Sunny blog | prose | `##` section header | 400–700 | ~80 |
| Rambler Tempe housing guide | prose | section / header | 300–500 | ~60 |
| Plexuss survival guide | prose | section / topic paragraph | 200–500 | ~50 |
| Weebly (each sub-page) | prose | paragraph break | 200–500 | ~50 |

*Mode `atomic` = 1 unit per chunk, no overlap (reviews/comments); `prose` = recursive semantic
split packed into the size range with overlap.*

> **Weebly homepage decision (update 2):** The original plan was to treat the
> Weebly homepage as a table of contents and never chunk it (see Anticipated Challenge #1). On the
> live site, the finals-week "Stress Relief Stations" detail (eval Q4) exists **only** in the
> homepage blob — it is not on any sub-page. Excluding the homepage would make Q4 unanswerable, so
> the homepage is now **semantically chunked** like other prose (the 4,500-char blob is split into
> ~500-char pieces; tiny TOC nav fragments are dropped). This re-introduces the topic-mixing risk
> Anticipated Challenge #1 warns about — a price paid to keep the only copy of that content — and
> is exactly the kind of failure case a reranker (stretch) would help filter.

---

## Retrieval Approach

<!-- Which embedding model are you using (e.g., all-MiniLM-L6-v2 via sentence-transformers)?
     How many chunks will you retrieve per query (top-k)?
     If you were deploying this for real users and cost wasn't a constraint, what tradeoffs
     would you weigh in choosing a different embedding model — context length, multilingual
     support, accuracy on domain-specific text, latency? -->

**Embedding model:**

BAAI/bge-m3 via sentence-transformers

**Top-k:**

5 chunks per query

**Production tradeoff reflection:**

On top-k=5, this is meant to be a starting point, not a fixed rule. Because when I run the five test questions, and count how often the correct source appears in position 6 or 7, and then I can raise k if I'm consistently missing it. An additional reranking step (retrieve 20, rerank to 5) is a better direction for production than just increasing k raw, since it widens the net without flooding the LLM context with noise.

> **M4 retrieval smoke test (update 1):** With BGE-M3 + ChromaDB (dense, cosine) over the 150
> M3 chunks, **all 5 eval questions retrieved their expected source at rank 1** (scores 0.63–0.73)
> — see `scripts/eval_retrieval.py`. k=5 is comfortably adequate for this corpus; the correct
> chunk is never even near the position 6–7 boundary, so the reranker stretch is **not needed**
> for the MVP and stays deferred.

---

## Evaluation Plan

<!-- List your 5 test questions with their expected correct answers.
     Questions should be specific enough that you can judge whether the system's response
     is right or wrong. "What are good dining halls?" is too vague.
     "What do students say about wait times at [dining hall name] during lunch?" is testable. -->

| # | Question | Expected answer |
|---|----------|-----------------|
| 1 | How long should a single study session be for ASU finals before taking a break? | Two sources give slightly different but compatible numbers. The ASU Online article recommends studying for 25 minutes then taking a 5-minute active break, repeated 4 times before a longer 15–30 minute break — the Pomodoro Method. The Hey Sunny blog recommends 30-minute study chunks with breaks in between for a snack, water, or a quick stretch. |
| 2 | What makes William Martin a popular professor at ASU? | Students praise William Martin because of the passion he brings to his work, his easy grading, and his presence. He is noted for showing up on time, making his courses interesting, and being easy on the eye. |
| 3 | What transportation options does the ASU provide for getting between campuses? | There's a free intercampus shuttle running every 30 minutes between Tempe, Downtown Phoenix, and West Campuses; the Valley Metro light rail with discounted annual student passes; rentable bikes on campus; and multiple parking structures at each campus. |
| 4 | What are resources available at the ASU libraries specifically during finals week? | During finals week, ASU libraries offer "Stress Relief Stations" where students can get free food and reduce stress with puzzles, coloring books, and stress balls. |
| 5 | What are some common mistakes freshman students do on exams, and how can I avoid it? | Spending too much time making flashcards instead of practicing, and not realizing that struggling through practice questions reinforced material better than passive memorization. What really helps is focussing on timed practice, writing summaries from memory, and having the mindset that success is about how you study, not how much.

---

## Anticipated Challenges

<!-- What could go wrong? Name at least two specific risks with reasoning.
     Consider: noisy or inconsistent documents, missing source attribution, off-topic
     retrieval, chunks that split key information across boundaries. -->

1. The Weebly homepage is a noisy and inconsistent document, since the entire homepage is one unbroken paragraph mixing transportation, food, housing, tutoring, and finals stress relief with no headers. If you embed it as-is, a query about "stress relief during finals" might retrieve a chunk that's 80% about light rail transit, because all those topics share the same embedding neighborhood.

   > **Observed + resolved (update 1):** This challenge materialized. The "Stress Relief Stations"
   > detail (eval Q4) turned out to live **only** in this homepage blob, not in a sub-page as
   > originally assumed. Rather than embed the 4,500-char blob as one chunk, the implementation
   > runs it through the same semantic splitter (~500-char pieces) and drops the TOC nav fragments,
   > so the stress-relief sentence lands in its own retrievable chunk. The residual topic-mixing is
   > the motivating evidence for the reranker stretch feature.

2. Several of the sources share vocabulary without sharing topics, which could lead to Off-topic retrieval. The word "finals" appears in the Hey Sunny blog (study strategy), the Weebly guide (library stress relief), the ASU Online checklist (exam prep logistics), and the Toni Miceli interview (bar exam tips). A query about "finals tips" can retrieve chunks from all four simultaneously, and if there's no reranker to filter well, we'll get a bar exam preparation tip dropped into an answer meant for freshman.

---

## Architecture

<!-- Draw a diagram of your pipeline showing the five stages:
     Document Ingestion → Chunking → Embedding + Vector Store → Retrieval → Generation
     Label each stage with the tool or library you're using.
     You can use ASCII art, a Mermaid diagram, or embed a sketch as an image.
     You'll use this diagram as context when prompting AI tools to implement each stage. -->

![Architecture Diagram](./ASU%20Freshman%20Unofficial%20Guide-2026-06-07-165619.png)

---

## AI Tool Plan

<!-- For each part of the pipeline below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, which requirements)
     - What you expect it to produce
     - How you'll verify the output matches your spec

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Chunking Strategy section and ask it to implement chunk_text()
     with my specified chunk size and overlap" is a plan. -->

**Milestone 3 — Ingestion and chunking:**

Tool: Claude Code.

Input I'll give it:

- The Sources & Access Notes and Preprocessing sections (the accessible-vs-blocked list, the source_type mapping, and the special cases for Weebly/Rambler Blog/Quora/Reddit).
- The Chunking Strategy per-source table (boundary, size target, overlap per source).
- The Chunk metadata fields list.
- A note that blocked sources (RMP, Quora, Reddit) are manual exports living in documents/.

What to expect it to produce:

- An HTML cleaner (strip nav/footer/ads/boilerplate) that produces clean text per source.
- A chunk_text() (or per-source chunker dispatch) that does recursive semantic splitting from paragraph to sentence to char fallback and applies overlap only to prose sources, none to reviews/comments.
- A metadata tagger attaching all 9 fields (chunk_id, source_url, source_title, source_type, author, date, chunk_index, section_title) to every chunk.
- Special-case handling: Weebly fetched per sub-page (homepage = TOC only, never chunked), Quora question prepended to each answer, Reddit top-level comments only and short-comment grouping, Rambler Blog flagged commercial.

How to verify against spec:

- Print chunk-size distribution per source and confirm it lands in the table's target ranges. And confirm review sources have zero overlap.
- Assert no chunk originates from the Weebly homepage blob.
- Spot-check that the William Martin review is one intact chunk and the Miceli Q&A stays together.
- Assert every chunk has all 9 metadata fields populated (or explicit null) and a valid source_type.

**Milestone 4 — Embedding and retrieval:**

Tool: Claude Code.

Input I'll give it:

- The Embedding Model section (BGE-M3 via sentence-transformers, normalize_embeddings=True).
- The Decided Config (MVP) section that emphasizes ChromaDB, dense-only, no reranker for MVP. Hybrid and cross-encoder are stretch and would not be built yet.
- The Retrieval Approach top-k guidance (default k=5).
- The chunk objects and metadata schema from M3.

What to expect it to produce:

- An embedding step to load BAAI/bge-m3, encode all chunks normalized to dense vectors.
- A ChromaDB collection storing vectors + full metadata per chunk.
- A retrieve(query, k=5) doing dense cosine search and returning chunks with their metadata (so source_type/source_url flow downstream).

How to verify against spec:

- Confirm embedding dim = 1024 and that long chunks aren't silently truncated (BGE-M3's 8192 window relevant if ever fall back needed to all-MiniLM's 256).
- Run each of the 5 eval questions as a retrieval-only smoke test and check the expected source chunk appears in the top-k. This is also the data for the top-k tuning note. If the right chunk keeps landing at position 6–7, that's the evidence to raise k or prioritize the hybrid/reranker stretch.
- Verify retrieved objects carry source_type and source_url. Needed for grounding.

**Milestone 5 — Generation and interface:**

Tool: Claude Code.

Input I'll give it:

- The Generation section using GROQ (Groq LLM, GROQ_API_KEY in .env). **Model used: `llama-3.3-70b-versatile`** (one-line `MODEL` constant in `rag/generate.py`, temperature 0.2).
- The Source quality risk note and source_type semantics (official, editorial, user_opinion, Rambler Blog = commercial bias).
- The LLM prompt inputs spec: top-5 chunks with text, source_type, source_url, instruction to cite sources and signal confidence by source type.

Requirements note: UI via Gradio.

What to expect it to produce:

- A prompt builder that formats the top-k chunks with their source_type and source_url inline.
- A grounded system prompt that answer only from retrieved context, cite sources, and lower confidence / caveat for user_opinion and commercially-biased editorial sources; say "not found in sources" when context is insufficient.
- A Groq generation call and a minimal Gradio/Streamlit query box.

How to verify against spec:

- Run all 5 eval questions end-to-end and fill the Evaluation Report table in README.md; compare to expected answers.
- Grounding test to ask an off-domain question (e.g. "what's ASU's football schedule?") and confirm it refuses rather than hallucinating.
- Attribution test to confirm answers cite source_url and that a Rambler Blog-sourced answer flags the commercial stake.
- Shared-vocab test on how a "finals tips" query shouldn't pull bar-exam content into a freshman answer. If it does, that's the documented failure case for the README.
