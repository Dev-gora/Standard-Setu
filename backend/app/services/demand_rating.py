"""Demand-vs-availability rating for bulk tender batches.

For every standard demanded across the uploaded tenders:
  - demanded_by      how many tenders cite it (the DEMAND side)
  - share_pct        demand share of the batch
  - verified_mandatory  whether the requirement is QCO-backed (honest provenance)
  - availability     the SUPPLY side: can certified suppliers plausibly serve
                     this demand? Derived deterministically from signals the
                     system actually has (BIS licence scheme presence, Product
                     Manual existence, scheme status) — never invented.
  - demand_level     HIGH / MEDIUM / LOW band for quick scanning

Interpretation for a procurement officer:
  HIGH demand + QCO-backed + established certification scheme
      -> healthy, competitive supply expected.
  HIGH demand + NO QCO backing / scheme doubt
      -> specification risk: demand is real but the certified-supplier pool
         is uncertain — split lots or allow equivalents.
Ratings are advisory analytics, not market data.
"""

from __future__ import annotations

from app.models.schemas import BulkCheckIssue
from app.services import gov_provenance


def _availability_note(standard: str, mandatory: bool, basis: str, issues_by_kind: dict) -> tuple[str, str]:
    """(availability_note, confidence) from signals we truly have.

    Signals used, in order of strength:
      1. QCO-backed mandatory certification -> formal certified-supplier pool
         must exist (BIS licenses under the scheme).
      2. Non-mandatory but BIS scheme exists -> voluntary certified pool.
      3. No scheme / unverified -> availability uncertain.
    Issue pressure (many outdated/unknown flags in tenders citing it) lowers
    practical availability.
    """
    if mandatory and basis == "VERIFIED":
        # Deliberate wording: this is an inference from QCO backing (a formal
        # certification ecosystem must exist), NOT a supplier-count or
        # market-share statistic — the system holds no such data.
        note, conf = "QCO-backed certification ecosystem — availability signal established", "high"
    elif mandatory:
        note, conf = "Mandatory per registry but QCO not verified — supplier pool uncertain", "medium"
    else:
        note, conf = "Voluntary product — no QCO pool signal; availability cannot be inferred from our data", "low"

    pressure = len(issues_by_kind.get("outdated_version", [])) + len(issues_by_kind.get("unknown_standard", []))
    if pressure:
        note += f"; {pressure} citation issue(s) in this batch suggest spec confusion"
        conf = "low" if pressure >= 3 else conf
    return note, conf


def _band(share_pct: float, mandatory: bool) -> str:
    if share_pct >= 50:
        return "HIGH"
    if share_pct >= 20:
        return "MEDIUM"
    return "LOW"


# Honest explanations for batch-level findings (the issue detail itself is
# per-file; this line explains what the group means for the batch).
_BATCH_DETAIL = {
    "unparseable": (
        "These documents had no extractable text (scanned images or unsupported "
        "files) — no citation checks were possible on them. Manual review required."
    ),
}


def batch_level_issues(results) -> list[dict]:
    """Aggregate issues that are NOT attributable to any single standard.

    Every issue carries an explicit attribution now (BulkCheckIssue.standard /
    .batch_level). Only genuinely unmappable issues — e.g. documents whose text
    could not be extracted — are batch-level; they are grouped by kind across
    files so per-standard views stay honest instead of pinning them to the
    first cited code.
    """
    by_kind: dict[str, list[str]] = {}
    for r in results:
        for iss in r.issues:
            if iss.batch_level or not (iss.standard or "").strip():
                by_kind.setdefault(iss.kind, []).append(r.file_name)
    return [
        {
            "kind": kind,
            "files": files,
            "count": len(files),
            "detail": _BATCH_DETAIL.get(kind, f"{kind.replace('_', ' ')} — not attributable to a specific standard."),
        }
        for kind, files in by_kind.items()
    ]


def rate_demand(results, total: int) -> list[dict]:
    """Build the per-standard demand rating for one bulk-check batch.

    Issue pressure per standard is attributed via each issue's explicit
    `standard` field — an issue is counted against the standard it CONCERNS,
    never against whichever code happened to be cited first.
    """
    demand: dict[str, dict] = {}
    issues_by_std: dict[str, dict] = {}

    for r in results:
        if r.status == "error":
            continue
        for code in r.standards_cited:
            key = code.split(":")[0].strip()
            d = demand.setdefault(key, {"demanded_by": 0, "issues": []})
            d["demanded_by"] += 1
        for iss in r.issues:
            # Explicit attribution only. Issues without a standard (unparseable
            # docs etc.) belong to the batch — surfaced via batch_level_issues(),
            # never guessed onto a citation.
            key = (iss.standard or "").split(":")[0].strip()
            if key:
                issues_by_std.setdefault(key, {}).setdefault(iss.kind, []).append(iss.detail)

    rated: list[dict] = []
    for code, d in demand.items():
        rec = gov_provenance.decorate(
            {"is_number_clean": code, "core_number": code.replace("IS ", ""), "certification": {"mandatory": False}}
        )
        # Prefer the real registry record when it exists (title/cert fields).
        from app.services import standards_registry as registry

        real = registry.get_by_is_number(code)
        if real:
            rec = gov_provenance.decorate(real)
        cert = rec.get("certification") or {}
        gov = rec.get("gov") or {}
        basis = gov.get("certification_basis", "UNVERIFIED")
        mandatory = bool(cert.get("mandatory"))
        share = round(d["demanded_by"] * 100 / max(total, 1), 1)
        note, conf = _availability_note(code, mandatory, basis, issues_by_std.get(code, {}))

        rated.append({
            "standard": code,
            "title": (rec.get("title") or "")[:80],
            "demanded_by": d["demanded_by"],
            "share_pct": share,
            "demand_level": _band(share, mandatory),
            "verified_mandatory": basis == "VERIFIED",
            "certification_status": basis,
            "availability_note": note,
            "availability_confidence": conf,
            "qco": (gov.get("qco") or {}).get("name", ""),
        })

    rated.sort(key=lambda x: (-x["demanded_by"], x["standard"]))
    return rated
