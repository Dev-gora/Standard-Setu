"""P0-2 — Clause/page source citations backed by an offline document index.

The BIS standard PDFs in <project>/reference/bis_pdfs are indexed once, offline,
by scripts/build_evidence_index.py into backend/data/evidence_index.json. This
service reads that index and resolves structured citations.

CRITICAL HONESTY RULE (never invent citations):
- page/clause are only ever taken verbatim from the built index.
- If the standard's document is not in the corpus, available=False with reason
  "source_document_not_indexed".
- If the document exists but no clause heading matches the query, the best we
  return is a page hit or "clause_page_not_indexed" — never a guessed number.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from app.models.schemas import ClaimEvidence, EvidenceRef
from app.services import standards_registry as registry
from app.services import gov_provenance

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
INDEX_FILE = DATA_DIR / "evidence_index.json"

_INDEX_CACHE: dict | None = None


def _load_index() -> dict:
    global _INDEX_CACHE
    if _INDEX_CACHE is None:
        if INDEX_FILE.exists():
            try:
                _INDEX_CACHE = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
            except Exception:
                _INDEX_CACHE = {}
        else:
            _INDEX_CACHE = {}
    return _INDEX_CACHE


def index_available() -> bool:
    return bool(_load_index().get("documents"))


def indexed_codes() -> list[str]:
    return sorted(_load_index().get("documents", {}).keys())


def _norm_code(code: str) -> str:
    """'IS 1786:2008' / 'IS 1239 (Part 1)' -> core number token for index keys."""
    m = re.search(r"(\d+)", code or "")
    return m.group(1) if m else ""


def _best_clause(doc: dict, query: str) -> dict | None:
    """Find the clause heading whose tokens overlap the query best.

    Deterministic token-overlap only — no model, no guessing. Returns the
    clause entry (with page) or None.
    """
    q_tokens = {
        t for t in re.findall(r"[a-z0-9]+", (query or "").lower())
        if t not in {"for", "the", "a", "an", "of", "in", "on", "and", "or", "to", "with", "is", "are"}
    }
    best, best_score = None, 0.0
    for clause in doc.get("clauses", []):
        c_tokens = set(re.findall(r"[a-z0-9]+", (clause.get("heading", "") or "").lower()))
        if not c_tokens or not q_tokens:
            continue
        overlap = len(q_tokens & c_tokens) / len(q_tokens)
        if overlap > best_score:
            best, best_score = clause, overlap
    return best if best and best_score >= 0.25 else None


def _first_relevant_page(doc: dict, query: str) -> dict | None:
    """Best page by token overlap with the page text captured at index time."""
    q_tokens = {
        t for t in re.findall(r"[a-z0-9]+", (query or "").lower())
        if t not in {"for", "the", "a", "an", "of", "in", "on", "and", "or", "to", "with", "is", "are"}
    }
    best, best_score = None, 0.0
    for page in doc.get("pages", []):
        p_tokens = set(re.findall(r"[a-z0-9]+", (page.get("sample", "") or "").lower()))
        if not p_tokens or not q_tokens:
            continue
        overlap = len(q_tokens & p_tokens) / len(q_tokens)
        if overlap > best_score:
            best, best_score = page, overlap
    return best if best and best_score >= 0.15 else None


def resolve_evidence(standard_record: dict, query: str) -> EvidenceRef:
    """Resolve a citation for one standard against the built index.

    Honesty matrix:
      document in index + clause match  -> clause + page + evidence snippet
      document in index + no clause     -> page hit if strong, else not indexed
      document not in index             -> source_document_not_indexed
    """
    code = standard_record.get("is_number_clean", "")
    edition = standard_record.get("latest_version", "")
    link = registry.archive_link(standard_record.get("is_number", code), edition)
    url = link.get("url", "")

    doc = _load_index().get("documents", {}).get(_norm_code(code))
    if not doc:
        return EvidenceRef(
            standard=code, edition=edition, url=url, available=False,
            unavailable_reason="source_document_not_indexed",
            source_type=_source_type(),
        )

    clause_hit = _best_clause(doc, query)
    if clause_hit:
        return EvidenceRef(
            standard=code, edition=edition,
            document=doc.get("document", ""),
            page=clause_hit.get("page"),
            clause=clause_hit.get("clause"),
            url=url, available=True,
            evidence=(clause_hit.get("heading", "") or "")[:200],
            source_type=_source_type(),
        )

    page_hit = _first_relevant_page(doc, query)
    if page_hit:
        return EvidenceRef(
            standard=code, edition=edition,
            document=doc.get("document", ""),
            page=page_hit.get("page"),
            clause=None, url=url, available=True,
            evidence=(page_hit.get("sample", "") or "")[:200],
            source_type=_source_type(),
        )

    return EvidenceRef(
        standard=code, edition=edition, document=doc.get("document", ""),
        url=url, available=False, unavailable_reason="clause_page_not_indexed",
        source_type=_source_type(),
    )


def _source_type() -> str:
    """Provenance class of this corpus (audit item 10).

    The reference PDFs came from a public mirror of official BIS documents
    (archive.org 'gov.in.is.*' uploads of Bureau of Indian Standards scans).
    They are NOT fetched from bis.gov.in itself, so they are classified as
    LOCAL_REFERENCE_DOCUMENT - honest about provenance without claiming the
    BIS website as the retrieval source.
    """
    return "LOCAL_REFERENCE_DOCUMENT"


def build_claim_evidence(query: str, record: dict, cert_mandatory: bool) -> list[ClaimEvidence]:
    """Structured 'why' claims, each paired with an honest citation."""
    claims: list[ClaimEvidence] = [
        ClaimEvidence(
            claim=f"Requirement matches this standard's scope: {record.get('title', '')}",
            kind="scope",
            evidence=resolve_evidence(record, query or record.get("title", "")),
        ),
        ClaimEvidence(
            claim=f"Registry edition on record: {record.get('latest_version', 'unknown')}"
                  + (f", {record['amendment']}" if record.get("amendment") else ""),
            kind="edition",
            evidence=resolve_evidence(record, "scope"),
        ),
    ]
    if cert_mandatory:
        # PROVENANCE-AWARE certification claim (audit items 4/10/11):
        # the wording depends on whether a QCO actually backs it.
        gov = gov_provenance.provenance_for(record)
        basis = gov.get("certification_basis")
        qco = gov.get("qco") or {}
        if basis == "VERIFIED":
            claim_text = (
                f"BIS certification is mandatory for this product under "
                f"{qco.get('name', 'a Quality Control Order')}"
                + (f" ({qco.get('notification')})" if qco.get("notification") else "")
            )
            reason = "qco_verified_but_document_not_indexed_locally"
        else:
            claim_text = (
                "Curated dataset lists BIS certification for this product, but no "
                "government notification backing it was verified - treat as unconfirmed"
            )
            reason = "qco_source_not_verified"
        claims.append(ClaimEvidence(
            claim=claim_text,
            kind="certification",
            evidence=EvidenceRef(
                standard=record.get("is_number_clean", ""),
                edition=record.get("latest_version", ""),
                url=(qco.get("source_url") or registry.archive_link(record.get("is_number", ""), record.get("latest_version", "")).get("url", "")),
                available=basis == "VERIFIED",
                unavailable_reason=reason,
                source_type="OFFICIAL_BIS_SOURCE" if basis == "VERIFIED" else "UNVERIFIED_SOURCE",
            ),
        ))
    return claims
