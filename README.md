# The Unofficial Guide — Project 1

> A retrieval-augmented (RAG) question-answering system over scattered, unofficial web sources
> about **thriving at Arizona State University (ASU) as a freshman**. Web sources → preprocessing →
> chunking → BGE-M3 embeddings → ChromaDB → dense retrieval → Groq (llama-3.3-70b-versatile)
> grounded answer with cited sources.

---

## Domain

This system answers questions about **what it's actually like to be a freshman at ASU** — study
and finals strategy, professor reputations, getting between campuses, housing, and library
resources. ASU is the largest US university by intake, but the genuinely useful "how do I survive
here" knowledge is scattered across student blogs, forums, anonymous review sites, and a Weebly
survival guide rather than official `.edu` catalog pages.

That knowledge is valuable because official channels describe *programs and policies*, not lived
experience — a course catalog won't tell you a professor "shows up on time and makes the course
interesting," or that the library runs "Stress Relief Stations" during finals. It's hard to find
because it's spread thin across many low-authority sources, mixed in with marketing (an apartment
complex's housing guide) and anonymous opinion (review sites, Reddit), with no single trustworthy
index. A RAG system that pulls these together — while tracking each source's trustworthiness — is
exactly the right tool.

---

## Document Sources

Sources span four formats — anonymous reviews, Q&A threads, official listicles, and unstructured
prose guides — and three trust tiers (`official`, `editorial`, `user_opinion`).

| # | Source | Type | URL or file path | Ingested? |
|---|--------|------|------------------|-----------|
| 1 | RateMyProfessors | user_opinion | https://www.ratemyprofessors.com/search/professors/15723 | ⛔ robots-blocked (needs manual export) |
| 2 | Quora — ASU professor recs | user_opinion | https://www.quora.com/Which-professors-at-Arizona-State-University-would-you-recommend... | ⛔ robots-blocked (needs manual export) |
| 3 | MyProfReviews | editorial | https://www.myprofreviews.com/r/2467-arizona-state-university-professor | ✅ live fetch |
| 4 | Rambler Tempe (housing) | editorial (commercial bias) | https://ramblertempe.com/resources/a-freshmans-guide-to-student-housing-at-arizona-state-university/ | ✅ live fetch |
| 5 | ASU Online — survive finals | official | https://asuonline.asu.edu/newsroom/online-learning-tips/survive-finals-week/ | ✅ live fetch |
| 6 | Hey Sunny — finals advice | official | https://heysunny.asu.edu/blog/finals-advice-you-can-actually-use | ✅ live fetch |
| 7 | ASU News — exam tips (Miceli) | official | https://news.asu.edu/20250414-sun-devil-community-tested-tips-taking-exams | ✅ live fetch |
| 8 | Reddit r/ASU — tips thread | user_opinion | https://www.reddit.com/r/ASU/comments/seracn/ | ⛔ blocked (needs Reddit API / export) |
| 9 | ASU Online — first-year checklist | official | https://asuonline.asu.edu/newsroom/online-learning-tips/prepare-first-year-college-student-checklist/ | ✅ live fetch |
| 10 | ASU Survival Guide (Weebly) | editorial | https://asusurvivalguide.weebly.com/ (homepage + 4 sub-pages) | ✅ live fetch |
| 11 | Plexuss — survival guide | editorial | https://plexuss.com/n/arizona-state-university-survival-guide | ⚠️ thin (JS-rendered) |

