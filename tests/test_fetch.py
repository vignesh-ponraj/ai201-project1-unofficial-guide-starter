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
