"""Tender document checking for the bulk mode (SIH26108).

Parses uploaded tender/specification PDFs and checks the Indian Standards
they cite against the curated registry:

- unknown codes (not in the registry)
- outdated editions (cited year older than the registry's latest_version)
- missing mandatory-certification language (ISI mark / BIS licence / QCO…)

PDF parsing uses pdfplumber (already a dependency). No new dependencies.
"""

from __future__ import annotations

import io
import re

from app.models.schemas import BulkCheckIssue, FileCheckResult
from app.services import standards_registry as registry
from app.services import gov_provenance

MAX_STANDARDS_PER_FILE = 30

# Standard-SPECIFIC certification language: names the mark/licence itself.
# Finding these anywhere in the document indicates a concrete BIS/ISI
# requirement (though not necessarily tied to one IS code).
CERT_LANGUAGE = re.compile(
    r"isi\s*mark|bis\s*licen[cs]e|licen[cs]e\s*number|cm\s*/\s*l\s*-|bis\s*certified|"
    r"qco|quality\s*control\s*order|crs|hallmark",
    re.IGNORECASE,
)

# GENERIC certification language: process boilerplate that does NOT name the
# mark or a licence. This alone is NOT proof that a specific IS standard's
# certification requirement has been addressed (audit item 9).
GENERIC_CERT_LANGUAGE = re.compile(
    r"certification|required\s+to\s+be\s+certified|certified\s+product|"
    r"quality\s+assurance|quality\s+plan|third[-\s]party\s+inspection",
    re.IGNORECASE,
)

# Citation pattern: IS 1786 | IS:1786 | IS 1786:2008 | IS 1239 (Part 1):2004 |
# IS 302 Part 1 Section 4 — captures the core code (with part/section) and year.
_CITE_RE = re.compile(
    r"\bIS\s*[\:\uff1a\-]?\s*"
    r"(\d{2,6}"
    r"(?:\s*\(?\s*(?:Part|Pt\.?)\s*\w+\s*\)?)?"
    r"(?:\s*\(?\s*(?:Section|Sec\.?)\s*\w+\s*\)?)?)"
    r"(?:\s*[\:\uff1a\-]\s*((?:19|20)\d{2}))?",
    re.IGNORECASE,
)


def extract_text_from_pdf(pdf_bytes: bytes, filename: str) -> str:
    """Extract all text from a PDF (bytes). Returns '' on failure."""
    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n".join(pages)
    except Exception:
        return ""


def _year_of(text: str) -> int | None:
    m = re.search(r"(19|20)\d{2}", text or "")
    return int(m.group(0)) if m else None


def extract_cited_standards(text: str) -> list[str]:
    """Extract IS codes cited in a document, in order of first appearance.

    Keeps the cited year when present ('IS 1786:2008') so the outdated-edition
    check can compare it against the registry's latest version.
    """
    codes: list[str] = []
    for m in _CITE_RE.finditer(text or ""):
        core = re.sub(r"\s+", " ", m.group(1).strip())
        code = f"IS {core}"
        if m.group(2):
            code = f"{code}:{m.group(2)}"
        if code not in codes:
            codes.append(code)
    return codes[:MAX_STANDARDS_PER_FILE]