**8 of 11 sources** were ingested (**150 chunks**). The 3 blocked sources are robots-disallowed and
gracefully skipped until a manual export is dropped in `documents/exports/`; none of the 5 eval
questions depend on them. Plexuss is client-side rendered, so the static fetch yielded only ~2
chunks (flagged by the pipeline's thin-content warning).

---

## Chunking Strategy

**Chunk size:** Source-dependent, **50–700 characters**, set per source rather than one global size
(see the per-source table in [CLAUDE.md](CLAUDE.md)). Examples: a RateMyProfessors review is 50–200
chars (1 review = 1 chunk); a Hey Sunny blog section is 400–700; the ASU News Q&A is 300–600 (1 Q+A
pair = 1 chunk).

**Overlap:** **15–20% of chunk size, applied only to prose articles** (e.g. ~80 chars for Hey Sunny,
~40 for ASU Online tips). Review/comment sources use **no overlap** — each review or comment is
already a self-contained thought, so overlap would only duplicate opinions across chunks.

**Why these choices fit the documents:** The corpus mixes atomic reviews, Q&A pairs, listicles, and
long prose. A single fixed size would either split a review opinion mid-thought or merge unrelated
tips into one diluted chunk. So chunking is **recursive and semantic** — split on paragraph → line →
sentence → character — and **boundary-aware per source**: reviews and Q&A pairs are kept intact as
single units, while prose is packed into the source's size range with overlap. Preprocessing before
chunking: fetch each page (saving a raw HTML snapshot for reproducibility), strip non-content with
BeautifulSoup (nav, footer, scripts, ads, share/cookie banners, "Read more" links), decode HTML
entities, and fix `requests`' UTF-8 mis-decoding. Source-specific handling: the Weebly homepage is
semantically chunked with its table-of-contents nav fragments dropped; each MyProfReviews professor
name is paired with its review so the name stays as context; Quora answers are prefixed with the
question; Reddit keeps only top-level comments.

**Final chunk count:** **150 chunks** across the 8 ingested sources.

---

## Sample Chunks

Five representative chunks (text verbatim from `data/chunks.jsonl`), each labeled with its source
document. Review sources are kept as one atomic unit with **no overlap**; prose sources are packed to
their size range **with overlap** — which is why some prose chunks begin mid-word (the leading
fragment is the ~15–20% tail carried over from the previous chunk, marked with `…`).

1. **MyProfReviews** (`editorial`, atomic — 1 review = 1 chunk, no overlap) · `myprofreviews::4` (319 chars):
   > 2. William Martin — William martin is an interesting English professor at Arizona State and many students love him because of the passion he enthuses in what he does, easy marks and presence. He is one of the few professors who show up on time and make their courses interesting. Besides, he is easy on the eye as well.

2. **ASU Online — Survive Finals Week** (`official`, prose, ~40-char overlap) · `asuonline_finals::3` (431 chars):
   > …It's simple: Study for 25 minutes, then take a 5-minute active break—like walking the dog, shooting hoops or practicing yoga. Light physical activity boosts focus and reduces stress. Repeat this 4 times, then take a longer 15- to 30-minute break to stay sharp. 2. Mix up your study techniques. Avoid passive techniques such as rereading notes or highlighting.

3. **Hey Sunny — Finals Advice** (`official`, prose, ~80-char overlap) · `heysunny::4` (658 chars):
   > …you shouldn't expect your brain to be able to study and retain information for hours without breaks. I found studying in smaller increments (I started with 30-minute chunks) with breaks in between for a snack, water, or a quick stretch…

4. **ASU Survival Guide (Weebly)** (`editorial`, homepage section, prose) · `weebly-homepage::11` (377 chars):
   > …During finals week, the ASU libraries are even offering extra support in the form of "Stress Relief Stations", where students can grab a bit of free food, and reduce stress with puzzles, coloring books, and stress balls.

5. **Rambler Tempe — Freshman Housing Guide** (`editorial`, commercial-bias flagged, prose) · `rambler_tempe::5` (488 chars):
   > …On-Campus Residence Halls: On-campus dorms are a common choice for ASU students. These are owned and operated by the university and offer several floor plan options, including double (shared) rooms with community bathrooms (the most popular layout), double rooms with a connected bathroom, triple rooms and single rooms…

---

## Embedding Model

**Model used:** **`BAAI/bge-m3`** via `sentence-transformers` — 1024-dimensional dense embeddings,
L2-normalized, stored in a persistent ChromaDB collection with cosine similarity. Queries are
embedded with the same model and retrieved with top-k = 5.

**Production tradeoff reflection:** BGE-M3 was the spec's primary choice for its 8,192-token context
window and strong retrieval accuracy, and it works well here. But an honest note from the build: our
chunks max out at ~180 tokens, so BGE-M3's long-context advantage is unused on *this* corpus —
`all-MiniLM-L6-v2` (≈80 MB vs 1.2 GB, much faster on CPU) would have retrieved these short chunks
just as well, and its only real weakness (256-token truncation) never triggers here. For a real
deployment with no cost constraint I'd weigh: **context length** (longer chunks or full documents
would justify BGE-M3 or an API model with a big window); **latency** (BGE-M3 at 1.2 GB is slow on
CPU — a hosted API like OpenAI `text-embedding-3-large` or Voyage `voyage-3-large` would cut tail
latency and remove local memory pressure); **domain accuracy** (fine-tuning on 50–200 labeled ASU
query–chunk pairs could beat any general model on this niche vocabulary); and **multilingual**
(not needed now — all sources are English — but BGE-M3 covers it if that changed).

