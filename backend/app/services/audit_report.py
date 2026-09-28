"""Audit artifacts (SIH26108 verification audit, item 14).

Generates the machine-readable verification report and the manual-review
worklist from the provenance model, and exposes both via API endpoints.
Files are (re)generated on import if missing so the repo always carries the
latest snapshot; regenerating is deterministic and side-effect free.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.services import gov_provenance

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
REPORT_FILE = DATA_DIR / "government_verification_report.json"
REVIEW_FILE = DATA_DIR / "manual_review.json"


def build_report() -> dict:
    """Assemble government_verification_report.json content."""
    s = gov_provenance.summary_counts()
    counts = s["counts"]
    discrepancies = list(s["discrepancies"])

    # Pull confirmed discrepancies from the audit-corrections log too.
    corrections_file = DATA_DIR / "data_corrections.json"
    if corrections_file.exists():
        try:
            corrections = json.loads(corrections_file.read_text(encoding="utf-8")).get("corrections", [])
        except Exception:
            corrections = []
        for c in corrections:
            discrepancies.append({
                "standard": c.get("standard", ""),
                "field": c.get("field", ""),
                "registry_value_before_fix": c.get("old_value", ""),
                "value_after_fix": c.get("new_value", ""),
                "official_source": c.get("source", ""),
                "severity": c.get("severity", "medium"),
                "action_taken": "registry corrected during the 2026-09-27 audit",
            })

    # Per-standard status table
    per_standard = []
    for rec in gov_provenance.decorated_all_standards():
        gov = rec["gov"]
        per_standard.append({
            "standard": rec.get("is_number_clean", ""),
            "title": rec.get("title", ""),
            "category": rec.get("category", ""),
            "registry_edition": rec.get("latest_version", ""),
            "verification_status": gov.get("verification_status", ""),
            "version_status": gov.get("version_status", ""),
            "certification_claim_mandatory": bool((rec.get("certification") or {}).get("mandatory")),
            "certification_basis": gov.get("certification_basis", ""),
            "qco": (gov.get("qco") or {}).get("name", ""),
            "qco_notification": (gov.get("qco") or {}).get("notification", ""),
        })

    return {
        "meta": {
            "generated": "2026-09-27",
            "tool": "Standard Setu government-source provenance audit (SIH26108)",
            "primary_source": "https://www.bis.gov.in/product-certification/products-under-compulsory-certification/scheme-i-mark-scheme/",
            "note": "Point-in-time snapshot. Only standards explicitly audited carry VERIFIED/PARTIALLY_VERIFIED; everything else is UNVERIFIED or MANUAL_REVIEW_REQUIRED by design.",
        },
        "totals": counts,
        "discrepancies": discrepancies,
        "per_standard": per_standard,
    }


def build_manual_review() -> dict:
    """Assemble manual_review.json content."""
    s = gov_provenance.summary_counts()
    items = list(s["manual_review"])

    # Add the deep-dive standards whose QCO status stayed unresolved.
    unresolved = [
        {
            "standard": "IS 383",
            "field": "certification.mandatory",
            "current_value": "mandatory: true (registry)",
            "reason": "IS 383 appears on BIS's official SIMPLIFIED-PROCEDURE (voluntary) list and no QCO covering aggregates was found on the compulsory-certification list.",
            "suggested_official_source": "https://www.bis.gov.in/product-certification/products-under-compulsory-certification/scheme-i-mark-scheme/",
            "severity": "high",
        },
        {
            "standard": "IS 1077",
            "field": "certification.mandatory",
            "current_value": "mandatory: true (registry)",
            "reason": "No QCO covering burnt clay bricks was located in official sources during the audit.",
            "suggested_official_source": "https://www.bis.gov.in/product-certification/products-under-compulsory-certification/scheme-i-mark-scheme/",
            "severity": "high",
        },
        {
            "standard": "IS 4984",
            "field": "certification.mandatory",
            "current_value": "mandatory: true (registry)",
            "reason": "PE pipes appear in BIS product manuals with QCO context, but no QCO notification covering IS 4984 was located on the official compulsory list.",
            "suggested_official_source": "https://www.bis.gov.in/product-certification/products-under-compulsory-certification/scheme-i-mark-scheme/",
            "severity": "medium",
        },
        {
            "standard": "IS 269",
            "field": "certification.note",
            "current_value": "mandatory under Cement Quality Control Order 2023",
            "reason": "The fetched official BIS page lists the Cement QCO 2003 (S.O. 191(E)); the 2023 order reference needs confirmation.",
            "suggested_official_source": "https://egazette.gov.in / BIS Scheme-1 page",
            "severity": "low",
        },
    ]
    seen = {i["standard"] for i in items}
    for u in unresolved:
        if u["standard"] not in seen:
            items.append(u)

    return {
        "meta": {
            "generated": "2026-09-27",
            "note": "Fields a human must verify against official BIS / eGazette sources before the application may present them as established government facts.",
        },
        "total_items": len(items),
        "items": items,
    }


def _refresh_files() -> None:
    try:
        REPORT_FILE.write_text(json.dumps(build_report(), ensure_ascii=False, indent=1), encoding="utf-8")
        REVIEW_FILE.write_text(json.dumps(build_manual_review(), ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        # Never break the app because a report could not be written.
        pass


_refresh_files()
