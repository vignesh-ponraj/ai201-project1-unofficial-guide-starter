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
    """Each Weebly page is fetched and chunked separately. The homepage holds content
    (e.g. finals stress-relief) that exists nowhere else, so it is semantically chunked
    too (TOC link fragments are dropped in preprocessing), not skipped."""
    chunks: List[dict] = []
    idx = 0
    pages = [("homepage", source.url)]
    pages += [(sub, f"{WEEBLY_BASE}{sub}") for sub in source.weebly_subpages]
    for name, url in pages:
        text = fetch_source(source, url=url, save_id=f"weebly-{name}")
        if not text:
            continue
        for c in chunks_for_source(source, text, is_homepage=(name == "homepage")):
            c["chunk_id"] = f"{source.id}-{name}::{idx}"
            c["chunk_index"] = idx
            c["section_title"] = name
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
    lines.append("")
    lines.append("PROBLEMS: " + ("none" if not problems else f"{len(problems)}"))
    lines.extend("  - " + p for p in problems[:20])

    # Soft warnings: a fetched source with almost no text is likely JS-rendered
    # (our requests-based fetcher can't run JS). Surfaced, not failed.
    thin = []
    fetched_ids = {s.id for s in registry if s.fetch != "export"}
    for src in registry:
        if src.id not in fetched_ids:
            continue
        total = sum(len(c["text"]) for c in by_src.get(src.id, []))
        if total < src.size_min:
            thin.append(f"{src.id}: only {total} chars extracted "
                        f"(likely JS-rendered — consider a manual export)")
    lines.append("")
    lines.append("THIN-CONTENT WARNINGS: " + ("none" if not thin else f"{len(thin)}"))
    lines.extend("  - " + w for w in thin)
    return "\n".join(lines)
