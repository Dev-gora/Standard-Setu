"""P1-7 — Specification risk heatmap.

Risk levels are derived ONLY from the deterministic findings produced by
tender_check.check_tender_text (issue kinds: unknown_standard,
outdated_version, missing_certification, unparseable). No LLM, no vibes: the
mapping from finding counts to levels is fixed and shown in the code.

Dimensions:
- Standard validity      -> outdated_version findings
- Referenced standards   -> unknown_standard findings
- Certification          -> missing_certification findings
- Document quality       -> unparseable findings / empty extraction
- Specification completeness -> files citing zero known standards
"""

from __future__ import annotations

from app.models.schemas import BulkCheckIssue, FileCheckResult, RiskDimension, RiskResponse, TenderRisk

ACTIONS = {
    "Standard validity": "Update cited editions to the latest versions listed in the registry.",
    "Referenced standards": "Replace or verify codes not covered by the registry; confirm they exist.",
    "Certification": "Add the applicable BIS certification requirement to the specification.",
    "Document quality": "Re-export the document with a text layer or attach a readable copy.",
    "Specification completeness": "Cite at least one applicable Indian Standard for each supplied product.",
}


def _level_from_count(n: int, high: int = 3) -> tuple[str, int]:
    """Deterministic count -> (level, 0-100 severity score)."""
    if n <= 0:
        return "low", 0
    if n == 1:
        return "medium", 40
    if n < high:
        return "medium", 60
    return "high", 85


def _kind_count(issues: list[BulkCheckIssue], kind: str) -> int:
    return sum(1 for i in issues if i.kind == kind)


def file_risk(result: FileCheckResult) -> TenderRisk:
    issues = result.issues or []
    dims: list[RiskDimension] = []

    n_outdated = _kind_count(issues, "outdated_version")
    n_unknown = _kind_count(issues, "unknown_standard")
    n_cert = _kind_count(issues, "missing_certification")
    n_unparseable = _kind_count(issues, "unparseable")

    lvl, sc = _level_from_count(n_outdated)
    dims.append(RiskDimension(
        dimension="Standard validity", level=lvl, score=sc,
        findings=[i.detail for i in issues if i.kind == "outdated_version"][:5],
        action=ACTIONS["Standard validity"] if n_outdated else "",
    ))

    lvl, sc = _level_from_count(n_cert, high=2)
    dims.append(RiskDimension(
        dimension="Certification", level=lvl, score=sc,
        findings=[i.detail for i in issues if i.kind == "missing_certification"][:5],
        action=ACTIONS["Certification"] if n_cert else "",
    ))

    lvl, sc = _level_from_count(n_unknown, high=4)
    dims.append(RiskDimension(
        dimension="Referenced standards", level=lvl, score=sc,
        findings=[i.detail for i in issues if i.kind == "unknown_standard"][:5],
        action=ACTIONS["Referenced standards"] if n_unknown else "",
    ))

    doc_quality_n = n_unparseable + (1 if result.status == "error" and not n_unparseable else 0)
    lvl, sc = _level_from_count(doc_quality_n, high=2)
    dims.append(RiskDimension(
        dimension="Document quality", level=lvl, score=sc,
        findings=[i.detail for i in issues if i.kind == "unparseable"][:5],
        action=ACTIONS["Document quality"] if doc_quality_n else "",
    ))

    completeness_n = 0 if (result.standards_cited or (result.status != "review")) else 1
    lvl, sc = _level_from_count(completeness_n, high=2)
    dims.append(RiskDimension(
        dimension="Specification completeness", level=lvl, score=sc,
        findings=[] if not completeness_n else
        ["No covered Indian Standards were identified in this document."],
        action=ACTIONS["Specification completeness"] if completeness_n else "",
    ))

    score = max((d.score for d in dims), default=0)
    overall = "low" if score <= 10 else ("medium" if score < 85 else "high")
    return TenderRisk(file_name=result.file_name, overall=overall, dimensions=dims)


def assess(files: list[FileCheckResult]) -> RiskResponse:
    risks = [file_risk(r) for r in files]
    if not risks:
        return RiskResponse(files=[], overall="low", summary="No documents assessed.")
    order = {"high": 3, "medium": 2, "low": 1}
    worst = max((order[r.overall] for r in risks), default=1)
    overall = {1: "low", 2: "medium", 3: "high"}[worst]
    flagged = sum(1 for r in risks if r.overall != "low")
    summary = (
        f"{flagged} of {len(risks)} documents carry at least one medium/high risk area. "
        "Levels are derived strictly from the deterministic findings listed per dimension."
    )
    return RiskResponse(files=risks, overall=overall, summary=summary)
