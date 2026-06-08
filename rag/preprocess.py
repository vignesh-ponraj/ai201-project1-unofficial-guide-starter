"""Per-source special-case handling applied to cleaned text BEFORE chunking.

Returns a list of "units" (blank-line-separated strings) ready for chunk_text.
For most sources this is a passthrough; the special sources are handled explicitly.
"""
import re
from typing import List

_QUESTION_PREFIX = re.compile(r"^\s*QUESTION:\s*(.+?)\s*$", re.I | re.M)
# A numbered professor header on MyProfReviews, e.g. "2. William Martin".
_PROF_HEADER = re.compile(r"^\d+\.\s+\S")
# Minimum length for a Weebly homepage paragraph to count as content (not a TOC link).
_HOMEPAGE_MIN_UNIT = 120


def _split_units(text: str) -> List[str]:
    return [u.strip() for u in text.split("\n\n") if u.strip()]


def prepare_units(source_id: str, text: str, is_homepage: bool = False) -> List[str]:
    if source_id == "weebly":
        units = _split_units(text)
        if is_homepage:
            # The homepage is one big multi-topic content blob surrounded by tiny TOC
            # link fragments. Keep the substantial paragraph(s) — which the downstream
            # semantic splitter breaks into retrievable chunks — and drop the nav TOC.
            units = [u for u in units if len(u) >= _HOMEPAGE_MIN_UNIT]
        return units
    if source_id == "myprofreviews":
        # Each professor entry is "N. Name" followed by the review body; keep them
        # together so the professor's name stays as context for the review.
        units = _split_units(text)
        merged: List[str] = []
        i = 0
        while i < len(units):
            u = units[i]
            if _PROF_HEADER.match(u) and len(u) < 60 and i + 1 < len(units):
                merged.append(f"{u} — {units[i + 1]}")
                i += 2
            else:
                merged.append(u)
                i += 1
        return merged
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
