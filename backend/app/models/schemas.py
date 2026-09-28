"""Pydantic request / response schemas for the procurement API (SIH26108)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CertificationInfo(BaseModel):
    """Certification claim + its provenance.

    `mandatory` is a CLAIM from the curated dataset. `verification_status`
    states how well that claim is backed:
      VERIFIED               - QCO/notification confirmed from an official BIS/GoI source
      PARTIALLY_VERIFIED     - official source supports part of the claim
      UNVERIFIED             - no authoritative source checked
      MANUAL_REVIEW_REQUIRED - curated claim of mandatory with no located QCO
    When verification_status is not VERIFIED the UI must not present the
    requirement as an established legal fact.
    """
    mandatory: bool
    scheme: str = ""
    note: str = ""
    verification_status: str = "UNVERIFIED"
    basis: str = ""          # QCO/notification text when VERIFIED
    source_url: str = ""


class RegistryStandard(BaseModel):
    """A standards-registry record as exposed to the frontend."""
    is_number: str
    title: str
    category: str = ""
    scope_description: str = ""
    latest_version: str = ""
    amendment: str = ""
    certification: CertificationInfo
    archive_link: dict = {}
    score: float | None = None
    # Government-source provenance (audit): LOCAL_REGISTRY vs GOVERNMENT_VERIFIED etc.
    version_status: str = "LOCAL_REGISTRY"
    verification_status: str = "UNVERIFIED"
    gov_edition: str = ""
    qco: dict = {}


class AlliedStandard(BaseModel):
    code: str
    title: str = ""
    category: str = ""
    purpose: str = "Related standard"
    latest_version: str = ""
    amendment: str = ""
    certification: CertificationInfo | None = None
    known: bool = True
    archive_link: dict = {}


class ClarifyOption(BaseModel):
    label: str
    query: str


class ClarifyPrompt(BaseModel):
    question: str
    helper: str = ""
    options: list[ClarifyOption]


class ProcureRequest(BaseModel):
    query: str
    language: str = "en"
    top_k: int = Field(default=4, ge=1, le=10)


# --- P0-2 structured evidence (defined early: used by recommendations) --------

class EvidenceRef(BaseModel):
    """A clause/page citation resolved (or honestly unresolvable) from the corpus.

    CRITICAL: page/clause are only ever filled from the offline index built over
    the actual BIS PDF corpus. When they are unknown, available=False and the UI
    shows 'Source available - clause/page not indexed'. Never invented.
    """
    standard: str
    edition: str = ""
    document: str = ""
    page: int | None = None
    clause: str | None = None
    url: str = ""
    evidence: str = ""
    available: bool = False
    unavailable_reason: str = ""
    # Provenance class (audit item 10):
    #   LOCAL_REFERENCE_DOCUMENT | OFFICIAL_BIS_SOURCE | OFFICIAL_GOVERNMENT_SOURCE
    #   USER_PROVIDED_DOCUMENT | UNVERIFIED_SOURCE
    source_type: str = "LOCAL_REFERENCE_DOCUMENT"


class ClaimEvidence(BaseModel):
    """A 'why' claim paired with its structured citation."""
    claim: str
    kind: str = Field(description="requirement_match | scope | certification | edition | source")
    evidence: EvidenceRef


# --- P0-1 Explainable Match Score -------------------------------------------

class ScoreFactor(BaseModel):
    """One traceable factor of the Match Score (value 0-100)."""
    label: str
    value: int = Field(ge=0, le=100, description="Factor score, 0-100")
    weight: int = Field(default=0, ge=0, le=100, description="Weight in the Match Score average, %")
    detail: str = ""


class ScoreBreakdown(BaseModel):
    """Explainable Match Score — traceable to actual matching signals.

    Never presented as a calibrated probability; always 'Match Score'.
    """
    score: int = Field(ge=0, le=100, description="Match Score 0-100 = weighted average of similarity factors")
    factors: list[ScoreFactor] = []
    signals: dict[str, float | None] = {}
    embedding_mode: str = Field(description="semantic | keyword_only")
    confidence: str = Field(description="High | Medium | Low")


class ProcureRecommendation(BaseModel):
    standard: RegistryStandard
    relevance_score: float
    reason: str = ""
    allied: list[AlliedStandard] = []
    tender_block: str = ""
    match: ScoreBreakdown | None = None
    evidence: list[ClaimEvidence] = []


class ProcureResponse(BaseModel):
    query: str
    product_label: str = ""
    clarify_needed: bool = False
    clarify: ClarifyPrompt | None = None
    recommendations: list[ProcureRecommendation] = []
    mode: str = "procure"
    history_id: str = ""


class TenderBlockRequest(BaseModel):
    is_number: str
    context: str = Field(default="", description="Original procurement query for wording hints")


class TenderBlockResponse(BaseModel):
    is_number: str
    tender_block: str
    generated_by: str = Field(description="template | llm")


# --- P1-7 risk heatmap --------------------------------------------------------

class RiskDimension(BaseModel):
    dimension: str
    level: str = Field(description="low | medium | high")
    score: int = Field(ge=0, le=100)
    findings: list[str] = []
    action: str = ""


class TenderRisk(BaseModel):
    file_name: str
    overall: str = "low"
    dimensions: list[RiskDimension] = []


class RiskResponse(BaseModel):
    files: list[TenderRisk]
    overall: str = "low"
    summary: str = ""


# --- P1-8 OCR -----------------------------------------------------------------

class OcrStatus(BaseModel):
    attempted: bool = False
    used: bool = False
    pages: int = 0
    confidence: float | None = None
    message: str = ""


class BulkCheckIssue(BaseModel):
    kind: str = Field(description="unknown_standard | outdated_version | missing_certification | unparseable")
    detail: str
    # Attribution — the specific standard this issue CONCERNS, or "" when the
    # issue genuinely cannot be mapped to one (e.g. an unparseable document).
    # Consumers must never guess: unmapped issues roll up to batch level
    # (BulkCheckResponse.batch_issues) instead of being pinned to a citation.
    standard: str = Field(default="", description="IS code this issue concerns, or '' when not attributable to a standard")
    batch_level: bool = Field(default=False, description="True when the issue belongs to the tender/batch, not any single standard")


class FileCheckResult(BaseModel):
    file_name: str
    status: str = Field(description="pass | review | error")
    product_label: str = ""
    standards_cited: list[str] = []
    primary_standard: str = ""
    issues: list[BulkCheckIssue] = []
    note: str = ""
    ocr: "OcrStatus | None" = None
    text_chars: int = 0


class BulkCheckResponse(BaseModel):
    files: list[FileCheckResult]
    total: int
    passing: int
    min_standards: list[str] = Field(description="Minimum set of standards covering every passing file")
    risk: "RiskResponse | None" = None
    # Demand vs availability rating (per batch): how many tenders demand each
    # standard, and how many certified-supplier/licence signals appear for it.
    demand_rating: list[dict] = Field(
        default_factory=list,
        description="Per-standard demand stats: {standard, demanded_by, share_pct, verified_mandatory, availability_note, demand_level}",
    )
    # Batch-level issues: issues that could NOT be attributed to a specific
    # standard (unparseable documents etc.), aggregated so per-standard views
    # stay honest instead of pinning them to the first cited code.
    batch_issues: list[dict] = Field(
        default_factory=list,
        description="Issues not attributable to any standard: {kind, files, count, detail}",
    )


# --- P0-3 BIS licence verification -------------------------------------------

class VerifyRequest(BaseModel):
    licence_number: str = ""
    supplier_name: str = ""
    is_number: str = ""


class VerifyResponse(BaseModel):
    licence_number: str
    supplier_name: str = ""
    is_number: str = ""
    status: str = Field(
        description="valid | invalid | expired | not_found | unable_to_verify | source_unavailable"
    )
    state: str = Field(
        default="",
        description="Exact audit state: INVALID_FORMAT | NOT_FOUND | SOURCE_UNAVAILABLE | SOURCE_LOCATED | VERIFIED_ACTIVE | VERIFIED_EXPIRED | VERIFIED_CANCELLED | VERIFIED_SCOPE_MATCH | VERIFIED_SCOPE_MISMATCH | MANUAL_REVIEW_REQUIRED",
    )
    detail: str = ""
    product: str = ""
    validity: str = ""
    source: str = "BIS (manakonline.in)"
    last_verified: str = ""
    cached: bool = False
    source_url: str = ""
    message: str = ""


# --- P0-4 audit history -------------------------------------------------------

class HistoryEntry(BaseModel):
    id: str
    ts: str
    kind: str = Field(description="recommendation | clarify | tender_check | verification")
    query: str = ""
    session_id: str = "local"
    title: str = ""
    status: str = "completed"
    payload: dict = {}


class HistoryListResponse(BaseModel):
    entries: list[HistoryEntry]
    total: int


# --- P0-5 watchlist + notifications -------------------------------------------

class WatchRequest(BaseModel):
    is_number: str
    note: str = ""


class WatchlistItem(BaseModel):
    is_number: str
    title: str = ""
    latest_version: str = ""
    amendment: str = ""
    added_at: str = ""
    last_checked: str = ""
    note: str = ""
    changed: bool = False
    baseline: dict = {}


class WatchlistResponse(BaseModel):
    items: list[WatchlistItem]
    notifications: list[dict] = []
    checked_at: str = ""
    total: int = 0


class NotificationsResponse(BaseModel):
    notifications: list[dict]
    unread: int


class NotificationActionRequest(BaseModel):
    id: str


# --- P1-1 comparison ----------------------------------------------------------

class CompareRequest(BaseModel):
    codes: list[str] = Field(min_length=2, max_length=5)
    query: str = ""


class CompareColumn(BaseModel):
    code: str
    title: str = ""
    found: bool = True
    latest_version: str = ""
    amendment: str = ""
    category: str = ""
    scope_description: str = ""
    certification: CertificationInfo | None = None
    normative_refs: list[str] = []
    match_score: int | None = None
    attributes: dict[str, str] = {}


class CompareResponse(BaseModel):
    columns: list[CompareColumn]
    attributes: list[str]
    query: str = ""


# --- P1-9 version comparison ---------------------------------------------------

class VersionSectionDiff(BaseModel):
    section: str
    previous: str
    current: str
    change: str = Field(description="added | removed | modified | unchanged | unable_to_determine")


class VersionCompareResponse(BaseModel):
    code: str
    from_version: str
    to_version: str
    sections: list[VersionSectionDiff] = []
    changed_count: int = 0
    available: bool = False
    message: str = ""


# --- P1-10 unified report ------------------------------------------------------

class ReportRequest(BaseModel):
    query: str
    code: str = ""
    include_evidence: bool = True
    include_tender_block: bool = True


class ReportResponse(BaseModel):
    generated_at: str
    query: str
    standard: RegistryStandard | None = None
    match: ScoreBreakdown | None = None
    evidence: list[ClaimEvidence] = []
    allied: list[AlliedStandard] = []
    tender_block: str = ""
    risk_notes: list[str] = []
    sources: list[EvidenceRef] = []
