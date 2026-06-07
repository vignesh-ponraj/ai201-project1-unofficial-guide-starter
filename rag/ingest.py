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
