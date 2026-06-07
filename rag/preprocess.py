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
