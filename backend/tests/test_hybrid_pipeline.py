"""Tests for the hybrid intelligence pipeline (task §28).

External services (BIS page, HF router) are mocked — no live dependencies.
LLM-failure paths are exercised by pointing the provider chain at a broken
provider via monkeypatched settings.
"""

from __future__ import annotations

import json

import pytest

from app.services import external_sources, pipeline, reconciliation, requirement
from app.services.external_sources import SourceFact


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Hermetic suite: block ALL real network from the app code.

    Individual tests that need a fake upstream re-patch httpx themselves;
    their monkeypatch (applied later) overrides this one.
    """
    import httpx

    def _blocked(url, *a, **k):
        raise httpx.ConnectError("network disabled in tests")

    monkeypatch.setattr(httpx, "get", _blocked, raising=False)
    monkeypatch.setattr(httpx, "post", _blocked, raising=False)


@pytest.fixture()
def no_llm(monkeypatch):
    """Force the LLM chain to fail at EVERY call site (missing token)."""
    import app.services.llm as llm_mod
    import app.services.pipeline as pipeline_mod
    import app.services.requirement as requirement_mod

    monkeypatch.setattr(llm_mod, "llm_complete", _raise_llm)
    # These modules bind llm_complete at import time — patch their bindings too.
    monkeypatch.setattr(requirement_mod, "llm_complete", _raise_llm, raising=False)
    monkeypatch.setattr(pipeline_mod, "llm_complete", _raise_llm, raising=False)


def _raise_llm(*a, **k):
    raise RuntimeError("HF_TOKEN not set")


@pytest.fixture()
def bis_page(monkeypatch):
    """Serve a synthetic official-looking Scheme-1 page to the BIS source."""
    import httpx

    html = """
    <html><body>
    सीमेंट (गुणवत्ता नियंत्रण) आदेश, 2003 एस.ओ. संख्या 191(E) दिनांक 17 फरवरी 2003
    IS 1489 (भाग 1) पोर्टलैंड पोज़ोलाना सीमेंट IS 1489 (भाग 2) IS 269 साधारण पोर्टलैंड सीमेंट
    इस्पात और इस्पात उत्पाद (गुणवत्ता नियंत्रण) आदेश, 2020 S.O. 756(E) दिनांक 14-02-2020
    IS 1786:2008 कंक्रीट सुदृढीकरण IS 2062:2011 हॉट रोल्ड संरचनात्मक इस्पात
    </body></html>
    """

    class FakeResp:
        status_code = 200
        text = html

    def fake_get(url, **kwargs):
        return FakeResp()

    monkeypatch.setattr(httpx, "get", fake_get)


def _fact(field: str, value: str, status: str = "SOURCE_RETRIEVED", std: str = "IS 2062") -> dict:
    return SourceFact(
        source_type="OFFICIAL_BIS", source_name="BIS", title="t",
        url="https://www.bis.gov.in/x", standard_number=std,
        field=field, value=value, fact=f"{field}: {value}",
        verification_status=status,
    ).to_dict()


# ---------------------------------------------------------------- requirement --

def test_interpret_deterministic_fallback(no_llm):
    out = requirement.interpret_requirement("cement for a government road construction project")
    assert out["source"] == "deterministic_fallback"
    assert out["llm_available"] is False
    assert out["product"] == "cement"
    assert out["procurement_type"] == "government"
    assert any(a["field"] == "cement_type" for a in out["ambiguities"])


@pytest.mark.usefixtures("no_llm")
def test_interpret_ambiguity_detection_rulebased():
    out = requirement.interpret_requirement("steel for a warehouse")
    assert any(a["field"] == "steel_form" for a in out["ambiguities"])
    out2 = requirement.interpret_requirement("TMT reinforcement bars steel for a slab")
    assert not any(a["field"] == "steel_form" for a in out2["ambiguities"])


@pytest.mark.usefixtures("no_llm")
def test_interpret_explicit_standard_numbers():
    out = requirement.interpret_requirement("tell me about IS 1786:2008 and IS 2062")
    nums = " ".join(out["explicit_standard_numbers"])
    assert "1786" in nums and "2062" in nums


def test_expand_query_fallback_hints_only(no_llm):
    out = requirement.expand_query("steel for structural construction")
    assert out["source"] == "deterministic_fallback"
    assert out["expansions"] and all(isinstance(e, str) for e in out["expansions"])


def test_plan_retrieval_version_question(no_llm):
    out = requirement.plan_retrieval("what is the current version of IS 383?", {})
    assert "current_standard_edition" in out["needs"]


def test_plan_retrieval_certification_question(no_llm):
    out = requirement.plan_retrieval("is this certification mandatory?", {})
    assert "certification_status" in out["needs"] and "qco" in out["needs"]


def test_llm_json_extraction_tolerates_fences():
    from app.services.requirement import _extract_json
    assert _extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert _extract_json('junk {"a": {"b": 2}} trailing') == {"a": {"b": 2}}
    assert _extract_json("no json here") is None


# ----------------------------------------------------------- external sources --

def test_bis_source_parses_listed_standard(bis_page, tmp_path, monkeypatch):
    monkeypatch.setattr(external_sources, "CACHE_FILE", tmp_path / "ext_cache.json")
    facts = external_sources.retrieve_external("qco", "IS 1786")
    assert facts and facts[0]["verification_status"] == "SOURCE_RETRIEVED"
    assert facts[0]["source_type"] == "OFFICIAL_BIS"
    assert facts[0]["url"].startswith("https://www.bis.gov.in")
    assert facts[0]["retrieved_at"]


def test_bis_source_marks_unlisted_standard(bis_page, tmp_path, monkeypatch):
    monkeypatch.setattr(external_sources, "CACHE_FILE", tmp_path / "ext_cache.json")
    facts = external_sources.retrieve_external("qco", "IS 9999")
    assert facts and facts[0]["value"] == "not_listed"


def test_bis_source_unavailable(tmp_path, monkeypatch):
    import httpx

    def boom(url, **k):
        raise httpx.ConnectError("no network")

    monkeypatch.setattr(httpx, "get", boom)
    monkeypatch.setattr(external_sources, "CACHE_FILE", tmp_path / "ext_cache.json")
    facts = external_sources.retrieve_external("qco", "IS 2062")
    assert facts and facts[0]["verification_status"] == "SOURCE_UNAVAILABLE"


def test_external_cache_preserves_retrieved_at(bis_page, tmp_path, monkeypatch):
    monkeypatch.setattr(external_sources, "CACHE_FILE", tmp_path / "ext_cache.json")
    first = external_sources.retrieve_external("qco", "IS 2062")
    second = external_sources.retrieve_external("qco", "IS 2062")
    assert first[0]["retrieved_at"] == second[0]["retrieved_at"]


def test_unknown_need_is_honest():
    facts = external_sources.retrieve_external("definitely_unknown_need", "IS 2062")
    assert facts and facts[0]["verification_status"] == "SOURCE_UNAVAILABLE"


# -------------------------------------------------------------- reconciliation --

def test_edition_mismatch_flags_outdated_registry():
    rec = {"is_number_clean": "IS 1234", "core_number": "1234", "latest_version": "1992",
           "certification": {"mandatory": False}}
    out = reconciliation.reconcile(rec, [_fact("edition", "2025")])
    types = {d["type"] for d in out["discrepancies"]}
    assert "EDITION_MISMATCH" in types
    assert out["verification_status"] == "OUTDATED_REGISTRY"
    assert out["upgrade_available"] is True
    d = next(d for d in out["discrepancies"] if d["type"] == "EDITION_MISMATCH")
    assert d["local_value"].endswith("1992") and d["external_value"].endswith("2025")
    assert d["status"] in ("OUTDATED_REGISTRY", "MANUAL_REVIEW_REQUIRED")


def test_qco_mismatch_when_not_listed():
    rec = {"is_number_clean": "IS 383", "core_number": "383", "latest_version": "2016",
           "certification": {"mandatory": True}}
    out = reconciliation.reconcile(rec, [_fact("qco", "not_listed")])
    assert any(d["type"] == "QCO_MISMATCH" for d in out["discrepancies"])
    assert out["verification_status"] == "PARTIALLY_VERIFIED"


def test_qco_listed_confirms_mandatory():
    rec = {"is_number_clean": "IS 1786", "core_number": "1786", "latest_version": "2008",
           "certification": {"mandatory": True}}
    out = reconciliation.reconcile(rec, [_fact("qco", '{"qco_name": "steel and steel products"}')])
    assert out["verification_status"] == "PARTIALLY_VERIFIED"
    assert not any(d["type"] == "QCO_MISMATCH" for d in out["discrepancies"])


def test_certification_mismatch_when_local_says_voluntary():
    rec = {"is_number_clean": "IS 999", "core_number": "999", "latest_version": "2010",
           "certification": {"mandatory": False}}
    out = reconciliation.reconcile(rec, [_fact("qco", '{"qco_name": "cement"}')])
    assert any(d["type"] == "CERTIFICATION_MISMATCH" for d in out["discrepancies"])


def test_source_unavailable_state():
    out = reconciliation.reconcile(None, [_fact("qco", "", status="SOURCE_UNAVAILABLE")])
    assert out["verification_status"] == "SOURCE_UNAVAILABLE"
    assert "Authoritative source could not be reached" in out["notes"][0]


def test_stale_cache_flagged():
    out = reconciliation.reconcile(None, [_fact("qco", "x", status="STALE_CACHE")])
    assert out["verification_status"] in ("PARTIALLY_VERIFIED", "SOURCE_UNAVAILABLE")
    assert any("stale" in n.lower() for n in out["notes"])


def test_reconcile_many_covers_unknown_codes():
    outs = reconciliation.reconcile_many([], {"IS 2062": [_fact("qco", "x")]})
    assert outs and outs[0]["standard"] == "IS 2062"


# ------------------------------------------------------------------ pipeline --

def test_grounded_pipeline_deterministic_end_to_end(no_llm, tmp_path, monkeypatch):
    monkeypatch.setattr(external_sources, "CACHE_FILE", tmp_path / "ext_cache.json")
    out = pipeline.grounded_recommend("Reinforcement bars for concrete in a bridge deck", top_k=4)
    assert out["recommendations"], "deterministic retrieval must still work with no LLM"
    assert out["explanation_source"] == "deterministic_fallback"
    assert out["interpreted_requirement"]["source"] == "deterministic_fallback"
    assert "grounded_context" in out and "warnings" in out
    ctx = out["grounded_context"]
    assert ctx["user_requirement"] == "Reinforcement bars for concrete in a bridge deck"
    assert ctx["candidate_standards"] and "match_score" in ctx["candidate_standards"][0]


def test_grounded_pipeline_llm_path(monkeypatch, tmp_path, no_llm):
    """With a fake LLM, the explanation is generated over the grounded context.
    (no_llm patches requirement.*'s llm_complete import chain to fail; the
    pipeline-level llm_complete is then monkeypatched to the fake.)"""
    import app.services.llm as llm_mod

    seen = {}

    def fake_llm(system, user, *, max_tokens=0, temperature=0.0):
        seen["system"] = system
        seen["user"] = user
        return "Explained from grounded context."

    monkeypatch.setattr(llm_mod, "llm_complete", fake_llm)
    # pipeline imported llm_complete by name too:
    monkeypatch.setattr(pipeline, "llm_complete", fake_llm, raising=False)
    monkeypatch.setattr(external_sources, "CACHE_FILE", tmp_path / "ext_cache.json")
    out = pipeline.grounded_recommend("cement for a government road project", top_k=3)
    assert out["explanation"] == "Explained from grounded context."
    assert out["explanation_source"] == "llm"
    # The grounding rule must be in the system prompt (task §22).
    assert "source of truth" in seen["system"]
    # The grounded context (not just the raw query) is what the LLM sees.
    assert "candidate_standards" in seen["user"]


def test_deterministic_explanation_never_empty(no_llm, tmp_path, monkeypatch):
    monkeypatch.setattr(external_sources, "CACHE_FILE", tmp_path / "ext_cache.json")
    out = pipeline.grounded_recommend("PVC insulated electrical cable 1.1kV", top_k=3)
    det = pipeline.deterministic_explanation(out)
    assert det and "Top match" in det


# -------------------------------------------------------------------- llm api --

def test_grounded_endpoint_works(client, no_llm, monkeypatch, tmp_path):
    monkeypatch.setattr(external_sources, "CACHE_FILE", tmp_path / "ext_cache.json")
    r = client.post("/api/procure/grounded-recommend", json={"query": "cement for a bridge", "top_k": 3})
    assert r.status_code == 200
    data = r.json()
    assert data["recommendations"] and data["explanation"]
    assert data["external_retrieval"]["calls"] >= 0


def test_grounded_endpoint_empty_query_422(client):
    assert client.post("/api/procure/grounded-recommend", json={"query": "  "}).status_code == 422


def test_requirement_endpoint(client, no_llm):
    r = client.get("/api/procure/requirement-understanding", params={"q": "cement for a road"})
    assert r.status_code == 200
    d = r.json()
    assert d["interpreted_requirement"]["product"] == "cement"


def test_no_secret_in_responses(client, no_llm, monkeypatch, tmp_path):
    """HF_TOKEN must never leak through any API response."""
    monkeypatch.setattr(external_sources, "CACHE_FILE", tmp_path / "ext_cache.json")
    r = client.post("/api/procure/grounded-recommend", json={"query": "steel beams", "top_k": 2})
    assert "hf_" not in r.text.lower().replace("hf token", "")