---

## Retrieval Test Results

Three queries run through `retrieve(query, k=3)` (BGE-M3 dense vectors, ChromaDB cosine; `score = 1 −
cosine distance`). Reproduce with `python3 -m scripts.eval_retrieval` (k=5) or the retriever directly.

**Query 1 — "How long should I study before taking a break?"**

| Rank | Source | Score | Chunk (excerpt) |
|------|--------|-------|-----------------|
| 1 | Hey Sunny | 0.686 | "…I started with 30-minute chunks) with breaks in between…" |
| 2 | ASU Online (finals) | 0.639 | "…Study for 25 minutes, then take a 5-minute active break…" |
| 3 | ASU News (Miceli) | 0.625 | "…Many spend hours passively reviewing notes, but that's not how…" |

*Why these are relevant:* The two highest-scoring chunks are exactly the two sources that answer the
question with concrete numbers — Hey Sunny's **30-minute** chunks and ASU Online's **25-minute**
Pomodoro — so the retriever surfaced *both* compatible answers rather than just one. Rank 3 is
adjacent finals-study advice (active vs. passive review): same topic, correctly scored lower.

**Query 2 — "Which professor should I take and why?"**

| Rank | Source | Score | Chunk (excerpt) |
|------|--------|-------|-----------------|
| 1 | MyProfReviews | 0.596 | "Before signing up for classes every student should gather as much information as possible…" |
| 2 | MyProfReviews | 0.593 | "Visit all pages and get all the information you need to choose the best class and best professor…" |
| 3 | MyProfReviews | 0.582 | "7. Nancy Sirianni — She is a great marketing professor…" |

