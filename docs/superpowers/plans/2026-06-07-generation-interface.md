# M5 Generation & Interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn M4's retrieved chunks into grounded, source-cited answers via Groq (llama-3.3-70b-versatile), exposed through a Gradio query box, and verify with the 5 eval questions + grounding/attribution probes.

**Architecture:** One `rag/generate.py` module (pure `build_prompt` + `answer()` with an injectable Groq client), a `app.py` Gradio UI, and a `scripts/eval_generate.py` verification script. Unit tests mock the Groq client and stub retrieval so the suite makes no API calls; the real key only runs in the eval script.

**Tech Stack:** Python 3.9, `groq==0.15.0`, `gradio`, `python-dotenv`, `pytest`.

---

## File Structure

- `rag/generate.py` — `MODEL`, `SYSTEM_PROMPT`, `get_client()`, `build_prompt(query, hits)`, `answer(query, k, client)`.
- `app.py` — Gradio interface calling `answer()`.
- `scripts/eval_generate.py` — 5 eval questions + refusal + attribution probes.
- `tests/test_generate.py` — unit tests (mocked client, stubbed retrieve).
- `requirements.txt` — uncomment `gradio`.
- `.env` — user-created from `.env.example` (not committed).

---

### Task 1: Install M5 dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Uncomment gradio in `requirements.txt`**

Change the Milestone-5 UI block from commented to active — replace:

```
# Query interface — add whichever you use for Milestone 5:
# gradio>=6.9.0
# streamlit>=1.40.0
```

with:

```
# Query interface (Milestone 5):
gradio>=4.44.0
# streamlit>=1.40.0
```

(`groq==0.15.0` and `python-dotenv==1.0.1` are already pinned.)

- [ ] **Step 2: Install**

Run: `python3 -m pip install "groq==0.15.0" "gradio>=4.44.0"`
Expected: completes (gradio pulls a few deps); may take a minute.

- [ ] **Step 3: Verify imports**

Run: `python3 -c "import groq, gradio; print('groq', groq.__version__, '| gradio', gradio.__version__)"`
Expected: prints versions, no ImportError.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "Add M5 generation/UI dependencies (groq, gradio)"
```

---

### Task 2: Prompt builder (`rag/generate.py` — `build_prompt`)

**Files:**
- Create: `rag/generate.py`
- Test: `tests/test_generate.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_generate.py
from rag.generate import build_prompt, SYSTEM_PROMPT

def _hits():
    return [
        {"text": "Free intercampus shuttle every 30 min.", "source_type": "editorial",
         "source_url": "http://weebly", "source_id": "weebly", "commercial_bias": False},
        {"text": "Our apartments are the best near campus.", "source_type": "editorial",
         "source_url": "http://rambler", "source_id": "rambler_tempe", "commercial_bias": True},
    ]

def test_build_prompt_includes_text_type_url_and_question():
    system, user = build_prompt("How do I get between campuses?", _hits())
    assert system == SYSTEM_PROMPT
    assert "Free intercampus shuttle" in user
    assert "editorial" in user
    assert "http://weebly" in user
    assert "How do I get between campuses?" in user

def test_build_prompt_marks_commercial_bias():
    _, user = build_prompt("housing?", _hits())
    assert "http://rambler" in user
    # the biased source is flagged somehow in its block
    rambler_block = user.split("http://rambler")[0].rsplit("Source", 1)[-1] + user.split("http://rambler")[1].split("Source")[0]
    assert "commercial" in user.lower()

def test_system_prompt_states_three_rules():
    s = SYSTEM_PROMPT.lower()
    assert "couldn't find" in s or "could not find" in s   # rule 1 refusal phrase
    assert "cite" in s                                       # rule 2
    assert "user_opinion" in s and "commercial" in s         # rule 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_generate.py -q`
Expected: FAIL with "No module named 'rag.generate'".

- [ ] **Step 3: Write `rag/generate.py` (constants + build_prompt only)**

```python
# rag/generate.py
"""Groq-backed answer generation grounded in retrieved chunks."""
import os
from typing import List, Optional, Tuple

MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = (
    "You are an assistant helping Arizona State University (ASU) freshmen. "
    "Answer using ONLY the numbered sources provided in the user message.\n"
    "Rules:\n"
    "1. If the sources do not contain the answer, reply exactly: "
    "\"I couldn't find that in the sources.\" Do not use outside knowledge or guess.\n"
    "2. Cite the source_url(s) you used, inline or in a short 'Sources:' list.\n"
    "3. Signal lower confidence and add a brief caveat when your support comes from a "
    "user_opinion source (anonymous, unverified) or an editorial source flagged "
    "commercial (the author has a financial stake).\n"
    "Be concise and specific."
)


def _format_hit(i: int, hit: dict) -> str:
    bias = " | commercial-bias: yes" if hit.get("commercial_bias") else ""
    return (f"[Source {i}] source_type={hit.get('source_type')} "
            f"url={hit.get('source_url')}{bias}\n{hit.get('text', '')}")


def build_prompt(query: str, hits: List[dict]) -> Tuple[str, str]:
    """Return (system, user) messages grounding the answer in `hits`."""
    blocks = "\n\n".join(_format_hit(i + 1, h) for i, h in enumerate(hits))
    user = f"Sources:\n{blocks}\n\nQuestion: {query}"
    return SYSTEM_PROMPT, user
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_generate.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add rag/generate.py tests/test_generate.py
git commit -m "Add grounded prompt builder with source-type and bias tagging"
```

