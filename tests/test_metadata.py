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
