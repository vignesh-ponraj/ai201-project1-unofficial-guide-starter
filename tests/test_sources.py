from rag.sources import SOURCE_REGISTRY, VALID_SOURCE_TYPES, Source


def test_registry_nonempty_and_unique_ids():
    ids = [s.id for s in SOURCE_REGISTRY]
    assert len(ids) == len(set(ids)), "source ids must be unique"
    assert len(SOURCE_REGISTRY) >= 8


def test_every_source_has_valid_type_and_required_fields():
    for s in SOURCE_REGISTRY:
        assert s.source_type in VALID_SOURCE_TYPES, s.id
        assert s.url and s.title
        assert s.fetch in {"live", "snapshot", "export"}
        assert s.mode in {"prose", "atomic"}
        assert s.size_min <= s.size_max
        if s.mode == "atomic":
            assert s.overlap == 0, s.id


def test_blocked_sources_use_export_strategy():
    by_id = {s.id: s for s in SOURCE_REGISTRY}
    for bid in ("ratemyprofessors", "quora", "reddit"):
        assert by_id[bid].fetch == "export"
