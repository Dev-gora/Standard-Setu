"""P1-10 — Unified procurement recommendation report.

Assembles ONE report object purely from the existing services:
- registry record (WHAT)
- scoring.score_breakdown (WHY - Match Score)
- evidence.build_claim_evidence (EVIDENCE)
- certification info (COMPLIANCE)
- deterministic risk notes derived from the record (RISK)
- the same deterministic tender block builder used by /recommend (ACTION)

No new analysis is invented here: every field is either a registry value or
the output of another service. The frontend renders it print-ready
(window.print()).
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.models.schemas import ReportResponse
from app.services import evidence, scoring, standards_registry as registry
from app.services.scoring import score_breakdown


def _risk_notes(rec: dict) -> list[str]:
    """Deterministic caution notes from registry facts (no speculation)."""
    notes: list[str] = []
    cert = rec.get("certification", {}) or {}
    if cert.get("mandatory"):
        note = f"BIS certification is mandatory ({cert.get('scheme') or 'BIS'})"
        if cert.get("note"):
            note += f" - {cert['note']}"
        notes.append(note + ". Ensure the certification condition appears explicitly in the tender.")
    else:
        notes.append(
            "Certification is not flagged mandatory for this product in the registry; "
            "consider requiring BIS certification as a quality condition."
        )
    if rec.get("amendment"):
        notes.append(f"Edition is amended ({rec['amendment']}) - cite the amendment with the standard.")
    if not evidence._load_index().get("documents", {}).get(rec.get("core_number")):
        notes.append("Source document not indexed - clause/page citations unavailable for this standard.")
    return notes


def build_report(query: str, code: str = "") -> ReportResponse | None:
    """Build the unified report for a query (and optionally a chosen standard)."""
    query = (query or "").strip()
    if not query:
        return None

    if code.strip():
        rec = registry.get_by_is_number(code)
        if rec is None:
            return None
    else:
        hits = registry.search_registry(query, top_k=1)
        if not hits:
            return None
        rec = hits[0]

    hybrid = float(rec.get("_score", 0.0))
    if "_semantic" not in rec:
        # record came from get_by_is_number (no search signals) - re-run the
        # REAL pipeline for the raw query so the Match Score is engine-true.
        rescored = scoring.rescore_record(query, rec)
        if rescored is None:
            return None
        rec, hybrid = rescored

    match = score_breakdown(query, rec, hybrid)
    allied = []
    for entry in registry.allied_standards_for(rec):
        cert = entry.get("certification") or {}
        allied.append({
            "code": entry["code"],
            "title": entry.get("title", ""),
            "category": entry.get("category", ""),
            "purpose": entry.get("purpose", "Related standard"),
            "latest_version": entry.get("latest_version", ""),
            "amendment": entry.get("amendment", ""),
            "certification": cert if cert else None,
            "known": entry.get("known", False),
            "archive_link": (
                registry.archive_link(entry["code"], entry.get("latest_version", ""))
                if entry.get("known") else registry.archive_search_link(entry["code"])
            ),
        })

    evidence_claims = evidence.build_claim_evidence(query, rec, bool(rec.get("certification", {}).get("mandatory")))
    sources: list = []
    seen_urls: set[str] = set()
    for c in evidence_claims:
        ev = c.evidence
        key = (ev.standard, ev.page, ev.clause)
        if key not in seen_urls:
            seen_urls.add(key)
            sources.append(ev)

    from app.routers.procurement import _build_tender_block  # deferred: avoids circular import

    return ReportResponse(
        generated_at=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        query=query,
        standard={
            "is_number": rec["is_number_clean"],
            "title": rec["title"],
            "category": rec["category"],
            "scope_description": rec["scope_description"],
            "latest_version": rec["latest_version"],
            "amendment": rec["amendment"],
            "certification": rec.get("certification", {}),
            "archive_link": registry.archive_link(rec["is_number"], rec["latest_version"]),
            "score": round(hybrid, 3),
        },
        match=match,
        evidence=evidence_claims,
        allied=allied,
        tender_block=_build_tender_block(rec, query),
        risk_notes=_risk_notes(rec),
        sources=sources,
    )