---

### Task 3: Answer function with injectable client (`rag/generate.py` — `answer`)

**Files:**
- Modify: `rag/generate.py`
- Test: `tests/test_generate.py`

- [ ] **Step 1: Write the failing test (append to tests/test_generate.py)**

```python
# append to tests/test_generate.py
from unittest.mock import MagicMock
import rag.generate as gen

def test_answer_uses_retrieved_sources_and_client(monkeypatch):
    fake_hits = [{"text": "Shuttle every 30 min.", "source_type": "editorial",
                  "source_url": "http://weebly", "source_id": "weebly", "commercial_bias": False}]
    monkeypatch.setattr(gen, "retrieve", lambda q, k=5: fake_hits)

    # fake Groq client: client.chat.completions.create(...).choices[0].message.content
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="Take the free shuttle. Sources: http://weebly"))
    ]

    out = gen.answer("how to get between campuses?", k=5, client=fake_client)
    assert out["answer"].startswith("Take the free shuttle")
    assert out["sources"] == fake_hits
    # the client was called with our model and a 2-message prompt
    kwargs = fake_client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == gen.MODEL
    assert kwargs["messages"][0]["role"] == "system"
    assert kwargs["messages"][1]["role"] == "user"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_generate.py::test_answer_uses_retrieved_sources_and_client -q`
Expected: FAIL (`answer` / `retrieve` not defined in module).

- [ ] **Step 3: Extend `rag/generate.py`**

Add the import and functions (append after `build_prompt`):

```python
from rag.retrieve import retrieve

_client = None


def get_client():
    """Lazy Groq client; reads GROQ_API_KEY from environment / .env."""
    global _client
    if _client is None:
        from dotenv import load_dotenv
        load_dotenv()
        from groq import Groq
        key = os.environ.get("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY not set — copy .env.example to .env and add your key.")
        _client = Groq(api_key=key)
    return _client


def answer(query: str, k: int = 5, client=None) -> dict:
    """Retrieve k chunks, build a grounded prompt, and generate a cited answer."""
    hits = retrieve(query, k=k)
    system, user = build_prompt(query, hits)
    client = client or get_client()
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=0.2,
    )
    return {"answer": resp.choices[0].message.content, "sources": hits}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_generate.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add rag/generate.py tests/test_generate.py
git commit -m "Add answer() wiring retrieve -> prompt -> Groq (injectable client)"
```

---

### Task 4: Gradio app (`app.py`)

**Files:**
- Create: `app.py`

- [ ] **Step 1: Write `app.py`**

```python
# app.py
"""Gradio UI for the ASU Freshman Unofficial Guide RAG.

Usage: python3 app.py   (needs GROQ_API_KEY in .env and a built index: scripts.build_index)
"""
import gradio as gr
from rag.generate import answer


def _respond(query: str):
    if not query or not query.strip():
        return "Ask a question about thriving at ASU as a freshman.", ""
    out = answer(query.strip(), k=5)
    seen = []
    for h in out["sources"]:
        line = f"- [{h.get('source_type')}] {h.get('source_url')}"
        if line not in seen:
            seen.append(line)
    return out["answer"], "\n".join(seen)


with gr.Blocks(title="ASU Freshman Unofficial Guide") as demo:
    gr.Markdown("# ASU Freshman Unofficial Guide\nAsk about studying, housing, transport, professors, finals.")
    q = gr.Textbox(label="Your question", placeholder="How long should I study before a break?")
    btn = gr.Button("Ask")
    ans = gr.Markdown(label="Answer")
    srcs = gr.Markdown(label="Sources")
    btn.click(_respond, inputs=q, outputs=[ans, srcs])
    q.submit(_respond, inputs=q, outputs=[ans, srcs])


if __name__ == "__main__":
    demo.launch()
```

- [ ] **Step 2: Import-smoke the app (no launch)**

