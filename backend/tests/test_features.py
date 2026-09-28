"""P0/P1 backend feature tests — honesty guarantees are the main subject.

These tests pin down the behaviour that makes Standard Setu auditable:
- Match Score factors come from real pipeline signals (semantic present only
  when embeddings are available).
- Citations are never invented: unindexed documents report
  source_document_not_indexed; page/clause come only from the built index.
- Licence verification never claims success without a real portal response.
- Watchlist change detection is deterministic from registry snapshots.
- Risk levels derive strictly from deterministic findings.
"""

from __future__ import annotations

import json

import pytest


# ── P0-1 Explainable Match Score ─────────────────────────────────────────────

def test_recommend_includes_match_breakdown(client):
    r = client.post("/api/procure/recommend",
                    json={"query": "Reinforcement bars for concrete in a bridge deck"})
    assert r.status_code == 200
    data = r.json()
    rec = data["recommendations"][0]
    assert rec["match"] is not None
    m = rec["match"]
    assert 0 <= m["score"] <= 100
    labels = {f["label"] for f in m["factors"]}
    assert "Keyword match" in labels
    assert "Product category" in labels
    assert m["embedding_mode"] in ("semantic", "keyword_only")
    assert m["confidence"] in ("High", "Medium", "Low")


def test_match_factors_never_invent_semantic_signal(client):
    """Factor labels must match what the pipeline actually computed."""
    from app.services import standards_registry as registry

    hits = registry.search_registry("cement for concrete works", top_k=2)
    assert hits
    from app.services.scoring import score_breakdown

    m = score_breakdown("cement for concrete works", hits[0], hits[0]["_score"])
    labels = {f.label for f in m.factors}
    has_semantic = hits[0].get("_semantic") is not None
    assert ("Semantic relevance" in labels) == has_semantic


# ── P0-2 Evidence / citations ────────────────────────────────────────────────

def test_evidence_is_indexed_standard_returns_real_pages(client):
    r = client.get("/api/procure/evidence/IS 1786", params={"query": "chemical composition"})
    assert r.status_code == 200
    claims = r.json()
    assert claims
    scope = next(c for c in claims if c["kind"] == "scope")
    ev = scope["evidence"]
    # From the actual built index over reference/bis_pdfs/1786*.pdf
    assert ev["available"] is True
    assert ev["page"] is not None and ev["page"] >= 1
    assert ev["document"].endswith(".pdf")
    if ev["clause"]:
        assert ev["clause"].replace(".", "").isdigit() or ev["clause"].lower().startswith("annex")


def test_evidence_unindexed_standard_never_invents(client):
    r = client.get("/api/procure/evidence/IS 1239")
    assert r.status_code == 200
    claims = r.json()
    assert claims
    for c in claims:
        ev = c["evidence"]
        assert ev["available"] is False
        assert ev["page"] is None and ev["clause"] is None
        # Audit renamed the QCO reason: qco_source_not_verified (provenance-aware).
        assert ev["unavailable_reason"] in (
            "source_document_not_indexed", "qco_source_not_indexed", "qco_source_not_verified"
        )


def test_evidence_unknown_standard_404(client):
    r = client.get("/api/procure/evidence/IS 999999")
    assert r.status_code == 404


# ── P0-3 BIS licence verification ────────────────────────────────────────────

