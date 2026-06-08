# M3 Ingestion & Chunking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fetch the ASU freshman web sources, save reproducible raw snapshots, clean them to substantive content, and chunk them per the CLAUDE.md per-source size/overlap table into `data/chunks.jsonl` with 9 metadata fields each.

**Architecture:** A lean `rag/` package, one module per stage (sources registry → fetch → clean → preprocess → chunk → metadata → ingest orchestrator). Raw text is snapshotted to `documents/raw/` between fetch and clean so the pipeline is reproducible offline. Pure-logic modules (clean, chunking, preprocess, metadata) are built test-first; fetch is tested against saved HTML fixtures.

**Tech Stack:** Python 3.9, `requests` (fetch), `beautifulsoup4` + `lxml` (clean), `pytest` (tests). No embeddings/LLM in this milestone.

---

## File Structure

- `requirements.txt` — add `requests`, `beautifulsoup4`, `lxml`, `pytest`.
- `rag/__init__.py` — package marker.
- `rag/sources.py` — `SOURCE_REGISTRY`, `Source` dataclass, `VALID_SOURCE_TYPES`.
- `rag/clean.py` — `html_to_text(html)`.
- `rag/chunking.py` — `recursive_split`, `merge_small`, `apply_overlap`, `chunk_text`, `group_short_units`.
- `rag/preprocess.py` — `prepare_units(source, text)` dispatch + Weebly/Quora/Reddit handlers.
- `rag/metadata.py` — `build_chunk`, `chunk_id`.
- `rag/fetch.py` — `fetch_source`, `load_raw`.
- `rag/ingest.py` — `ingest_all`, `verification_report`.
- `scripts/run_ingest.py` — CLI entry.
- `tests/` — `test_clean.py`, `test_chunking.py`, `test_preprocess.py`, `test_metadata.py`, `test_fetch.py`, `test_sources.py`, `fixtures/`.
- `documents/raw/`, `documents/exports/`, `data/` — runtime/output dirs (`.gitkeep`).

---

### Task 1: Project setup — deps, dirs, package skeleton

**Files:**
- Modify: `requirements.txt`
- Create: `rag/__init__.py`, `tests/__init__.py`, `documents/raw/.gitkeep`, `documents/exports/.gitkeep`, `data/.gitkeep`, `pytest.ini`

- [ ] **Step 1: Add dependencies to `requirements.txt`**

Append below the existing pinned deps (before the commented UI section):

```
# Ingestion & chunking (Milestone 3):
requests==2.32.3
beautifulsoup4==4.12.3
lxml==5.3.0
pytest==8.3.4
```

- [ ] **Step 2: Install**

Run: `python3 -m pip install requests beautifulsoup4 lxml pytest`
Expected: installs succeed; `python3 -c "import bs4, requests, lxml"` exits 0.

- [ ] **Step 3: Create package + dirs**

```bash
mkdir -p rag tests tests/fixtures documents/raw documents/exports data
touch rag/__init__.py tests/__init__.py
touch documents/raw/.gitkeep documents/exports/.gitkeep data/.gitkeep
```

- [ ] **Step 4: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
```

- [ ] **Step 5: Verify pytest runs (no tests yet)**

Run: `python3 -m pytest -q`
Expected: "no tests ran" (exit code 5 is fine).

- [ ] **Step 6: Commit**

```bash
git add requirements.txt rag tests documents data pytest.ini
git commit -m "Scaffold rag package, dirs, and M3 deps"
```

---

### Task 2: Sources registry (`rag/sources.py`)

**Files:**
- Create: `rag/sources.py`
- Test: `tests/test_sources.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sources.py
from rag.sources import SOURCE_REGISTRY, VALID_SOURCE_TYPES, Source

def test_registry_nonempty_and_unique_ids():
    ids = [s.id for s in SOURCE_REGISTRY]
    assert len(ids) == len(set(ids)), "source ids must be unique"
    assert len(SOURCE_REGISTRY) >= 8

def test_every_source_has_valid_type_and_required_fields():
    for s in SOURCE_REGISTRY:
        assert s.source_type in VALID_SOURCE_TYPES, s.id
        assert s.url and s.title
        assert s.fetch in {"live", "snapshot", "export"}
        assert s.mode in {"prose", "atomic"}
        assert s.size_min <= s.size_max
        # overlap only on prose
        if s.mode == "atomic":
            assert s.overlap == 0, s.id