Run: `python3 -c "import app; print('app import ok')"`
Expected: prints `app import ok` (importing defines the Blocks but does not launch).

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "Add Gradio query interface"
```

---

### Task 5: End-to-end verification script (`scripts/eval_generate.py`)

**Files:**
- Create: `scripts/eval_generate.py`

- [ ] **Step 1: Write `scripts/eval_generate.py`**

```python
# scripts/eval_generate.py
"""End-to-end generation eval: 5 questions + a refusal probe + an attribution probe.

Usage: python3 -m scripts.eval_generate   (needs GROQ_API_KEY in .env + built index)
"""
from rag.generate import answer

EVAL = [
    "How long should a single study session be before a break?",
    "What makes William Martin a popular professor?",
    "What transportation options does ASU provide between campuses?",
    "What resources are at ASU libraries during finals week?",
    "What common mistakes do students make on exams and how can I avoid them?",
]
REFUSAL_PROBE = "What is ASU's football schedule this season?"
ATTRIBUTION_PROBE = "What should I know about freshman housing near ASU?"


def _show(q):
    out = answer(q, k=5)
    urls = sorted({h.get("source_url") for h in out["sources"]})
    print(f"\nQ: {q}\nA: {out['answer']}\n   sources: {urls}")


def main():
    print("=== 5 eval questions ===")
    for q in EVAL:
        _show(q)
    print("\n=== refusal probe (off-domain — expect a 'not in sources' style answer) ===")
    _show(REFUSAL_PROBE)
    print("\n=== attribution probe (housing — expect a commercial-bias caveat if Rambler is used) ===")
    _show(ATTRIBUTION_PROBE)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Ensure `.env` exists with a real key**

Check: `python3 -c "from dotenv import load_dotenv; load_dotenv(); import os; print('key set:', bool(os.environ.get('GROQ_API_KEY')))"`
Expected: `key set: True`. If False, copy `.env.example` to `.env` and add the real `GROQ_API_KEY` before running Step 3.

- [ ] **Step 3: Run end-to-end (needs the M4 index built)**

Run: `python3 -m scripts.build_index` (if `chroma_db/` not present), then `python3 -m scripts.eval_generate`
Expected: 5 answers consistent with planning.md's expected answers; the football question is refused ("I couldn't find that in the sources."); the housing answer flags Rambler's commercial stake if it cites Rambler.

- [ ] **Step 4: Commit**

```bash
git add scripts/eval_generate.py
git commit -m "Add end-to-end generation eval (5 questions + refusal + attribution probes)"
```

---

### Task 6: Full suite + README evaluation report

**Files:**
- Modify: `README.md` (Evaluation Report — if the template has one) or `planning.md`

- [ ] **Step 1: Run the full unit suite**

Run: `python3 -m pytest -q`
Expected: all M3 + M4 + M5 unit tests PASS (no API calls — Groq mocked, retrieve stubbed).

- [ ] **Step 2: Record the end-to-end results**

In `README.md` (if it has an Evaluation/AI-usage section) or appended to `planning.md`'s
Evaluation Plan, note the M5 outcome using the actual `eval_generate` output, e.g.:

```markdown
**M5 end-to-end (2026-06-07, llama-3.3-70b-versatile):** All 5 eval questions answered
correctly with cited source_urls. Off-domain "football schedule" question correctly refused.
Housing answer flagged Rambler Tempe's commercial bias. [Adjust to actual observed output.]
```

- [ ] **Step 3: Commit**

```bash
git add README.md planning.md
git commit -m "Record M5 end-to-end evaluation results"
```

---

## Self-Review notes

- **Spec coverage:** build_prompt with source_type+url+bias (T2) · three grounding rules in SYSTEM_PROMPT (T2) · answer() returns {answer, sources} with injectable client (T3) · Groq llama-3.3-70b + GROQ_API_KEY via dotenv (T3) · Gradio UI showing answer + sources (T4) · eval 5 questions + refusal + attribution probes (T5) · mocked-client unit tests (T2/T3) · install deps (T1) · record results (T6). All covered.
- **Type consistency:** `build_prompt(query, hits) -> (system, user)`, `answer(query, k=5, client=None) -> {"answer","sources"}`, `get_client()`, `MODEL`, `SYSTEM_PROMPT`, `retrieve(query, k)` (from M4) used consistently. The unit test monkeypatches `rag.generate.retrieve`, so `answer` must call the module-level `retrieve` name (imported via `from rag.retrieve import retrieve`).
- **Secrets:** `.env` is gitignored (never committed); only `.env.example` is in the repo.
- **Note:** the `test_build_prompt_marks_commercial_bias` assertion is simplified to check `"commercial" in user.lower()`; the intermediate `rambler_block` slicing line is illustrative only — keep just the `assert "commercial" in user.lower()` and the URL assertion.
```
