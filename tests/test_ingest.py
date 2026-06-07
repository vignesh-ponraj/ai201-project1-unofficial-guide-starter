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
    assert "shows up on time" in chunks[0]["text"]


def test_chunks_for_source_prose_has_overlap():
    src = Source("demo_prose", "http://x", "Demo", "official", "live", "prose",
                 150, 400, overlap=40)
    text = "This is a study tip sentence that repeats. " * 30
    chunks = chunks_for_source(src, text)
    assert len(chunks) >= 2
    assert chunks[1]["text"].startswith(chunks[0]["text"][-40:])
