# Design: Milestone 5 — Generation & Interface

> ASU Freshman Unofficial Guide RAG pipeline. Covers M5 (generation + UI) — the final milestone.
> Canonical project context: [CLAUDE.md](../../../CLAUDE.md) · spec: [planning.md](../../../planning.md).
> Builds on M4 `retrieve(query, k=5)`. Status: approved 2026-06-07.

## Goal

Turn retrieved chunks into a grounded, source-cited answer via Groq, exposed through a Gradio
query box. Answers cite `source_url`, flag lower confidence for `user_opinion` / commercially
biased sources, and refuse off-domain questions. Verify with the 5 eval questions plus grounding
and attribution checks.

## Decisions (resolved with user, 2026-06-07)

1. **Run end-to-end this session** — user adds `.env` with a real `GROQ_API_KEY`; we then run the
   full RAG over the 5 eval questions.
2. **Model: `llama-3.3-70b-versatile`** on Groq (one-line `MODEL` constant; easy to change).
3. **Interface: Gradio** (per planning.md), `app.py`. A separate `scripts/eval_generate.py` runs
   the verification suite without a browser.
4. **`answer()` returns both** the answer text and the source list it was grounded on, so the UI
   and eval can render citations.
5. Groq **client is injectable** so unit tests mock it (no API calls in the test suite) — same
   pattern as the M4 fake embedder.

## Environment notes (from probe)

- `groq` + `gradio` not installed → `pip install`. `python-dotenv` already present.
- No `.env` yet; `GROQ_API_KEY` unset. The verification step is gated on the user adding it.

## Data flow

```
query
  │ retrieve(k=5)                      (M4)
  ▼
top-5 chunks (text + source_type + source_url + commercial_bias)
  │ build_prompt -> (system, user)
  ▼
Groq chat completion (llama-3.3-70b-versatile, temperature ~0.2)
  ▼
{ answer: str, sources: [hit, ...] }   -> Gradio UI / eval script
```

## Modules

- `rag/generate.py`
  - `MODEL = "llama-3.3-70b-versatile"`; `get_client()` loads `GROQ_API_KEY` via `python-dotenv`
    and returns a `groq.Groq` client (lazy).
  - `build_prompt(query, hits) -> (system, user)`: pure function. System prompt encodes the three
    grounding rules; user message interleaves each hit as a context block tagged with its
    `source_type` and `source_url` (and a `commercial_bias` note), followed by the question.
  - `answer(query, k=5, client=None) -> {"answer": str, "sources": list[dict]}`: retrieve →
    build_prompt → `client.chat.completions.create(...)` → return text + the hits used. `client`
    injectable for tests.
- `app.py`: Gradio `Interface`/`Blocks` — a textbox and a submit; renders the answer and a
  "Sources" section listing each cited `source_url` with its `source_type`.
- `scripts/eval_generate.py`: runs the 5 eval questions end-to-end (prints answer + sources), an
  off-domain refusal probe ("What is ASU's football schedule?"), and an attribution probe (a
  housing question that pulls Rambler Tempe → answer should flag the commercial stake).

## Grounding rules (system prompt)

1. Answer **only** from the provided sources; if they don't contain the answer, say
   "I couldn't find that in the sources." (no outside knowledge, no fabrication).
2. **Cite** the `source_url`(s) used in the answer.
3. **Lower confidence / add a caveat** when support comes from a `user_opinion` source
   (anonymous, unverified) or an editorial source with `commercial_bias` (financial stake).
Keep answers concise.

## Testing

- **Unit (no API):**
  - `build_prompt` output contains every hit's text, its `source_type` and `source_url`, the
    question, and all three rules; commercial-bias hits are marked.
  - `answer()` with a **mocked Groq client** (fake `chat.completions.create`) returns the mocked
    text and the retrieved sources; verifies retrieve→prompt→client wiring. Retrieval is stubbed
    so the unit test needs no ChromaDB/model.
- **Integration (real key, `scripts/eval_generate.py`):** 5 eval answers match expected content;
  off-domain question is refused; Rambler-sourced answer flags commercial bias.

## Out of scope

- Stretch: hybrid (BM25) retrieval, cross-encoder reranker, conversation history/multi-turn.
