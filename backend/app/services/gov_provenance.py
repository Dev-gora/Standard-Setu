"""Government-source provenance model (SIH26108 audit).

Every government-related value exposed by the API (mandatory certification,
QCO backing, latest-edition claims) is decorated with an explicit
verification status instead of silently inheriting the curated registry's
authority.

Statuses (explicit, per the audit brief):
  VERIFIED              - an official BIS / GoI source was actually checked and supports the value
  PARTIALLY_VERIFIED    - an official source supports part of the claim (e.g. the QCO covers
                          the product, but the edition was confirmed only via a public mirror)
  UNVERIFIED            - no authoritative source checked or located
  SOURCE_UNAVAILABLE    - verification was attempted but the source could not be reached
  OUTDATED_REGISTRY     - the registry value conflicts with an official source (registry is stale)
  MANUAL_REVIEW_REQUIRED- a human must check this before the value may be relied upon

Data flow:
  backend/data/government_sources.json  - point-in-time audit snapshot (the ONLY source of
                                          VERIFIED / PARTIALLY_VERIFIED statuses)
  backend/data/standards_registry.json  - curated dataset; certification.mandatory is treated
                                          as a CLAIM, never as a fact.

This module never mutates the registry; it decorates. The registry remains the
source of titles/scopes/search text (curation), while government claims carry
their own explicit status.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
GOV_SOURCES_FILE = DATA_DIR / "government_sources.json"

# Explicit status vocabulary (audit brief section 7).
VERIFIED = "VERIFIED"
PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
UNVERIFIED = "UNVERIFIED"
SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
OUTDATED_REGISTRY = "OUTDATED_REGISTRY"
MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
NOT_FOUND_ON_COMPULSORY_LIST = "NOT_FOUND_ON_COMPULSORY_LIST"

VALID_STATUSES = {
    VERIFIED, PARTIALLY_VERIFIED, UNVERIFIED, SOURCE_UNAVAILABLE,
    OUTDATED_REGISTRY, MANUAL_REVIEW_REQUIRED, NOT_FOUND_ON_COMPULSORY_LIST,
}


@lru_cache(maxsize=1)
def _gov_sources() -> dict:
    """The audit snapshot: standard key -> {verification_status, qco{...}, ...}."""
    if not GOV_SOURCES_FILE.exists():
        return {}
    try:
        data = json.loads(GOV_SOURCES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: dict[str, dict] = {}
    for key, entry in (data.get("standards") or {}).items():
        # Normalize the key the same way the registry resolver normalizes codes,
        # so 'IS 1489 (Part 2)' and 'IS 1489 Part 2 : 2015' both hit.
        norm = _norm_key(key)
        if norm:
            out[norm] = entry
    return out


def _norm_key(code: str) -> str:
    """Normalize any IS citation to the audit-key form (structural parse).

    'is 1489 part 2 : 2015' / 'IS 1489 (Part 2):2015' -> 'IS 1489 (PART 2)'
    'IS 2062:2011' -> 'IS 2062'

    Structural, not year-stripping: IS numbers themselves can look like years
    (IS 2062, IS 1993), so a bare regex would destroy them.
    """
    import re
    s = re.sub(r"\s+", " ", (code or "").strip().upper()).replace("IS:", "IS ")
    m = re.match(
        r"^IS\s*:?\s*(\d{2,6})"
        r"(?:\s*\(\s*PART\s*(\d+)\s*\)|\s+PART\s+(\d+))?",
        s,
    )
    if not m:
        return s
    core = f"IS {m.group(1)}"
    part = m.group(2) or m.group(3)
    return f"{core} (PART {part})" if part else core


def gov_record(code: str) -> dict | None:
    """The audit entry for a standard, or None when never government-checked."""
    return _gov_sources().get(_norm_key(code))


def _core_norm(core_number: str) -> str | None:
    if not core_number:
        return None
    return f"IS {core_number.strip()}"


def provenance_for(record: dict) -> dict:
    """Build the provenance block for one registry record.

    Returns a dict with:
      verification_status, source, source_url, source_title, verified_at, notes,
      version_status, gov_edition, qco{status,name,notification,source_url},
      certification_basis (VERIFIED | UNVERIFIED | NOT_ESTABLISHED | ...)
    """
    code = record.get("is_number_clean", "") or _core_norm(record.get("core_number", "")) or ""
    entry = gov_record(code) or gov_record(record.get("is_number", ""))
    if not entry:
        # No government check on file: everything stays a curated claim.
        cert = record.get("certification") or {}
        if cert.get("mandatory"):
            cert_status = MANUAL_REVIEW_REQUIRED
            cert_note = (
                "Curated dataset claims mandatory certification but no official "
                "QCO/notification has been verified for this standard yet."
            )
        else:
            cert_status = UNVERIFIED
            cert_note = "Curated dataset says certification is not mandatory; not government-verified."
        return {
            "verification_status": UNVERIFIED,
            "version_status": UNVERIFIED,
            "source": "Curated dataset (standards_registry.json) - not government-verified",
            "source_url": "",
            "source_title": "",
            "verified_at": "",
            "notes": [],
            "gov_edition": "",
            "qco": {"status": UNVERIFIED, "name": "", "notification": "", "source_url": ""},
            "certification_basis": cert_status,
            "certification_note": cert_note,
        }

    cert = record.get("certification") or {}
    qco = entry.get("qco") or {}
    basis = entry.get("certification_basis", UNVERIFIED)
    qco_status = qco.get("status", UNVERIFIED)

    if basis == VERIFIED and cert.get("mandatory"):
        cert_status = VERIFIED
        cert_note = f"Mandatory via {qco.get('name') or 'official BIS list'} ({qco.get('notification', '')})."
    elif qco_status in (NOT_FOUND_ON_COMPULSORY_LIST, UNVERIFIED) and cert.get("mandatory"):
        cert_status = MANUAL_REVIEW_REQUIRED
        cert_note = (
            "Curated dataset claims mandatory certification, but no QCO/notification "
            "backing it was located in official sources during the audit. Treat as "
            "MANUAL_REVIEW_REQUIRED until a government source is produced."
        )
    elif not cert.get("mandatory"):
        cert_status = UNVERIFIED
        cert_note = "Curated dataset says certification is not mandatory; not government-verified."
    else:
        cert_status = PARTIALLY_VERIFIED
        cert_note = qco.get("name", "")

    return {
        "verification_status": entry.get("verification_status", UNVERIFIED),
        "version_status": entry.get("version_status", UNVERIFIED),
        "source": "Official BIS / Government of India sources (audit snapshot)",
        "source_url": qco.get("source_url", ""),
        "source_title": "BIS Scheme-1 compulsory certification list / BIS product manuals",
        "verified_at": entry.get("verified_at", ""),
        "notes": entry.get("notes", []),
        "gov_edition": entry.get("gov_edition", ""),
        "qco": {
            "status": qco_status,
            "name": qco.get("name", ""),
            "notification": qco.get("notification", ""),
            "source_url": qco.get("source_url", ""),
        },
        "certification_basis": cert_status,
        "certification_note": cert_note,
    }


def decorate(record: dict) -> dict:
    """Return a shallow copy of a registry record with a 'gov' provenance block."""
    out = dict(record)
    out["gov"] = provenance_for(record)
    return out


def decorated_all_standards() -> list[dict]:
    """All registry records with their provenance block attached."""
    from app.services import standards_registry as registry

    return [decorate(r) for r in registry.all_standards()]


def summary_counts() -> dict:
    """Audit summary across the whole registry (for the verification report)."""
    counts = {
        "total": 0, "verified": 0, "partially_verified": 0, "unverified": 0,
        "outdated": 0, "source_unavailable": 0, "manual_review_required": 0,
        "mandatory_claims_total": 0,
        "mandatory_claims_qco_backed": 0,
        "mandatory_claims_manual_review": 0,
    }
    discrepancies: list[dict] = []
    manual_review: list[dict] = []

    for rec in decorated_all_standards():
        counts["total"] += 1
        gov = rec["gov"]
        status = gov.get("verification_status", UNVERIFIED)
        if status == VERIFIED:
            counts["verified"] += 1
        elif status == PARTIALLY_VERIFIED:
            counts["partially_verified"] += 1
        elif status == MANUAL_REVIEW_REQUIRED:
            counts["manual_review_required"] += 1
        elif status == OUTDATED_REGISTRY:
            counts["outdated"] += 1
        elif status == SOURCE_UNAVAILABLE:
            counts["source_unavailable"] += 1
        else:
            counts["unverified"] += 1

        cert = rec.get("certification") or {}
        if cert.get("mandatory"):
            counts["mandatory_claims_total"] += 1
            basis = gov.get("certification_basis")
            if basis == VERIFIED:
                counts["mandatory_claims_qco_backed"] += 1
            elif basis == MANUAL_REVIEW_REQUIRED:
                counts["mandatory_claims_manual_review"] += 1
                qco = gov.get("qco") or {}
                manual_review.append({
                    "standard": rec.get("is_number_clean", ""),
                    "field": "certification.mandatory",
                    "current_value": "mandatory: true",
                    "reason": "No QCO/government notification located that makes this mandatory.",
                    "suggested_official_source": "https://www.bis.gov.in/product-certification/products-under-compulsory-certification/scheme-i-mark-scheme/",
                    "severity": "high",
                })
        # Edition mismatch between registry and the audit snapshot
        gov_ed = (gov.get("gov_edition") or "")
        if gov.get("version_status") == OUTDATED_REGISTRY or "previously said" in gov_ed:
            discrepancies.append({
                "standard": rec.get("is_number_clean", ""),
                "field": "latest_version",
                "registry_value": rec.get("latest_version", ""),
                "government_value": gov_ed,
                "severity": "medium",
            })

    return {"counts": counts, "discrepancies": discrepancies, "manual_review": manual_review}
