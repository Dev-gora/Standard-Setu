"""Issue attribution in the tender risk overview.

Regression for: "every issue in a tender was automatically assigned to the
first cited standard". Issues must carry the standard they actually CONCERN;
issues that cannot be mapped to a standard (unparseable documents etc.) are
batch-level findings, never guessed onto a citation.
"""

from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import BulkCheckIssue, FileCheckResult
from app.services import demand_rating
from app.services import tender_check

client = TestClient(app)


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


def test_each_issue_attribution_names_its_own_standard():
    """One document, three problems on three different standards.

    The unknown code is cited FIRST — under the old behaviour every issue
    below was pinned to it. Each issue must now name the standard it concerns.
    """
    text = "Supply of materials per IS 99999, IS 269:1950 and IS 1786."
    result = tender_check.check_tender_text("t.pdf", text)
    std_by_kind: dict[str, list[str]] = {}
    for iss in result.issues:
        std_by_kind.setdefault(iss.kind, []).append(iss.standard)

    # The unknown code was cited FIRST — under the old behaviour every issue
    # was pinned to it. Attribution must instead name the standard concerned.
    assert "IS 99999" in std_by_kind.get("unknown_standard", [])
    # Outdated attribution keeps the citation as written ('IS 269:1950') so the
    # UI can show exactly what the document wrongly cited.
    assert any(s.startswith("IS 269") for s in std_by_kind.get("outdated_version", []))
    # IS 1786 must have its own issue (cert language missing), attributed to
    # IS 1786 — whatever provenance-backed kind applies.
    is1786_kinds = [iss.kind for iss in result.issues if iss.standard == "IS 1786"]
    assert is1786_kinds and set(is1786_kinds) <= {
        "missing_certification", "certification_unverified", "generic_certification_language",
    }
    # Every issue in this document is attributable to a specific standard.
    assert all(iss.standard for iss in result.issues)
    assert not any(iss.batch_level for iss in result.issues)


def test_unparseable_document_is_batch_level_not_pinned():
    """No text -> no citation to blame; the issue must be batch-level."""
    result = tender_check.check_tender_text("scanned.pdf", "   ")
    assert result.status == "error"
    assert len(result.issues) == 1
    iss = result.issues[0]
    assert iss.kind == "unparseable"
    assert iss.batch_level is True
    assert iss.standard == ""


def test_batch_issues_aggregated_in_api_response():
    """Unattributable issues roll up to the batch, with the file list."""
    good = _make_simple_pdf("Tender for supply per IS 1786:2008")
    files = [
        ("files", ("good.pdf", good, "application/pdf")),
        ("files", ("scanned1.pdf", b"%PDF-1.4 garbage", "application/pdf")),
        ("files", ("scanned2.pdf", b"%PDF-1.4 garbage", "application/pdf")),
    ]
    r = client.post("/api/procure/bulk-check", files=files)
    assert r.status_code == 200
    body = r.json()

    batch = body["batch_issues"]
    unparseable = [b for b in batch if b["kind"] == "unparseable"]
    assert unparseable, "two unreadable documents must produce a batch finding"
    assert unparseable[0]["count"] == 2
    assert set(unparseable[0]["files"]) == {"scanned1.pdf", "scanned2.pdf"}
    assert unparseable[0]["detail"]

    # Per-file issues stay attributed: no guessed standards anywhere.
    for f in body["files"]:
        for iss in f["issues"]:
            if iss["kind"] != "unparseable":
                assert iss.get("standard"), (f["file_name"], iss)


def test_demand_rating_pressure_uses_explicit_attribution():
    """Issue pressure lands on the standard the issue CONCERNS."""
    r1 = FileCheckResult(
        file_name="a.pdf", status="review",
        standards_cited=["IS 1786", "IS 269"],
        issues=[BulkCheckIssue(kind="outdated_version", standard="IS 269", detail="x")],
    )
    rated = {row["standard"]: row for row in demand_rating.rate_demand([r1], 1)}

    # The pressure is IS 269's, even though IS 1786 was cited first.
    assert "1 citation issue(s)" in rated["IS 269"]["availability_note"]
    assert "citation issue" not in rated["IS 1786"]["availability_note"]


def test_demand_rating_ignores_unattributable_issues():
    """Batch-level issues must not inflate any standard's row — they are
    captured by batch_level_issues() instead."""
    r1 = FileCheckResult(
        file_name="a.pdf", status="error",
        standards_cited=[],
        issues=[BulkCheckIssue(kind="unparseable", batch_level=True, detail="no text")],
    )
    assert demand_rating.rate_demand([r1], 1) == []
    batch = demand_rating.batch_level_issues([r1])
    assert [b["kind"] for b in batch] == ["unparseable"]
    assert batch[0]["files"] == ["a.pdf"] and batch[0]["count"] == 1
