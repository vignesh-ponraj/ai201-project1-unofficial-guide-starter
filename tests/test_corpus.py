import json
from rag.corpus import load_chunks


def test_load_chunks_reads_jsonl(tmp_path):
    p = tmp_path / "c.jsonl"
    rows = [{"chunk_id": "a::0", "text": "hello"}, {"chunk_id": "a::1", "text": "world"}]
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    out = load_chunks(p)
    assert [c["chunk_id"] for c in out] == ["a::0", "a::1"]
    assert out[0]["text"] == "hello"


def test_load_chunks_skips_blank_lines(tmp_path):
    p = tmp_path / "c.jsonl"
    p.write_text('{"chunk_id":"a::0","text":"x"}\n\n', encoding="utf-8")
    assert len(load_chunks(p)) == 1
