"""Data-integrity guards: title fallback (no blank or invented titles)."""

import json


def test_registry_title_fallback(monkeypatch, tmp_path):
    """Standards with an IS number but no usable title get the exact
    sentinel 'Title unavailable in registry' — never a blank, never invented."""
    import app.services.standards_registry as reg

    data = {"standards": [
        {"is_number_clean": "IS 1", "core_number": "1", "title": ""},
        {"is_number_clean": "IS 2", "core_number": "2", "title": "   "},
        {"is_number_clean": "IS 3", "core_number": "3", "title": "Real title"},
    ]}
    f = tmp_path / "reg.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(reg, "REGISTRY_FILE", f)
    reg._load_registry.cache_clear()
    try:
        recs = reg.all_standards()
        assert recs[0]["title"] == "Title unavailable in registry"
        assert recs[1]["title"] == "Title unavailable in registry"
        assert recs[2]["title"] == "Real title"
    finally:
        # Restore the real registry cache for every other test.
        reg._load_registry.cache_clear()


def test_real_registry_has_no_blank_titles():
    """Audit result: the shipped registry currently has zero blank titles."""
    from app.services import standards_registry as reg

    blanks = [r for r in reg.all_standards() if not (r.get("title") or "").strip()]
    assert blanks == []