def check_tender_text(file_name: str, text: str) -> FileCheckResult:
    """Check one tender document's text against the registry."""
    text = (text or "").strip()
    if not text:
        return FileCheckResult(
            file_name=file_name,
            status="error",
            note="Could not extract text (scanned image PDF or unsupported file).",
            issues=[BulkCheckIssue(
                kind="unparseable", batch_level=True,
                detail="No text could be extracted from this document.",
            )],
        )

    cited = extract_cited_standards(text)
    issues: list[BulkCheckIssue] = []
    known_records: list[dict] = []

    for code in cited:
        record = registry.get_by_is_number(code)
        if record is None:
            # This issue CONCERNS code — attribution is explicit, never guessed.
            issues.append(BulkCheckIssue(
                kind="unknown_standard",
                detail=f"{code} is not in the covered registry — verify manually or extend the dataset.",
                standard=code,
            ))
            continue

        known_records.append(record)

        # Outdated edition check: cited year vs registry latest_version year.
        # Prefer the explicit citation year ('IS 1786:2008'); if absent, fall back
        # to the first 4-digit number inside the citation itself (skipping the
        # IS number and part tokens).
        latest_year = _year_of(record.get("latest_version", ""))
        year_m = re.search(r"(19|20)\d{2}", code)
        cited_year = int(year_m.group(0)) if year_m else None
        if cited_year is None:
            tail = re.sub(r"^IS\s*\d+", "", code)          # drop the IS number
            tail = re.sub(r"(?i)part|section|\d+", " ", tail)  # drop part/section tokens
            cited_year = _year_of(tail)
        if latest_year and cited_year and cited_year < latest_year:
            issues.append(BulkCheckIssue(
                kind="outdated_version",
                standard=code,
                detail=(
                    f"{code} predates the current edition "
                    f"({record['is_number_clean']}, {record['latest_version']}"
                    + (f"; {record['amendment']}" if record["amendment"] else "") + ")."
                ),
            ))

        # Mandatory certification language check — PROVENANCE-AWARE.
        # 'mandatory' is a curated CLAIM; only QCO-backed claims may drive a
        # 'missing certification' finding. Everything else becomes a
        # manual-review note instead of a compliance verdict.
        if record.get("certification", {}).get("mandatory"):
            gov = gov_provenance.provenance_for(record)
            basis = gov.get("certification_basis")
            qco_name = (gov.get("qco") or {}).get("name", "")
            specific = CERT_LANGUAGE.search(text)
            generic_only = (not specific) and bool(GENERIC_CERT_LANGUAGE.search(text))

            if basis == "VERIFIED":
                if not specific and not generic_only:
                    issues.append(BulkCheckIssue(
                        kind="missing_certification",
                        standard=record["is_number_clean"],
                        detail=(
                            f"{record['is_number_clean']} requires BIS certification "
                            f"(mandatory under {qco_name or 'a Quality Control Order'}) "
                            "but the document contains no certification/licence requirement language."
                        ),
                    ))
                elif generic_only:
                    issues.append(BulkCheckIssue(
                        kind="generic_certification_language",
                        standard=record["is_number_clean"],
                        detail=(
                            f"The document mentions certification only generically. "
                            f"{record['is_number_clean']} is mandatory under {qco_name or 'a QCO'} — "
                            "add a product-specific BIS/ISI licence requirement naming the standard."
                        ),
                    ))
            else:
                # Not QCO-backed: never claim the tender is non-compliant.
                issues.append(BulkCheckIssue(
                    kind="certification_unverified",
                    standard=record["is_number_clean"],
                    detail=(
                        f"{record['is_number_clean']} is listed as requiring certification in the "
                        "curated dataset, but no government notification backing that requirement "
                        "could be verified — confirm on the BIS portal before relying on it."
                    ),
                ))

    if cited and not known_records and not issues:
        status = "review"
    elif issues:
        status = "review"
    else:
        status = "pass"

    primary = known_records[0] if known_records else None
    standards_cited = [r["is_number_clean"] for r in known_records] or cited

    note = ""
    if status == "pass":
        note = "Meets the mandatory quality/certification requirements for the standards it cites."
    elif primary is None and cited:
        note = "None of the cited standards are in the registry — manual review needed."

    return FileCheckResult(
        file_name=file_name,
        status=status,
        product_label=primary["category"] if primary else "",
        standards_cited=standards_cited,
        primary_standard=primary["is_number_clean"] if primary else "",
        issues=issues,
        note=note,
    )


def check_tender_pdf(pdf_bytes: bytes, file_name: str) -> FileCheckResult:
    return check_tender_text(file_name, extract_text_from_pdf(pdf_bytes, file_name))


def minimum_standards_set(results: list[FileCheckResult]) -> list[str]:
    """Unique registry standards across all passing files (capped)."""
    seen: list[str] = []
    for r in results:
        if r.status != "pass":
            continue
        for code in r.standards_cited:
            if code not in seen:
                seen.append(code)
    return seen[:40]
