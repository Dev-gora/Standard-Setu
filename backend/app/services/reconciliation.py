"""Local vs external reconciliation (task §12-§13, §26).

Compares provenance-carrying external facts against local registry values
and emits explicit discrepancies. NEVER mutates local data.

Discrepancy types: EDITION_MISMATCH, REVISION_MISMATCH, AMENDMENT_MISMATCH,
REAFFIRMATION_MISMATCH, TITLE_MISMATCH, SCOPE_MISMATCH, CERTIFICATION_MISMATCH,
QCO_MISMATCH, SOURCE_CONFLICT, MISSING_LOCAL_DATA, MISSING_EXTERNAL_DATA.

Verification states: VERIFIED | PARTIALLY_VERIFIED | UNVERIFIED |
SOURCE_UNAVAILABLE | OUTDATED_REGISTRY | MANUAL_REVIEW_REQUIRED.
"""

from __future__ import annotations

import json
import re

from app.services import gov_provenance

_YEAR_RE = re.compile(r"(19|20)\d{2}")


def _norm_code(code: str) -> str:
    m = re.match(r"^IS\s*:?\s*(\d{2,6})", (code or "").upper().replace("IS:", "IS "))
    return f"IS {m.group(1)}" if m else (code or "").upper().strip()


def _registry_value(record: dict, field: str) -> str:
    if field == "edition":
        return _YEAR_RE.search(record.get("latest_version", "") or "").group(0) if _YEAR_RE.search(record.get("latest_version", "") or "") else ""
    if field == "qco":
        return json.dumps((gov_provenance.provenance_for(record).get("qco") or {}), ensure_ascii=False)
    return ""


def reconcile(record: dict | None, facts: list[dict]) -> dict:
    """One standard's local-vs-external reconciliation.

    Returns {standard, external_facts, verification_status, discrepancies,
    upgrade_available, notes} — pure, no mutation.
    """
    code = _norm_code((record or {}).get("is_number_clean", "") or (facts[0].get("standard_number", "") if facts else ""))
    out: dict = {
        "standard": code,
        "external_facts": facts,
        "verification_status": "UNVERIFIED",
        "discrepancies": [],
        "upgrade_available": False,
        "notes": [],
    }

    source_facts = [f for f in facts if f.get("verification_status") == "SOURCE_RETRIEVED"]
    unavailable = [f for f in facts if f.get("verification_status") in ("SOURCE_UNAVAILABLE",)]
    stale = [f for f in facts if f.get("verification_status") == "STALE_CACHE"]

    if not facts or (unavailable and not source_facts and not stale):
        out["verification_status"] = "SOURCE_UNAVAILABLE"
        out["notes"].append("Authoritative source could not be reached — nothing was verified externally.")
        return out

    if stale and not source_facts:
        out["verification_status"] = "SOURCE_UNAVAILABLE"
        out["notes"].append("Only a stale cached copy of the source was available (retrieved_at shown per fact).")
        source_facts = stale

    listed = [f for f in source_facts if f.get("field") == "qco" and f.get("value") not in ("not_listed", "", None)]
    not_listed = [f for f in source_facts if f.get("field") == "qco" and f.get("value") == "not_listed"]
    ext_edition = next((f for f in source_facts if f.get("field") == "edition" and f.get("value")), None)

    # --- certification / QCO -------------------------------------------------
    local_cert = (record or {}).get("certification") or {}
    local_mandatory = bool(local_cert.get("mandatory"))
    if listed:
        out["verification_status"] = "PARTIALLY_VERIFIED"
        if not local_mandatory:
            out["discrepancies"].append({
                "type": "CERTIFICATION_MISMATCH",
                "standard": code,
                "local_value": "certification not mandatory",
                "external_value": listed[0].get("fact", ""),
                "source": listed[0].get("url", ""),
                "status": "MANUAL_REVIEW_REQUIRED",
            })
    elif not_listed:
        if local_mandatory:
            out["discrepancies"].append({
                "type": "QCO_MISMATCH",
                "standard": code,
                "local_value": "mandatory certification claimed by curated registry",
                "external_value": "not on the fetched official BIS compulsory-certification list",
                "source": not_listed[0].get("url", ""),
                "status": "MANUAL_REVIEW_REQUIRED",
            })
        out["verification_status"] = "PARTIALLY_VERIFIED"

    # --- edition --------------------------------------------------------------
    if record:
        local_edition = _registry_value(record, "edition")
        if ext_edition:
            ext_year = _YEAR_RE.search(ext_edition.get("value", "") or "")
            ext_year = ext_year.group(0) if ext_year else ""
            if local_edition and ext_year and local_edition != ext_year:
                out["discrepancies"].append({
                    "type": "EDITION_MISMATCH",
                    "standard": code,
                    "local_value": f"IS {record.get('core_number', '')}:{local_edition}",
                    "external_value": f"IS {record.get('core_number', '')}:{ext_year}",
                    "source": ext_edition.get("url", ""),
                    "status": "OUTDATED_REGISTRY" if local_edition < ext_year else "MANUAL_REVIEW_REQUIRED",
                })
                if local_edition < ext_year:
                    out["verification_status"] = "OUTDATED_REGISTRY"
                    out["upgrade_available"] = True
            elif local_edition == ext_year:
                # Official list cites the same edition as the registry.
                if out["verification_status"] == "UNVERIFIED":
                    out["verification_status"] = "PARTIALLY_VERIFIED"
                out["notes"].append(f"External source cites edition {local_edition}, matching the local registry.")
    else:
        if ext_edition:
            out["discrepancies"].append({
                "type": "MISSING_LOCAL_DATA",
                "standard": code,
                "local_value": "",
                "external_value": ext_edition.get("fact", ""),
                "source": ext_edition.get("url", ""),
                "status": "MANUAL_REVIEW_REQUIRED",
            })

    # External facts that carry no matching local side at all.
    if not record and not ext_edition:
        out["discrepancies"].append({
            "type": "MISSING_LOCAL_DATA",
            "standard": code,
            "local_value": "",
            "external_value": json.dumps(source_facts[:1], ensure_ascii=False)[:200],
            "source": (source_facts[0].get("url", "") if source_facts else ""),
            "status": "MANUAL_REVIEW_REQUIRED",
        })

    if out["verification_status"] == "UNVERIFIED" and source_facts:
        out["verification_status"] = "PARTIALLY_VERIFIED"
    return out


def reconcile_many(records: list[dict], facts_by_code: dict[str, list[dict]]) -> list[dict]:
    """Reconcile several standards; codes without records still reconcile."""
    by_norm = {_norm_code(r.get("is_number_clean", "")): r for r in records}
    out = []
    for code, facts in facts_by_code.items():
        out.append(reconcile(by_norm.get(_norm_code(code)), facts))
    return out
