"""P1-9 — Standard version comparison from actual indexed sources.

Strict honesty rules:
- Only editions whose documents were actually indexed from reference/bis_pdfs
  can be compared. With fewer than two indexed editions the answer is
  "Comparison unavailable — source document not indexed."
- Diffs are computed section-by-section on clause headings captured at index
  time (clause number + heading text + page). We never speculate about section
  content we do not have; sections that cannot be matched are reported as
  "unable_to_determine".
"""

from __future__ import annotations

import difflib
import re

from app.models.schemas import VersionCompareResponse, VersionSectionDiff
from app.services.evidence import _load_index
from app.services import standards_registry as registry

_YEAR_RE = re.compile(r"(19|20)\d{2}")


def _clause_key(clause: str) -> str:
    return re.sub(r"\s+", " ", (clause or "")).strip().lower()


def _edition_key_for_year(doc: dict, year: str | None) -> str | None:
    """Pick the edition file whose name/edition key matches a cited year best."""
    keys = doc.get("edition_keys") or []
    if not keys:
        return None
    if not year:
        return keys[0]
    if year in keys:
        return year
    # fall back: the edition whose key contains the year
    for k in keys:
        if year in k:
            return k
    return keys[0]


def _section_map(doc: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for c in doc.get("clauses", []):
        key = _clause_key(c.get("clause", ""))
        if key:
            out.setdefault(key, c)
    return out


def compare_versions(code: str, from_year: str | None = None, to_year: str | None = None) -> VersionCompareResponse:
    rec = registry.get_by_is_number(code)
    core = rec["core_number"] if rec else (re.search(r"\d{2,6}", code or "").group(0)
                                           if re.search(r"\d{2,6}", code or "") else "")
    doc = _load_index().get("documents", {}).get(core)

    if not doc:
        return VersionCompareResponse(
            code=code, from_version=from_year or "", to_version=to_year or "",
            available=False,
            message="Comparison unavailable - source document not indexed.",
        )

    editions = doc.get("editions") or {}
    edition_keys = doc.get("edition_keys") or []

    # Distinct editions only (an edition map with one key cannot show change).
    if len(edition_keys) < 2 and len(editions) < 2:
        return VersionCompareResponse(
            code=code, from_version=from_year or "", to_version=to_year or "",
            available=False,
            message=("Source document is indexed, but only one edition file exists in the "
                     "corpus - version comparison needs two editions. "
                     "Comparison unavailable - source document not indexed."),
        )

    from_key = _edition_key_for_year(editions, from_year) or edition_keys[0]
    to_key = _edition_key_for_year(editions, to_year) or edition_keys[-1]
    if from_key == to_key:
        # Same edition file picked for both sides - nothing honest to compare.
        return VersionCompareResponse(
            code=code, from_version=from_key, to_version=to_key,
            available=False,
            message="Only one edition of this standard is indexed; "
                    "comparison unavailable - source document not indexed.",
        )

    prev_doc = editions[from_key]
    curr_doc = editions[to_key]
    prev_sections = _section_map(prev_doc)
    curr_sections = _section_map(curr_doc)

    sections: list[VersionSectionDiff] = []
    all_keys = list(dict.fromkeys(list(prev_sections.keys()) + list(curr_sections.keys())))
    for key in all_keys[:60]:  # cap for report size
        p, c = prev_sections.get(key), curr_sections.get(key)
        if p and not c:
            change = "removed"
        elif c and not p:
            change = "added"
        else:
            sim = difflib.SequenceMatcher(
                None, _clause_key(p.get("heading", "")), _clause_key(c.get("heading", ""))
            ).ratio()
            if sim >= 0.97:
                change = "unchanged"
            elif sim >= 0.6:
                change = "modified"
            else:
                change = "unable_to_determine"
        sections.append(VersionSectionDiff(
            section=key,
            previous=(p or {}).get("heading", ""),
            current=(c or {}).get("heading", ""),
            change=change,
        ))

    changed_count = sum(1 for s in sections if s.change not in ("unchanged",))
    return VersionCompareResponse(
        code=code,
        from_version=from_key,
        to_version=to_key,
        sections=sections,
        changed_count=changed_count,
        available=True,
        message=f"{changed_count} section(s) differ between indexed editions "
                f"({from_key} file vs {to_key} file).",
    )
