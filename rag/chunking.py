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
    if len(out) > 1 and len(out[-1]) < size_min:
        last = out[-1]
        if len(out[-2]) + len(sep) + len(last) <= size_max:
            out.pop()
            out[-1] = out[-1] + sep + last
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