def test_blocked_sources_use_export_strategy():
    by_id = {s.id: s for s in SOURCE_REGISTRY}
    for bid in ("ratemyprofessors", "quora", "reddit"):
        assert by_id[bid].fetch == "export"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_sources.py -q`
Expected: FAIL with "No module named 'rag.sources'".

- [ ] **Step 3: Write `rag/sources.py`**

```python
# rag/sources.py
"""Registry of project sources with per-source fetch + chunking parameters.

Chunk size/overlap follow CLAUDE.md's per-source Chunking Strategy table
(authoritative). `mode`: "atomic" = 1 unit (review/comment) -> 1 chunk, no overlap;
"prose" = recursive semantic split with overlap.
"""
from dataclasses import dataclass, field
from typing import Optional

VALID_SOURCE_TYPES = {"official", "editorial", "user_opinion"}


@dataclass(frozen=True)
class Source:
    id: str
    url: str
    title: str
    source_type: str          # official | editorial | user_opinion
    fetch: str                # live | snapshot | export
    mode: str                 # prose | atomic
    size_min: int
    size_max: int
    overlap: int = 0
    author: Optional[str] = None
    date: Optional[str] = None
    commercial_bias: bool = False
    weebly_subpages: tuple = field(default=())


SOURCE_REGISTRY = [
    Source("ratemyprofessors",
           "https://www.ratemyprofessors.com/search/professors/15723?q=*&did=11",
           "RateMyProfessors — ASU", "user_opinion", "export", "atomic", 50, 200),
    Source("quora",
           "https://www.quora.com/Which-professors-at-Arizona-State-University-would-you-recommend-that-people-take-classes-from-and-why",
           "Quora — ASU professor recommendations", "user_opinion", "export", "atomic", 100, 600),
    Source("myprofreviews",
           "https://www.myprofreviews.com/r/2467-arizona-state-university-professor",
           "MyProfReviews — ASU", "editorial", "live", "atomic", 100, 200),
    Source("rambler_tempe",
           "https://ramblertempe.com/resources/a-freshmans-guide-to-student-housing-at-arizona-state-university/",
           "Rambler Tempe — Freshman Housing Guide", "editorial", "snapshot", "prose",
           300, 500, overlap=60, commercial_bias=True),
    Source("asuonline_finals",
           "https://asuonline.asu.edu/newsroom/online-learning-tips/survive-finals-week/",
           "ASU Online — Survive Finals Week", "official", "live", "prose", 150, 400, overlap=40),
    Source("heysunny",
           "https://heysunny.asu.edu/blog/finals-advice-you-can-actually-use",
           "Hey Sunny — Finals Advice", "official", "live", "prose", 400, 700, overlap=80),
    Source("asunews_miceli",
           "https://news.asu.edu/20250414-sun-devil-community-tested-tips-taking-exams",
           "ASU News — Tested Tips for Taking Exams", "official", "live", "prose", 300, 600, overlap=60),
    Source("reddit",
           "https://www.reddit.com/r/ASU/comments/seracn/hey_devils_what_are_the_best_tips_youve_ever/",
           "Reddit r/ASU — Best tips thread", "user_opinion", "export", "atomic", 50, 400),
    Source("asuonline_checklist",
           "https://asuonline.asu.edu/newsroom/online-learning-tips/prepare-first-year-college-student-checklist/",
           "ASU Online — First-Year Checklist", "official", "live", "prose", 200, 400, overlap=40),
    Source("weebly",
           "https://asusurvivalguide.weebly.com/",
           "ASU Survival Guide (Weebly)", "editorial", "live", "prose", 200, 500, overlap=50,
           weebly_subpages=("food-and-fun", "housing", "resources", "getting-around")),
    Source("plexuss",
           "https://plexuss.com/n/arizona-state-university-survival-guide",
           "Plexuss — ASU Survival Guide", "editorial", "live", "prose", 200, 500, overlap=50),
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_sources.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add rag/sources.py tests/test_sources.py
git commit -m "Add source registry with per-source fetch and chunk params"
```

---

### Task 3: HTML cleaner (`rag/clean.py`)

**Files:**
- Create: `rag/clean.py`
- Test: `tests/test_clean.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_clean.py
from rag.clean import html_to_text

SAMPLE = """
<html><head><style>.x{color:red}</style><script>var a=1;</script></head>
<body>
<nav>Home About Apply Now</nav>
<header>SiteName</header>
<div class="cookie-banner">We use cookies</div>
<main>
  <h2>Study Tips</h2>
  <p>Professor Smith&#39;s exams are based on lecture slides, not the textbook.</p>
  <a class="share" href="#">Share</a>
  <a href="#">Read more</a>
</main>
<footer>Copyright 2026</footer>
<aside class="ad">Buy now</aside>
</body></html>
"""

def test_strips_boilerplate_and_decodes_entities():
    text = html_to_text(SAMPLE)
    assert "Professor Smith's exams" in text          # apostrophe entity decoded
    assert "<" not in text and ">" not in text          # no tags
    assert "&#39;" not in text                           # no raw entities
    for junk in ("cookies", "Apply Now", "Copyright", "Buy now", "Share", "Read more", "var a"):
        assert junk not in text, junk

def test_collapses_whitespace():
    text = html_to_text("<p>a</p>\n\n\n<p>b</p>")
    assert "\n\n\n" not in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_clean.py -q`
Expected: FAIL with "No module named 'rag.clean'".

- [ ] **Step 3: Write `rag/clean.py`**

```python
# rag/clean.py
"""Convert raw HTML to substantive clean text: strip nav/footer/ads/boilerplate,
decode entities, normalize whitespace. Paragraph breaks are preserved as blank lines
so downstream recursive splitting can use them as semantic boundaries."""
import re
from bs4 import BeautifulSoup

# Tags that never contain substantive content.
_DROP_TAGS = ["script", "style", "nav", "footer", "header", "aside", "noscript",
              "form", "button", "svg", "iframe"]

# class/id substrings that mark boilerplate (ads, share bars, cookie banners, etc.).
_DROP_HINTS = ("cookie", "ad-", "ads", "advert", "share", "social", "newsletter",
               "subscribe", "breadcrumb", "sidebar", "menu", "nav-", "footer",
               "header", "banner", "popup", "modal", "related", "comment-count")

# Link/anchor texts to drop (call-to-action boilerplate).
_DROP_LINK_TEXT = re.compile(r"^\s*(read more|share|apply now|sign up|subscribe|learn more)\s*$", re.I)


def _is_boilerplate(tag):
    attr = " ".join(tag.get("class", []) + [tag.get("id", "")]).lower()
    return any(h in attr for h in _DROP_HINTS)


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for t in soup(_DROP_TAGS):
        t.decompose()
    for t in soup.find_all(True):
        if _is_boilerplate(t):
            t.decompose()
    for a in soup.find_all("a"):
        if _DROP_LINK_TEXT.match(a.get_text(strip=True)):
            a.decompose()
    text = soup.get_text(separator="\n")
    # normalize: trim lines, drop empties, collapse to single blank-line paragraph breaks
    lines = [ln.strip() for ln in text.splitlines()]
    out, blank = [], False
    for ln in lines:
        if ln:
            out.append(ln)
            blank = False
        elif not blank and out:
            out.append("")
            blank = True
    return "\n".join(out).strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_clean.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add rag/clean.py tests/test_clean.py
git commit -m "Add HTML cleaner that strips boilerplate and decodes entities"
```

---

### Task 4: Chunking core (`rag/chunking.py`)

**Files:**
- Create: `rag/chunking.py`
- Test: `tests/test_chunking.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_chunking.py
from rag.chunking import recursive_split, merge_small, apply_overlap, chunk_text, group_short_units

def test_recursive_split_respects_max():
    text = ("Para one sentence. Another sentence here.\n\n"
            "Para two has more words and keeps going for a while indeed.\n\n"
            "Para three is short.")
    pieces = recursive_split(text, size_max=60)
    assert all(len(p) <= 60 for p in pieces)
    assert "".join(pieces).replace(" ", "") != ""  # non-empty

def test_merge_small_combines_trailing_fragment():
    merged = merge_small(["aaaa", "bb", "cc"], size_min=5, size_max=10)
    # "bb" and "cc" are below min and should merge with neighbors, none left < min if avoidable
    assert all(len(m) >= 5 for m in merged) or len(merged) == 1

def test_apply_overlap_prepends_tail_of_previous():
    chunks = ["abcdefghij", "klmnopqrst"]
    out = apply_overlap(chunks, overlap=4)
    assert out[0] == "abcdefghij"
    assert out[1].startswith("ghij")  # last 4 chars of previous prepended

def test_apply_overlap_zero_is_identity():
    chunks = ["aaa", "bbb"]
    assert apply_overlap(chunks, overlap=0) == chunks

def test_chunk_text_prose_applies_overlap_and_bounds():
    text = "Sentence one is here. " * 30  # long prose
    chunks = chunk_text(text, mode="prose", size_min=150, size_max=400, overlap=40)
    assert len(chunks) >= 2
    assert all(len(c) <= 400 + 40 for c in chunks)  # +overlap allowance
    assert chunks[1].startswith(chunks[0][-40:])

def test_chunk_text_atomic_one_unit_one_chunk_no_overlap():
    text = "Review A is great.\n\nReview B is also great and detailed enough."
    chunks = chunk_text(text, mode="atomic", size_min=10, size_max=200, overlap=0)
    assert chunks == ["Review A is great.", "Review B is also great and detailed enough."]

def test_group_short_units_merges_under_threshold():
    units = ["hi", "yo", "this is a sufficiently long standalone comment here"]
    grouped = group_short_units(units, min_chars=50)
    # the two short ones get grouped together
    assert any("hi" in g and "yo" in g for g in grouped)
    assert "this is a sufficiently long standalone comment here" in grouped
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_chunking.py -q`
Expected: FAIL with "No module named 'rag.chunking'".

- [ ] **Step 3: Write `rag/chunking.py`**

```python
# rag/chunking.py
"""Recursive semantic chunking.

prose mode : recursive_split (paragraph -> line -> sentence -> word -> char) packed
             into [size_min, size_max], then overlap carried between chunks.
atomic mode: 1 unit (blank-line-separated review/comment) = 1 chunk, no overlap;
             units under `min_chars` grouped thematically (consecutive) so no
             standalone one-liner fragments survive.
"""
from typing import List

_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


def recursive_split(text: str, size_max: int, separators: List[str] = None) -> List[str]:
    """Split text into pieces each <= size_max, preferring coarse semantic boundaries."""
    separators = separators if separators is not None else _SEPARATORS
    text = text.strip()
    if len(text) <= size_max or not separators:
        return [text] if text else []
    sep, rest = separators[0], separators[1:]
    if sep == "":
        return [text[i:i + size_max] for i in range(0, len(text), size_max)]
    parts = text.split(sep)
    chunks, cur = [], ""
    for part in parts:
        candidate = part if not cur else cur + sep + part
        if len(candidate) <= size_max:
            cur = candidate
        else:
            if cur:
                chunks.append(cur)
                cur = ""
            if len(part) > size_max:
                chunks.extend(recursive_split(part, size_max, rest))
            else:
                cur = part
    if cur:
        chunks.append(cur)
    return [c.strip() for c in chunks if c.strip()]


def merge_small(chunks: List[str], size_min: int, size_max: int, sep: str = " ") -> List[str]:
    """Merge adjacent chunks below size_min while staying <= size_max."""
    if not chunks:
        return []
    out = [chunks[0]]
    for c in chunks[1:]:
        if len(out[-1]) < size_min and len(out[-1]) + len(sep) + len(c) <= size_max:
            out[-1] = out[-1] + sep + c
        else:
            out.append(c)
    # last chunk still too small: fold back into previous if it fits
    if len(out) > 1 and len(out[-1]) < size_min and len(out[-2]) + len(sep) + len(out[-1]) <= size_max:
        out[-2] = out[-2] + sep + out.pop()
    return out


def apply_overlap(chunks: List[str], overlap: int) -> List[str]:
    """Prepend the last `overlap` chars of each chunk to the next (prose only)."""
    if overlap <= 0 or len(chunks) < 2:
        return chunks
    out = [chunks[0]]
    for prev, cur in zip(chunks, chunks[1:]):
        tail = prev[-overlap:]
        out.append(tail + cur)
    return out


def group_short_units(units: List[str], min_chars: int, sep: str = " ") -> List[str]:
    """Group consecutive units shorter than min_chars (Reddit short-comment grouping)."""
    out, buf = [], ""
    for u in units:
        u = u.strip()
        if not u:
            continue
        if len(u) < min_chars:
            buf = (buf + sep + u).strip() if buf else u
            if len(buf) >= min_chars:
                out.append(buf)
                buf = ""
        else:
            if buf:
                out.append(buf)
                buf = ""
            out.append(u)
    if buf:
        out.append(buf)
    return out


def chunk_text(text: str, mode: str, size_min: int, size_max: int, overlap: int = 0) -> List[str]:
    """Top-level chunker dispatch for a single cleaned document."""
    if mode == "atomic":
        units = [u.strip() for u in text.split("\n\n") if u.strip()]
        return group_short_units(units, min_chars=size_min)
    pieces = recursive_split(text, size_max)
    pieces = merge_small(pieces, size_min, size_max)
    return apply_overlap(pieces, overlap)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_chunking.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add rag/chunking.py tests/test_chunking.py
git commit -m "Add recursive semantic chunker with overlap and atomic modes"
```

---

### Task 5: Metadata tagger (`rag/metadata.py`)

**Files:**
- Create: `rag/metadata.py`
- Test: `tests/test_metadata.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_metadata.py
from rag.metadata import build_chunk, chunk_id, REQUIRED_FIELDS
from rag.sources import SOURCE_REGISTRY

def test_chunk_id_format():
    assert chunk_id("weebly", 3) == "weebly::3"

def test_build_chunk_has_all_required_fields():
    src = next(s for s in SOURCE_REGISTRY if s.id == "heysunny")
    chunk = build_chunk(src, chunk_index=0, text="Some text", section_title="Study Tips")
    for f in REQUIRED_FIELDS:
        assert f in chunk, f
    assert chunk["chunk_id"] == "heysunny::0"
    assert chunk["source_type"] == "official"
    assert chunk["section_title"] == "Study Tips"
    assert chunk["text"] == "Some text"

def test_build_chunk_nulls_are_explicit():
    src = next(s for s in SOURCE_REGISTRY if s.id == "plexuss")
    chunk = build_chunk(src, chunk_index=1, text="x")
    assert "author" in chunk and chunk["author"] is None
    assert "section_title" in chunk and chunk["section_title"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_metadata.py -q`
Expected: FAIL with "No module named 'rag.metadata'".

- [ ] **Step 3: Write `rag/metadata.py`**

```python
# rag/metadata.py
"""Attach the 9 required metadata fields to every chunk."""
from typing import Optional
from rag.sources import Source

REQUIRED_FIELDS = (
    "chunk_id", "source_url", "source_title", "source_type",
    "author", "date", "chunk_index", "section_title", "source_id",
)


def chunk_id(source_id: str, index: int) -> str:
    return f"{source_id}::{index}"


def build_chunk(source: Source, chunk_index: int, text: str,
                section_title: Optional[str] = None) -> dict:
    return {
        "chunk_id": chunk_id(source.id, chunk_index),
        "source_id": source.id,
        "source_url": source.url,
        "source_title": source.title,
        "source_type": source.source_type,
        "author": source.author,
        "date": source.date,
        "chunk_index": chunk_index,
        "section_title": section_title,
        "commercial_bias": source.commercial_bias,
        "text": text,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_metadata.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add rag/metadata.py tests/test_metadata.py
git commit -m "Add chunk metadata tagger with 9 required fields"
```

---

### Task 6: Per-source preprocessing (`rag/preprocess.py`)

**Files:**
- Create: `rag/preprocess.py`
- Test: `tests/test_preprocess.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_preprocess.py
from rag.preprocess import prepare_units, weebly_is_homepage_blob

def test_weebly_homepage_blob_excluded():
    # Homepage = single unbroken blob mixing many topics -> not chunkable
    blob = ("Transportation light rail food dining housing tutoring finals stress relief "
            "bikes parking everything in one paragraph " * 5)
    assert weebly_is_homepage_blob(blob, is_homepage=True) is True
    units = prepare_units("weebly", blob, is_homepage=True)
    assert units == []   # homepage produces no units

def test_weebly_subpage_kept():
    text = "Getting Around\n\nThere is a free intercampus shuttle every 30 minutes."
    units = prepare_units("weebly", text, is_homepage=False)
    assert any("shuttle" in u for u in units)

def test_quora_prepends_question():
    text = "QUESTION: Which professors do you recommend?\n\nDr. Lee is fantastic for stats."
    units = prepare_units("quora", text)
    assert all(u.startswith("Which professors do you recommend?") for u in units)

def test_reddit_keeps_text_units():
    text = "Go to office hours.\n\nUse the free tutoring center, it is underrated."
    units = prepare_units("reddit", text)
    assert len(units) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_preprocess.py -q`
Expected: FAIL with "No module named 'rag.preprocess'".

- [ ] **Step 3: Write `rag/preprocess.py`**

```python
# rag/preprocess.py
"""Per-source special-case handling applied to cleaned text BEFORE chunking.

Returns a list of "units" (blank-line-separated strings) ready for chunk_text.
For most sources this is a passthrough; the special sources are handled explicitly.
"""
import re
from typing import List

_QUESTION_PREFIX = re.compile(r"^\s*QUESTION:\s*(.+?)\s*$", re.I | re.M)


def weebly_is_homepage_blob(text: str, is_homepage: bool) -> bool:
    """The Weebly homepage is one unbroken multi-topic blob; never chunk it (TOC only)."""
    return bool(is_homepage)


def _split_units(text: str) -> List[str]:
    return [u.strip() for u in text.split("\n\n") if u.strip()]


def prepare_units(source_id: str, text: str, is_homepage: bool = False) -> List[str]:
    if source_id == "weebly":
        if weebly_is_homepage_blob(text, is_homepage):
            return []                      # homepage blob is a table of contents only
        return _split_units(text)
    if source_id == "quora":
        m = _QUESTION_PREFIX.search(text)
        question = m.group(1).strip() if m else ""
        body = _QUESTION_PREFIX.sub("", text).strip()
        answers = _split_units(body)
        return [f"{question} {a}".strip() for a in answers] if question else answers
    if source_id == "reddit":
        # top-level comments only (export already excludes nested replies); short-comment
        # grouping happens later in chunk_text(atomic).
        return _split_units(text)
    return _split_units(text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_preprocess.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add rag/preprocess.py tests/test_preprocess.py
git commit -m "Add per-source preprocessing (Weebly TOC, Quora prepend, Reddit)"
```

---

### Task 7: Fetch + raw snapshot (`rag/fetch.py`)

**Files:**
- Create: `rag/fetch.py`
- Test: `tests/test_fetch.py`, `tests/fixtures/sample.html`

- [ ] **Step 1: Create fixture**

`tests/fixtures/sample.html`:

```html
<html><body><nav>menu</nav><main><p>Hello world content.</p></main><footer>f</footer></body></html>
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_fetch.py
import os, pathlib
from rag.fetch import load_raw, raw_paths

def test_raw_paths_uses_documents_raw(tmp_path):
    html_p, txt_p = raw_paths("heysunny", base=tmp_path)
    assert html_p.name == "heysunny.html"
    assert txt_p.name == "heysunny.txt"

def test_load_raw_prefers_txt_snapshot(tmp_path):
    html_p, txt_p = raw_paths("demo", base=tmp_path)
    txt_p.write_text("clean snapshot text", encoding="utf-8")
    assert load_raw("demo", base=tmp_path) == "clean snapshot text"

def test_load_raw_missing_returns_none(tmp_path):
    assert load_raw("nope", base=tmp_path) is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 -m pytest tests/test_fetch.py -q`
Expected: FAIL with "No module named 'rag.fetch'".

- [ ] **Step 4: Write `rag/fetch.py`**

```python
# rag/fetch.py
"""Fetch sources and persist a raw snapshot to documents/raw/.

Strategies (from Source.fetch):
  live     : GET the URL with a browser UA, save <id>.html + <id>.txt (cleaned).
  snapshot : do NOT hit network; read a pre-saved <id>.html committed to the repo
             (used for bot-blocked sources like Rambler Tempe).
  export   : read a manual export from documents/exports/<id>.* if present, else warn+skip.
"""
import pathlib
import sys
from typing import Optional, Tuple
import requests

from rag.sources import Source
from rag.clean import html_to_text

RAW_DIR = pathlib.Path("documents/raw")
EXPORT_DIR = pathlib.Path("documents/exports")
_UA = {"User-Agent": "Mozilla/5.0 (compatible; ASU-RAG-coursework/1.0)"}


def raw_paths(source_id: str, base: pathlib.Path = RAW_DIR) -> Tuple[pathlib.Path, pathlib.Path]:
    base = pathlib.Path(base)
    return base / f"{source_id}.html", base / f"{source_id}.txt"


def load_raw(source_id: str, base: pathlib.Path = RAW_DIR) -> Optional[str]:
    """Return cleaned snapshot text if present (.txt preferred, else clean the .html)."""
    html_p, txt_p = raw_paths(source_id, base)
    if txt_p.exists():
        return txt_p.read_text(encoding="utf-8")
    if html_p.exists():
        return html_to_text(html_p.read_text(encoding="utf-8"))
    return None


def _save(source_id: str, html: str) -> str:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    html_p, txt_p = raw_paths(source_id)
    html_p.write_text(html, encoding="utf-8")
    text = html_to_text(html)
    txt_p.write_text(text, encoding="utf-8")
    return text


def fetch_source(source: Source, url: Optional[str] = None) -> Optional[str]:
    """Return cleaned text for a source, fetching+snapshotting if needed.

    `url` overrides source.url (used for Weebly sub-pages).
    Returns None when an export source has no file (caller logs+skips)."""
    target = url or source.url
    if source.fetch == "export":
        for ext in ("txt", "html", "json"):
            p = EXPORT_DIR / f"{source.id}.{ext}"
            if p.exists():
                raw = p.read_text(encoding="utf-8")
                return html_to_text(raw) if ext == "html" else raw
        print(f"[skip] no export found for '{source.id}' in {EXPORT_DIR}/", file=sys.stderr)
        return None
    if source.fetch == "snapshot":
        text = load_raw(source.id)
        if text is None:
            print(f"[skip] no snapshot found for '{source.id}' in {RAW_DIR}/", file=sys.stderr)
        return text
    # live
    cached = load_raw(source.id) if url is None else None
    if cached is not None:
        return cached
    resp = requests.get(target, headers=_UA, timeout=20)
    resp.raise_for_status()
    return _save(source.id, resp.text)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_fetch.py -q`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add rag/fetch.py tests/test_fetch.py tests/fixtures/sample.html
git commit -m "Add fetcher with live/snapshot/export strategies and raw snapshots"
```

---

### Task 8: Orchestrator + verification report (`rag/ingest.py`, `scripts/run_ingest.py`)

**Files:**
- Create: `rag/ingest.py`, `scripts/run_ingest.py`
- Test: `tests/test_ingest.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ingest.py
from rag.ingest import chunks_for_source
from rag.sources import Source

def test_chunks_for_source_atomic_produces_metadata():
    src = Source("demo_rev", "http://x", "Demo Reviews", "user_opinion",
                 "export", "atomic", 20, 200)
    text = ("Professor A shows up on time and grades easy, students love the energy.\n\n"
            "Professor B is tough but fair and explains concepts clearly every lecture.")
    chunks = chunks_for_source(src, text)
    assert len(chunks) == 2
    assert chunks[0]["chunk_id"] == "demo_rev::0"
    assert chunks[0]["source_type"] == "user_opinion"
    # atomic -> review boundary preserved intact (no mid-opinion split)
    assert "shows up on time" in chunks[0]["text"]

def test_chunks_for_source_prose_has_overlap():
    src = Source("demo_prose", "http://x", "Demo", "official", "live", "prose",
                 150, 400, overlap=40)
    text = "This is a study tip sentence that repeats. " * 30
    chunks = chunks_for_source(src, text)
    assert len(chunks) >= 2
    assert chunks[1]["text"].startswith(chunks[0]["text"][-40:])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_ingest.py -q`
Expected: FAIL with "No module named 'rag.ingest'".

- [ ] **Step 3: Write `rag/ingest.py`**

```python
# rag/ingest.py
"""Orchestrate fetch -> clean -> preprocess -> chunk -> tag for all sources,
writing data/chunks.jsonl, then a verification report."""
import json
import pathlib
from typing import List, Optional

from rag.sources import Source, SOURCE_REGISTRY
from rag.fetch import fetch_source
from rag.preprocess import prepare_units
from rag.chunking import chunk_text
from rag.metadata import build_chunk, REQUIRED_FIELDS

OUT_PATH = pathlib.Path("data/chunks.jsonl")
WEEBLY_BASE = "https://asusurvivalguide.weebly.com/"


def chunks_for_source(source: Source, text: str, is_homepage: bool = False) -> List[dict]:
    units = prepare_units(source.id, text, is_homepage=is_homepage)
    joined = "\n\n".join(units)
    pieces = chunk_text(joined, source.mode, source.size_min, source.size_max, source.overlap)
    return [build_chunk(source, i, p) for i, p in enumerate(pieces)]


def _weebly_chunks(source: Source) -> List[dict]:
    """Homepage is TOC only (never chunked); each sub-page fetched + chunked separately."""
    chunks: List[dict] = []
    idx = 0
    for sub in source.weebly_subpages:
        text = fetch_source(source, url=f"{WEEBLY_BASE}{sub}")
        if not text:
            continue
        for c in chunks_for_source(source, text):
            c["chunk_id"] = f"{source.id}-{sub}::{idx}"
            c["chunk_index"] = idx
            c["section_title"] = sub
            chunks.append(c)
            idx += 1
    return chunks


def ingest_source(source: Source) -> List[dict]:
    if source.id == "weebly":
        return _weebly_chunks(source)
    text = fetch_source(source)
    if not text:
        return []
    return chunks_for_source(source, text)


def ingest_all(registry: Optional[List[Source]] = None) -> List[dict]:
    registry = registry or SOURCE_REGISTRY
    all_chunks: List[dict] = []
    for src in registry:
        all_chunks.extend(ingest_source(src))
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    return all_chunks


def verification_report(chunks: List[dict], registry: Optional[List[Source]] = None) -> str:
    registry = registry or SOURCE_REGISTRY
    by_src = {}
    for c in chunks:
        by_src.setdefault(c["source_id"], []).append(c)
    lines = ["=== Ingestion verification report ===",
             f"total chunks: {len(chunks)}", ""]
    for src in registry:
        cs = by_src.get(src.id, [])
        if not cs:
            lines.append(f"{src.id:24s}  (no chunks — skipped/empty)")
            continue
        sizes = [len(c["text"]) for c in cs]
        lines.append(f"{src.id:24s}  n={len(cs):3d}  size[min/avg/max]="
                     f"{min(sizes)}/{sum(sizes)//len(sizes)}/{max(sizes)}  "
                     f"target={src.size_min}-{src.size_max} overlap={src.overlap}")
    # assertions
    problems = []
    for c in chunks:
        missing = [f for f in REQUIRED_FIELDS if f not in c]
        if missing:
            problems.append(f"{c.get('chunk_id')}: missing {missing}")
        if c["source_type"] not in {"official", "editorial", "user_opinion"}:
            problems.append(f"{c.get('chunk_id')}: bad source_type")
    if any(c["chunk_id"].startswith("weebly::") for c in chunks):
        problems.append("Weebly homepage blob was chunked (should be TOC only)")
    lines.append("")
    lines.append("PROBLEMS: " + ("none" if not problems else f"{len(problems)}"))
    lines.extend("  - " + p for p in problems[:20])
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_ingest.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Write `scripts/run_ingest.py`**

```python
# scripts/run_ingest.py
"""CLI: run the full ingestion + chunking pipeline and print the verification report.

Usage: python3 -m scripts.run_ingest
"""
from rag.ingest import ingest_all, verification_report


def main():
    chunks = ingest_all()
    print(verification_report(chunks))
    print(f"\nWrote {len(chunks)} chunks to data/chunks.jsonl")


if __name__ == "__main__":
    main()
```

Also create `scripts/__init__.py` (empty) so `-m scripts.run_ingest` works.

- [ ] **Step 6: Commit**

```bash
git add rag/ingest.py scripts/run_ingest.py scripts/__init__.py tests/test_ingest.py
git commit -m "Add ingestion orchestrator, Weebly subpage handling, verification report"
```

---

### Task 9: Fetch real snapshots, run end-to-end, update planning.md

**Files:**
- Create: `documents/raw/rambler_tempe.html` (committed snapshot)
- Modify: `planning.md` (Chunking Strategy note)
- Output: `data/chunks.jsonl`

- [ ] **Step 1: Provide the Rambler Tempe snapshot (bot-blocked, 403 on requests)**

The assistant fetches the page via its WebFetch tool and writes the article HTML/text to
`documents/raw/rambler_tempe.html`. (If WebFetch is unavailable at execution time, save the
page source manually from a browser to that path.) Verify:

Run: `python3 -c "from rag.fetch import load_raw; print(len(load_raw('rambler_tempe') or ''))"`
Expected: a non-zero length.

- [ ] **Step 2: Run the full pipeline**

Run: `python3 -m scripts.run_ingest`
Expected: verification report prints; "PROBLEMS: none"; `data/chunks.jsonl` created.

- [ ] **Step 3: Inspect size distribution vs. targets**

Read the printed per-source `size[min/avg/max]` lines and confirm each lands near its
`target` range. If a prose source's chunks systematically exceed `size_max + overlap`, lower
its `size_max` in `rag/sources.py`; if reviews fragment, this is the atomic-grouping path.
Record any deliberate change for Step 5.

- [ ] **Step 4: Add the per-source-ranges note to `planning.md`**

Under the **Chunking Strategy → Reasoning** bullet in `planning.md`, append:

```markdown
> **Per-source refinement (implementation):** The "200–600 chars" above is a summary range.
> The implemented chunker uses CLAUDE.md's per-source table as authoritative. Review/comment
> sources (RateMyProfessors 50–200, MyProfReviews 100–200, Reddit 50–400) intentionally fall
> below the 200 floor: an atomic review is one self-contained thought and must not be padded or
> merged with another review just to clear a minimum. Prose sources keep the 15–20% overlap;
> review/comment sources use none.
```

- [ ] **Step 5: Log the AI override in CLAUDE.md**

Add a row to the **AI Usage — Override Log** table in `CLAUDE.md`:

```markdown
| 2026-06-07 | Chunking | Generated per-source chunker honoring CLAUDE.md size table | Refined planning.md's flat "200–600" range; let review sources go below 200, no-overlap for atomic units | Atomic reviews must stay one intact thought, not be padded to a minimum |
```

- [ ] **Step 6: Run the whole test suite**

Run: `python3 -m pytest -q`
Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add documents/raw/rambler_tempe.html data/chunks.jsonl planning.md CLAUDE.md
git commit -m "Run M3 pipeline end-to-end; snapshot Rambler; document chunk-range refinement"
```

---

## Self-Review notes

- **Spec coverage:** fetch+snapshot (T7) · clean/strip boilerplate (T3) · recursive semantic split + overlap + atomic (T4) · per-source params (T2) · Weebly homepage-not-chunked + subpages (T6/T8) · Quora prepend (T6) · Reddit top-level+short-grouping (T6/T4) · Rambler commercial flag (T2 `commercial_bias` → metadata T5) · 9 metadata fields (T5) · verification report (T8) · planning.md update (T9). All covered.
- **Type consistency:** `chunk_text(text, mode, size_min, size_max, overlap)`, `prepare_units(source_id, text, is_homepage)`, `fetch_source(source, url)`, `build_chunk(source, chunk_index, text, section_title)`, `load_raw(source_id, base)` used consistently across tasks.
- **Note on `data/chunks.jsonl` commit:** committed as the M3 deliverable so M4 can consume it without re-fetching; remove from git later if the corpus grows large.
