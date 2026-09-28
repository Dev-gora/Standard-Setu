"""Regression tests for the government-verification audit (SIH26108).

Covers: provenance statuses, version honesty, certification basis logic,
licence states, evidence provenance, and tender certification detection.
These tests supplement (never replace) test_features.py.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.services import gov_provenance
from app.services.verify import (
    LICENCE_STATES,
    licence_format_valid,
    normalize_licence,
)
from app.services.tender_check import check_tender_text


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    return TestClient(app)


# ---------------------------------------------------------------- provenance --

def test_verified_standard_has_qco_backing():
    """IS 2062 was checked against the official BIS Scheme-1 list during the audit."""
    rec = next(r for r in gov_provenance.decorated_all_standards() if r["is_number_clean"] == "IS 2062")
    gov = rec["gov"]
    assert gov["verification_status"] in (gov_provenance.VERIFIED, gov_provenance.PARTIALLY_VERIFIED)
    assert gov["certification_basis"] == gov_provenance.VERIFIED
    assert "Quality Control" in gov["qco"]["name"]
    assert gov["qco"]["source_url"].startswith("https://www.bis.gov.in")


def test_unaudited_standard_is_unverified_not_fake_verified():
    """A standard with no government audit entry must NOT claim VERIFIED."""
    rec = next(r for r in gov_provenance.decorated_all_standards() if r["is_number_clean"] == "IS 1239 (Part 1)")
    gov = rec["gov"]
    assert gov["verification_status"] == gov_provenance.UNVERIFIED
    # Its mandatory claim is exactly that - a claim needing review:
    assert gov["certification_basis"] == gov_provenance.MANUAL_REVIEW_REQUIRED


def test_status_vocabulary_complete():
    valid = {
        gov_provenance.VERIFIED, gov_provenance.PARTIALLY_VERIFIED,
        gov_provenance.UNVERIFIED, gov_provenance.SOURCE_UNAVAILABLE,
        gov_provenance.OUTDATED_REGISTRY, gov_provenance.MANUAL_REVIEW_REQUIRED,
    }
    for rec in gov_provenance.decorated_all_standards():
        assert rec["gov"]["verification_status"] in valid | {gov_provenance.NOT_FOUND_ON_COMPULSORY_LIST}


def test_normalization_hits_part_standards():
    assert gov_provenance.gov_record("IS 1489 (Part 2)") is not None
    assert gov_provenance.gov_record("IS 1489 Part 2 : 2015") is not None
    assert gov_provenance.gov_record("IS 2062:2011") is not None


# ------------------------------------------------------------------- version --

def test_registry_edition_corrected_is_1489_part2():
    """The audit-corrected edition (1991 -> 2015) must stick."""
    rec = next(r for r in gov_provenance.decorated_all_standards() if r["is_number_clean"] == "IS 1489 (Part 2)")
    assert "2015" in rec["latest_version"]
    assert "1991" not in rec["latest_version"]


def test_correction_log_preserves_old_values():
    """Old values survive in data_corrections.json - no silent overwrite."""
    import json
    from pathlib import Path
    p = Path("data/data_corrections.json")
    assert p.exists()
    data = json.loads(p.read_text(encoding="utf-8"))
    corrections = [c for c in data["corrections"] if c["standard"] == "IS 1489 (Part 2)" and c["field"] == "latest_version"]
    assert corrections and corrections[0]["old_value"] == "1991"


def test_gov_edition_distinguished_from_registry_edition():
    """The API exposes version_status + gov_edition separately from latest_version."""
    rec = next(r for r in gov_provenance.decorated_all_standards() if r["is_number_clean"] == "IS 2062")
    assert rec["gov"]["version_status"] in ("GOVERNMENT_VERIFIED", "PARTIALLY_VERIFIED", "CORRECTED_DURING_AUDIT")
    assert "2011" in rec["gov"]["gov_edition"]


# ------------------------------------------------------------- certification --

def test_verified_mandatory_certification_api_response(client):
    """QCO-backed mandatory claims carry basis + source through the API."""
    r = client.get("/api/procure/browse")
    std = next(s for s in r.json()["standards"] if s["code"] == "IS 2062")
    assert std["certification"]["mandatory"] is True
    assert std["certification"]["verification_status"] == "VERIFIED"
    assert "Quality Control" in std["certification"]["basis"]


def test_unverified_mandatory_certification_flagged(client):
    """Mandatory claims without QCO backing say MANUAL_REVIEW_REQUIRED, not VERIFIED."""
    r = client.get("/api/procure/browse")
    std = next(s for s in r.json()["standards"] if s["code"] == "IS 383")
    assert std["certification"]["verification_status"] == "MANUAL_REVIEW_REQUIRED"


def test_recommendation_cert_factor_mentions_provenance():
    from app.services.scoring import score_breakdown
    rec = next(r for r in gov_provenance.decorated_all_standards() if r["is_number_clean"] == "IS 2062")
    bd = score_breakdown("structural steel plates", rec, rec.get("_score", 0.5))
    cert = next(f for f in bd.factors if f.label == "Certification")
    assert "Quality Control" in cert.detail or "manual review" in cert.detail.lower()


# -------------------------------------------------------------------- licence --

def test_licence_format_validation():
    assert licence_format_valid("CM/L-8700123456")
    assert not licence_format_valid("8700123456")
    assert not licence_format_valid("CM/L-12")
    assert normalize_licence("cml 8700123456") == "CM/L-8700123456"


def test_licence_state_mapping_covers_all_states():
    """Every explicit state maps to a legacy API status for compatibility."""
    assert LICENCE_STATES["INVALID_FORMAT"] == "invalid"
    assert LICENCE_STATES["NOT_FOUND"] == "not_found"
    assert LICENCE_STATES["SOURCE_UNAVAILABLE"] == "source_unavailable"
    assert LICENCE_STATES["SOURCE_LOCATED"] == "unable_to_verify"
    assert LICENCE_STATES["VERIFIED_ACTIVE"] == "valid"


def test_licence_verify_never_claims_active_without_evidence(client):
    """A well-formed licence that the portal never confirmed must NOT return 'valid'."""
    r = client.post("/api/procure/verify", json={"licence_number": "CM/L-8700123456", "supplier_name": "Test", "is_number": "IS 1786"})
    data = r.json()
    assert data["status"] != "valid"  # offline test env: source unavailable at best
    assert data["state"] in ("SOURCE_UNAVAILABLE", "NOT_FOUND", "SOURCE_LOCATED", "MANUAL_REVIEW_REQUIRED")
    assert data["source_url"].startswith("https://www.manakonline.in")


# ------------------------------------------------------------------- evidence --

def test_evidence_has_source_type(client):
    r = client.get("/api/procure/evidence/IS 1786")
    assert r.status_code == 200
    for claim in r.json():
        assert claim["evidence"]["source_type"] in (
            "LOCAL_REFERENCE_DOCUMENT", "OFFICIAL_BIS_SOURCE",
            "OFFICIAL_GOVERNMENT_SOURCE", "USER_PROVIDED_DOCUMENT", "UNVERIFIED_SOURCE",
        )


def test_evidence_official_pages_never_fabricated(client):
    """Page/clause only appear when the local index actually resolved them."""
    r = client.get("/api/procure/evidence/IS 99999")
    assert r.status_code == 404  # unknown standard: no invented evidence


def test_certification_claim_wording_matches_provenance():
    from app.services.evidence import build_claim_evidence
    verified_rec = next(r for r in gov_provenance.decorated_all_standards() if r["is_number_clean"] == "IS 2062")
    claims = build_claim_evidence("structural steel", verified_rec, True)
    cert_claim = next(c for c in claims if c.kind == "certification")
    assert "Quality Control" in cert_claim.claim  # QCO-backed wording
    assert cert_claim.evidence.source_type == "OFFICIAL_BIS_SOURCE"

    unverified_rec = next(r for r in gov_provenance.decorated_all_standards() if r["is_number_clean"] == "IS 1077")
    claims2 = build_claim_evidence("bricks", unverified_rec, True)
    cert_claim2 = next(c for c in claims2 if c.kind == "certification")
    assert "no government notification backing it was verified" in cert_claim2.claim
    assert cert_claim2.evidence.source_type == "UNVERIFIED_SOURCE"


# ----------------------------------------------------------------- tender audit --

def test_generic_certification_language_flagged_not_silent():
    """Generic 'certification required' wording is NOT treated as ISI compliance."""
    text = (
        "Supply of TMT bars. All materials must have third party inspection and "
        "quality assurance certification. IS 1786:2008 shall apply."
    )
    result = check_tender_text("t.pdf", text)
    kinds = {i.kind for i in result.issues}
    assert "generic_certification_language" in kinds


def test_missing_cert_language_still_detected_for_qco_backed():
    result = check_tender_text("t.pdf", "Supply shall conform to IS 1786:2008.")
    kinds = {i.kind for i in result.issues}
    assert "missing_certification" in kinds


def test_unverified_mandatory_does_not_fail_tender():
    """Non-QCO-backed mandatory claims must NOT produce missing_certification."""
    text = "Supply shall conform to IS 383:2016."
    result = check_tender_text("t.pdf", text)
    kinds = {i.kind for i in result.issues}
    assert "missing_certification" not in kinds
    assert "certification_unverified" in kinds


def test_specific_licence_language_passes_qco_backed_standard():
    text = "Supply shall conform to IS 1786:2008. Bidders must provide BIS licence number (CM/L-) with ISI mark."
    result = check_tender_text("t.pdf", text)
    kinds = {i.kind for i in result.issues}
    assert "missing_certification" not in kinds
    assert "generic_certification_language" not in kinds


# ------------------------------------------------------------------- reports --

def test_verification_report_endpoint(client):
    r = client.get("/api/procure/verification-report")
    assert r.status_code == 200
    data = r.json()
    assert data["totals"]["total"] == 130
    assert data["totals"]["mandatory_claims_qco_backed"] <= data["totals"]["mandatory_claims_total"]
    assert isinstance(data["discrepancies"], list) and data["discrepancies"]


def test_manual_review_endpoint(client):
    r = client.get("/api/procure/manual-review")
    assert r.status_code == 200
    data = r.json()
    assert data["total_items"] >= 80
    for item in data["items"][:5]:
        assert item["field"] and item["reason"] and item["suggested_official_source"]
