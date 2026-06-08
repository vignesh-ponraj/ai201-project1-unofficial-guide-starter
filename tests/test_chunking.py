from rag.chunking import (recursive_split, merge_small, apply_overlap,
                          chunk_text, group_short_units)


def test_recursive_split_respects_max():
    text = ("Para one sentence. Another sentence here.\n\n"
            "Para two has more words and keeps going for a while indeed.\n\n"
            "Para three is short.")
    pieces = recursive_split(text, size_max=60)
    assert all(len(p) <= 60 for p in pieces)
    assert "".join(pieces).replace(" ", "") != ""  # non-empty


def test_merge_small_combines_trailing_fragment():
    merged = merge_small(["aaaa", "bb", "cc"], size_min=5, size_max=10)
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
    assert any("hi" in g and "yo" in g for g in grouped)
    assert "this is a sufficiently long standalone comment here" in grouped