*Why these are relevant:* All three hits come from MyProfReviews — the only source about *choosing
professors*. The retriever concentrated on the single intent-matching source instead of pulling
finals/housing chunks that share generic campus vocabulary, and it returned both the guide's framing
(#1–2) and a concrete named review (#3, Nancy Sirianni).

**Query 3 — "How do I get around between ASU campuses?"**

| Rank | Source | Score | Chunk (excerpt) |
|------|--------|-------|-----------------|
| 1 | Weebly | 0.733 | "…transportation. Getting around the downtown campus and to other ASU campuses…" |
| 2 | Weebly | 0.694 | "Getting Around… There are a variety of transportation options for students…" |
| 3 | Weebly | 0.665 | "…between Tempe, Downtown Phoenix and West Campuses… Valley Metro light rail offers discounted annual student passes…" |

---

## Grounded Generation

**System prompt grounding instruction:** The model is told to answer **using only the numbered
sources** in the user message, with three explicit rules: (1) *"If the sources do not contain the
answer, reply exactly: 'I couldn't find that in the sources.' Do not use outside knowledge or
guess."* (2) Cite the `source_url`(s) used. (3) Lower confidence and add a caveat when support comes
from a `user_opinion` source (anonymous, unverified) or an editorial source flagged commercial
(financial stake). Temperature is 0.2 to keep answers tight and faithful.

**Structural choices that enforce grounding:** Retrieval is the only context the model ever sees —
`answer()` runs `retrieve(query, k=5)` and formats each chunk into a numbered block tagged with its
`source_type`, `source_url`, and a `commercial-bias: yes` marker, then passes those blocks as the
user message. Because trust metadata is *in the prompt*, the model can act on it — e.g. it appends
*"the source has a commercial bias"* when answering a housing question from Rambler Tempe.

**How source attribution is surfaced:** Answers cite the `source_url`s inline / in a short "Sources:"
list, and the Gradio UI renders a separate **Sources** panel listing each cited URL with its
`source_type`. Off-domain questions (e.g. "ASU's football schedule") are refused rather than
answered from outside knowledge.

---

## Example Responses

Two grounded answers with **source attribution visible in the output text**, plus one out-of-scope
query showing refusal. Taken verbatim from `python3 -m scripts.eval_generate`.

**Example 1 — professor question (inline citation):**

> **Q:** What makes William Martin a popular professor?
>
> **A:** According to Source 1 (https://www.myprofreviews.com/r/2467-arizona-state-university-professor),
> William Martin is a popular professor because of the passion he enthuses in what he does, he gives
> easy marks, and has a strong presence. He also shows up on time and makes his courses interesting.
> Sources: 1. https://www.myprofreviews.com/r/2467-arizona-state-university-professor

**Example 2 — housing question (citation + commercial-bias caveat):**

> **Q:** What should I know about freshman housing near ASU?
>
> **A:** …there are several options available, including on-campus residence halls, private dorms, and
> off-campus student apartments (https://ramblertempe.com/resources/a-freshmans-guide-to-student-housing-at-arizona-state-university/).
> **Please note that the source has a commercial bias.** …Only about 24% of ASU students live in
> university-owned housing, so be prepared to consider off-campus options as well.

**Out-of-scope query (refusal):**

> **Q:** What is ASU's football schedule this season?
>
> **A:** I couldn't find that in the sources.

---

## Query Interface

A Gradio web app (`app.py`), launched with `python3 app.py` (needs `GROQ_API_KEY` in `.env` and a
built index from `python3 -m scripts.build_index`).

**Input field:**
- *Your question* — a single free-text textbox for a question about ASU freshman life (submit by
  clicking **Ask** or pressing Enter).

**Output fields:**
- *Answer* — a Markdown panel with the grounded, cited answer text.
- *Sources* — a Markdown panel listing the deduplicated chunks the answer was grounded on, each as
  `[source_type] source_url`.

**Sample interaction transcript (one complete query → response):**

> **Your question:** What transportation options does ASU provide between campuses?
>
> **Answer:** ASU provides the following transportation options between campuses: (1) free
> intercampus shuttles that run every 30 minutes; (2) the Valley Metro light rail with discounted
> annual student passes; (3) bikes that can be rented on campus; and (4) multiple parking structures
> at each campus. (Source: https://asusurvivalguide.weebly.com/)
>
> **Sources:**
> - [editorial] https://asusurvivalguide.weebly.com/

---

## Evaluation Report

<!-- Results from `python3 -m scripts.eval_generate` (BGE-M3 + ChromaDB retrieval,
     Groq llama-3.3-70b-versatile), 2026-06-07. Retrieval-only smoke test:
     `python3 -m scripts.eval_retrieval` returned the expected source at rank 1 for all 5. -->

| # | Question | Expected answer | System response (summarized) | Retrieval quality | Response accuracy |
|---|----------|-----------------|------------------------------|-------------------|-------------------|
| 1 | How long should a study session be before a break? | 25 min (ASU Online Pomodoro) **and** 30 min (Hey Sunny) | Gave **both**: 25-min study / 5-min break (ASU Online) and 30-min chunks (Hey Sunny), each cited | Relevant | Accurate |
| 2 | What makes William Martin a popular professor? | Passion, easy grading, presence, shows up on time, makes courses interesting | Passion, easy marks, presence, shows up on time, interesting — cited MyProfReviews | Relevant | Accurate |
| 3 | What transportation options between campuses? | Free intercampus shuttle, Valley Metro light rail, rentable bikes, parking structures | All four listed (shuttle every 30 min, light rail w/ student passes, bikes, parking) — cited Weebly | Relevant | Accurate |
| 4 | What library resources during finals week? | "Stress Relief Stations": free food, puzzles, coloring books, stress balls | Exactly that — cited Weebly | Relevant | Accurate |
| 5 | What common exam mistakes and how to avoid them? | Too much time on passive flashcards; fix = timed practice + writing summaries from memory | Correct direction (passive review vs. active learning, practice questions, spacing) but **more generic** than the specific flashcard/bar-exam anecdote in the source — cited ASU News | Relevant | Partially accurate |

**Retrieval quality:** Relevant / Partially relevant / Off-target  
**Response accuracy:** Accurate / Partially accurate / Inaccurate

**Grounding & attribution probes (beyond the 5 questions):**
- *Off-domain refusal:* "What is ASU's football schedule this season?" → **"I couldn't find that in the sources."** (correctly refused rather than hallucinating).
- *Commercial-bias attribution:* "What should I know about freshman housing near ASU?" → answered from Rambler Tempe **and explicitly flagged** "the source has a commercial bias."

---

## Failure Case Analysis

**Question that failed:** #5 — "What common mistakes do students make on exams, and how can I avoid
them?"

**What the system returned:** A correct-but-generic answer — passive review vs. active learning,
practice questions, spacing study sessions — citing ASU News. It missed the source's *specific*
anecdote: that the interviewee wasted time making flashcards for the California bar exam, and that
what actually worked was timed practice and writing summaries/essays from memory.

**Root cause (tied to a specific pipeline stage):** This is a **generation-stage dilution**, set up
by the **shared-vocabulary retrieval** risk noted in planning.md (Anticipated Challenge #2). The
specific Miceli chunk *was* retrieved at rank 1, so retrieval wasn't the problem. But the word
"exam/finals" appears across several sources, so the top-5 also pulled generic finals-tips chunks
(ASU Online, Hey Sunny). Given five chunks that mostly say "study actively," the 70B model
synthesized toward that common denominator and dropped the distinctive flashcard/bar-exam specifics
as an outlier.

**What I would change to fix it:** Add the planned **cross-encoder reranker** (stretch) so the most
on-topic chunk dominates the context instead of being one of five near-equal voices; and/or sharpen
the system prompt to *"preserve concrete specifics and examples from the sources, not just the
general advice."* Lowering k for narrow questions would also reduce the diluting chunks.

---

## Spec Reflection

> *(Draft from the build history — review and put in your own voice before submitting.)*

**One way the spec helped you during implementation:** planning.md's per-source chunking table and
its five concrete eval questions turned vague intentions into testable targets. Because the spec said
exactly which boundary and size each source should use, and exactly what answer each question should
return, the chunker could be built and then *verified* against the spec — printing the per-source
size distribution and asserting that each eval answer survived as one intact chunk (the William
Martin review, the Miceli Q&A) — instead of eyeballing output and hoping. The eval questions also
became the M4 retrieval smoke test and the M5 end-to-end test, so the spec drove verification across
three milestones.

**One way your implementation diverged from the spec, and why:** The spec said to treat the Weebly
homepage as a table of contents and **never chunk it** (it's one noisy multi-topic blob). But on the
live site, the finals-week "Stress Relief Stations" detail that eval Q4 expects exists **only** on
that homepage — not on any sub-page. Skipping it would have made Q4 unanswerable, so the homepage is
now **semantically chunked** (split into ~500-char pieces with the nav fragments dropped). This
reintroduces the topic-mixing risk the spec warned about, which is documented in planning.md's
Anticipated Challenge #1 as an observed, accepted tradeoff.

---

## AI Usage

> *(Draft from the real build history captured in CLAUDE.md's "AI Usage — Override Log" — review,
> confirm, and reword in your own voice before submitting.)*

**Instance 1 — chunk-size policy**

- *What I gave the AI:* planning.md's Chunking Strategy section and the per-source size table, asking
  it to implement the chunker.
- *What it produced:* A per-source recursive chunker that honored the size targets.
- *What I changed or overrode:* I directed it to let review sources fall **below** planning's flat
  "200–600 char" floor (RateMyProfessors 50–200) and to keep an over-long single review whole even
  when it exceeds the per-source max — because an atomic review is one self-contained thought and
  must not be padded or split to hit a number. I had planning.md updated to record why.

**Instance 2 — HTML cleaning robustness**

- *What I gave the AI:* The preprocessing requirements (strip nav/footer/ads/boilerplate) and the
  list of sources to clean.
- *What it produced:* A first cleaner that blanket-removed `<form>` tags and matched boilerplate
  class names by substring.
- *What I changed or overrode:* That cleaner silently erased entire pages — all of MyProfReviews
  (whose whole body is one ASP.NET `<form>`) and the Weebly content (whose container
  `id="wsite-content" class="wsite-not-footer"` matched the substring "footer"). I directed the fix:
  **keep `<form>`**, and switch class matching to **sub-tokens with a negation guard** so
  "not-footer" is spared. I also caught that `requests` was decoding pages as ISO-8859-1 and mangling
  punctuation, and had it forced to UTF-8. These overrides are logged in CLAUDE.md.
