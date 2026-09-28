"""P1-1 — Standard comparison matrix (2-5 standards).

Every cell comes from the registry record itself: edition, amendment,
category, scope, certification, normative references, document-index status.
When the caller supplies the original procurement query, we additionally run
the REAL recommendation pipeline per code and attach the actual Match Score —
the same scoring.py used in /recommend, so the comparison can never show a
number the engine would not produce.
"""

from __future__ import annotations

from app.models.schemas import CompareColumn
from app.services import evidence, scoring, standards_registry as registry
from app.services.scoring import rescore_record


def compare_columns(codes: list[str], query: str = "") -> tuple[list[CompareColumn], list[str]]:
    """Build comparison columns. Unknown codes are returned as found=False
    columns (honest absence) rather than silently dropped."""
    columns: list[CompareColumn] = []
    matched_records: list[tuple[str, dict | None]] = []

    for code in codes:
        rec = registry.get_by_is_number(code)
        matched_records.append((code, rec))

    # Real match scores per code when a query context was provided: each score
    # is what the recommendation pipeline itself would produce for the raw query.
    scores: dict[str, int] = {}
    if query.strip():
        for code, rec in matched_records:
            if rec is None:
                continue
            rescored = rescore_record(query, rec)
            if rescored is not None:
                hit, hybrid = rescored
                scores[rec["is_number_clean"]] = scoring.score_breakdown(query, hit, hybrid).score

    for code, rec in matched_records:
        if rec is None:
            columns.append(CompareColumn(code=code, found=False))
            continue
        doc_indexed = evidence._load_index().get("documents", {}).get(rec["core_number"]) is not None
        columns.append(CompareColumn(
            code=rec["is_number_clean"],
            title=rec["title"],
            found=True,
            latest_version=rec["latest_version"],
            amendment=rec["amendment"],
            category=rec["category"],
            scope_description=rec["scope_description"],
            certification={
                "mandatory": bool(rec["certification"].get("mandatory")),
                "scheme": rec["certification"].get("scheme", ""),
                "note": rec["certification"].get("note", ""),
            },
            normative_refs=list(rec.get("normative_refs", []))[:8],
            match_score=scores.get(rec["is_number_clean"]),
            attributes={
                "Source document": (
                    "Indexed (clause/page citations available)"
                    if doc_indexed else "Not indexed"
                ),
                "Normative references": (
                    f"{len(rec.get('normative_refs', []))} referenced"
                    if rec.get("normative_refs") else "None recorded"
                ),
            },
        ))

    attributes = ["Certification", "Category", "Current edition", "Amendment",
                  "Source document", "Normative references", "Match score"]
    return columns, attributes