def test_verify_rejects_bad_format_without_network(client):
    r = client.post("/api/procure/verify", json={"licence_number": "not-a-licence"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "invalid"
    assert body["last_verified"]  # still timestamped


def test_verify_result_has_timestamp_and_source(client):
    r = client.post("/api/procure/verify",
                    json={"licence_number": "CM/L-8700123456", "supplier_name": "Test Steel",
                          "is_number": "IS 1786"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("valid", "invalid", "expired", "not_found",
                              "unable_to_verify", "source_unavailable")
    assert body["last_verified"]
    assert "BIS" in body["source"]


def test_verify_caches_result(client):
    payload = {"licence_number": "CM/L-8700123999"}
    r1 = client.post("/api/procure/verify", json=payload).json()
    r2 = client.post("/api/procure/verify", json=payload).json()
    # Second identical call must be served from cache (no second network hit).
    assert r2["cached"] is True
    assert r2["status"] == r1["status"]


# ── P0-4 Audit history ───────────────────────────────────────────────────────

def test_recommendation_recorded_in_history(client):
    r = client.post("/api/procure/recommend",
                    json={"query": "Portland cement for slab casting OPC 53 grade"})
    assert r.status_code == 200
    history = client.get("/api/procure/history").json()
    assert history["total"] >= 1
    entry = history["entries"][0]
    assert entry["kind"] == "recommendation"
    assert entry["query"] == "Portland cement for slab casting OPC 53 grade"
    payload = entry["payload"]
    assert "candidates" in payload and payload["candidates"]


def test_history_detail_endpoint(client):
    # Self-sufficient: record an event first rather than assuming prior state.
    client.post("/api/procure/recommend", json={"query": "reinforcement steel bars rebar"})
    history = client.get("/api/procure/history").json()
    assert history["entries"], "expected at least one recorded event"
    eid = history["entries"][0]["id"]
    r = client.get(f"/api/procure/history/{eid}")
    assert r.status_code == 200
    assert r.json()["id"] == eid
    assert client.get("/api/procure/history/does-not-exist").status_code == 404


# ── P0-5 Watchlist + change detection ────────────────────────────────────────

def test_watch_add_list_remove(client):
    r = client.post("/api/procure/watchlist", json={"is_number": "IS 1786"})
    assert r.status_code == 200
    assert r.json()["is_number"] == "IS 1786"
    assert r.json()["baseline"].get("latest_version")

    wl = client.get("/api/procure/watchlist").json()
    assert wl["total"] == 1
    assert wl["items"][0]["is_number"] == "IS 1786"

    d = client.delete("/api/procure/watchlist/IS 1786")
    assert d.status_code == 200
    assert client.get("/api/procure/watchlist").json()["total"] == 0


def test_watch_unknown_standard_404(client):
    assert client.post("/api/procure/watchlist", json={"is_number": "IS 999999"}).status_code == 404


def test_change_detection_is_deterministic(client, monkeypatch):
    """Amending the registry must produce exactly one notification, once."""
    from app.services import store

    client.post("/api/procure/watchlist", json={"is_number": "IS 1786"})
    before = client.get("/api/procure/notifications").json()["unread"]

    # Simulate an authoritative registry update (deterministic, no network).
    real = store.registry.get_by_is_number

    def amended(code):
        rec = real(code)
        if rec and rec["core_number"] == "1786":
            rec = dict(rec)
            rec["amendment"] = "Amendment 3 (2027)"
        return rec

    monkeypatch.setattr(store.registry, "get_by_is_number", amended)
    new = store.check_watchlist()
    assert len(new) == 1
    assert new[0]["is_number"] == "IS 1786"
    assert "Amendment 3" in new[0]["change"]

    after = client.get("/api/procure/notifications").json()
    assert after["unread"] == before + 1

    # A second check with no further change must NOT re-alert.
    again = store.check_watchlist()
    assert again == []


# ── P1-1 Comparison ──────────────────────────────────────────────────────────

def test_compare_matrix_from_registry(client):
    r = client.post("/api/procure/compare",
                    json={"codes": ["IS 1786", "IS 2062"], "query": "reinforcement steel"})
    assert r.status_code == 200
    body = r.json()
    assert len(body["columns"]) == 2
    col = body["columns"][0]
    assert col["found"] is True
    assert col["latest_version"]
    assert col["certification"] is not None
    assert col["match_score"] is None or 0 <= col["match_score"] <= 100


def test_compare_reports_unknown_codes_honestly(client):
    r = client.post("/api/procure/compare",
                    json={"codes": ["IS 1786", "IS 9999"]})
    assert r.status_code == 200
    cols = {c["code"]: c for c in r.json()["columns"]}
    assert cols["IS 9999"]["found"] is False


def test_compare_enforces_2_to_5(client):
    assert client.post("/api/procure/compare", json={"codes": ["IS 1786"]}).status_code == 422
    many = [f"IS {1786 + i}" for i in range(6)]
    assert client.post("/api/procure/compare", json={"codes": many}).status_code == 422


# ── P1-7 Risk heatmap ────────────────────────────────────────────────────────

def test_bulk_check_produces_risk_heatmap(client):
    # Minimal but valid PDF with a cited standard and no certification language.
    pdf = _make_simple_pdf("Tender for supply per IS 1786:2008")
    files = {"files": ("t1.pdf", pdf, "application/pdf")}
    r = client.post("/api/procure/bulk-check", files=files)
    assert r.status_code == 200
    body = r.json()
    assert body["risk"] is not None
    dims = {d["dimension"]: d for d in body["risk"]["files"][0]["dimensions"]}
    assert "Certification" in dims
    assert "Standard validity" in dims
    # IS 1786:2008 cited; latest is 2008+amendments — outdated only if year < latest year.
    cert = dims["Certification"]
    assert cert["level"] in ("low", "medium", "high")
    if cert["level"] != "low":
        assert cert["action"]


def _make_simple_pdf(text: str) -> bytes:
    """Tiny valid one-page PDF containing the given text (no deps)."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objects.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>")
    objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF").encode()
    return bytes(out)


# ── P1-8 OCR fallback ────────────────────────────────────────────────────────

def test_ocr_reports_honest_unavailability(client):
    from app.services import ocr

    info = ocr.availability()
    assert info["available"] in (True, False)
    if not info["available"]:
        assert info["reason"]
        result = ocr.ocr_pdf(b"%PDF-not-a-real-pdf")
        assert result["used"] is False
        assert "unavailable" in result["message"].lower() or "failed" in result["message"].lower()


def test_scanned_pdf_reports_ocr_status(client):
    # A PDF page with no text layer: the checker should attempt OCR (or
    # honestly report its unavailability) instead of a bare failure.
    pdf = _make_simple_pdf("x")  # minimal text won't trigger; craft empty-text case
    pdf = pdf.replace(b"(x)", b"()")  # empty text run -> effectively no text layer
    files = {"files": ("scanned.pdf", pdf, "application/pdf")}
    r = client.post("/api/procure/bulk-check", files=files)
    assert r.status_code == 200
    result = r.json()["files"][0]
    assert result["status"] in ("error", "review")
    if not result["ocr"]:  # OCR attempted only when text extraction is thin
        assert result["issues"]


# ── P1-9 Version comparison ─────────────────────────────────────────────────

def test_versions_honest_when_single_edition(client):
    r = client.get("/api/procure/versions/IS 1786")
    assert r.status_code == 200
    body = r.json()
    if not body["available"]:
        assert "not indexed" in body["message"].lower()
        assert body["sections"] == []


def test_versions_unknown_code_still_honest(client):
    r = client.get("/api/procure/versions/IS 999999")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is False
    assert "not indexed" in body["message"].lower()


# ── P1-10 Unified report ─────────────────────────────────────────────────────

def test_report_assembles_all_stages(client):
    r = client.post("/api/procure/report",
                    json={"query": "Reinforcement bars for concrete in a bridge deck", "code": "IS 1786"})
    assert r.status_code == 200
    rep = r.json()
    assert rep["standard"]["is_number"] == "IS 1786"
    assert rep["match"] is not None and 0 <= rep["match"]["score"] <= 100
    assert rep["evidence"]
    assert rep["tender_block"]
    assert rep["risk_notes"]
    assert rep["generated_at"]


def test_report_unknown_code_404(client):
    r = client.post("/api/procure/report", json={"query": "anything", "code": "IS 999999"})
    assert r.status_code == 404


# ── Privacy: session data deletion ──────────────────────────────────────

def test_session_data_purge(client):
    """Events recorded with a session id are deleted by the purge endpoint."""
    sid = "test-session-123"
    # Record via a real recommend call carrying the session header.
    r = client.post("/api/procure/recommend",
                    json={"query": "reinforcement steel bars rebar"},
                    headers={"X-Session-Id": sid})
    assert r.status_code == 200

    # Session-scoped history shows the entry.
    hist = client.get("/api/procure/history", headers={"X-Session-Id": sid}).json()
    assert any(e["session_id"] == sid for e in hist["entries"])

    # Purge deletes it.
    r = client.delete("/api/procure/session-data", headers={"X-Session-Id": sid})
    assert r.status_code == 200
    assert r.json()["cleared"] is True

    hist_after = client.get("/api/procure/history", headers={"X-Session-Id": sid}).json()
    assert not any(e["session_id"] == sid for e in hist_after["entries"])


# ── Existing functionality preserved ────────────────────────────────────────

def test_existing_endpoints_unchanged(client):
    assert client.get("/api/procure/health").json()["status"] == "healthy"
    meta = client.get("/api/procure/meta").json()
    assert meta["registry"]["count"] == 130
    assert "cement" in " ".join(meta["categories"]).lower()
    r = client.post("/api/procure/recommend", json={"query": "Steel for a warehouse structure"})
    assert r.status_code == 200
    data = r.json()
    assert data["clarify_needed"] is True and data["clarify"]["options"]
