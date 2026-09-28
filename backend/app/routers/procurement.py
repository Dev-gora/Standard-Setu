"""Procurement router — SIH26108 endpoints.

Turns the Standard Setu POC's mock flows into real endpoints backed by the
curated standards registry, the existing embedding/LLM services, and
pdfplumber-based tender parsing.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile

from app.models.schemas import (
    AlliedStandard,
    BulkCheckResponse,
    CertificationInfo,
    ClaimEvidence,
    ClarifyOption,
    ClarifyPrompt,
    CompareRequest,
    CompareResponse,
    FileCheckResult,
    HistoryEntry,
    HistoryListResponse,
    NotificationActionRequest,
    NotificationsResponse,
    OcrStatus,
    ProcureRecommendation,
    ProcureRequest,
    ProcureResponse,
    RegistryStandard,
    ReportRequest,
    ReportResponse,
    TenderBlockRequest,
    TenderBlockResponse,
    VerifyRequest,
    VerifyResponse,
    VersionCompareResponse,
    WatchRequest,
    WatchlistItem,
    WatchlistResponse,
)
from app.services import (
    compare as compare_service,
    evidence as evidence_service,
    ocr as ocr_service,
    report as report_service,
    risk as risk_service,
    scoring,
    standards_registry as registry,
    store,
    tender_check,
    verify as verify_service,
    versions as versions_service,
)
from app.services.llm import llm_complete
from app.services import gov_provenance
from app.services import demand_rating

router = APIRouter(prefix="/api/procure", tags=["procurement"])

# Clarify gate, on the card's scale: `_score` is the same weighted-factor
# Match Score the UI displays (1.0 == perfect card), so this reads "best card
# below 30/100". Specific product queries score 0.36+ and must not be blocked;
# only genuinely weak matches with disagreeing runners-up ask for clarify.
WEAK_MATCH_THRESHOLD = 0.30

MAX_FILES = 500
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB


def _session_id(request: Request) -> str:
    """Anonymous per-browser session id (random UUID, no PII)."""
    return request.headers.get("X-Session-Id", "local")


def _cert_info(raw: dict) -> CertificationInfo:
    return CertificationInfo(
        mandatory=bool(raw.get("mandatory")),
        scheme=raw.get("scheme", ""),
        note=raw.get("note", ""),
    )


def _to_registry_standard(rec: dict, score: float | None = None) -> RegistryStandard:
    # Provenance: decorate the record with its government-verification status.
    gov = gov_provenance.provenance_for(rec)
    cert_raw = rec.get("certification") or {}
    qco = gov.get("qco") or {}
    # The CertificationInfo carries the claim PLUS its backing evidence.
    cert = CertificationInfo(
        mandatory=bool(cert_raw.get("mandatory")),
        scheme=cert_raw.get("scheme", ""),
        note=cert_raw.get("note", ""),
        verification_status=gov.get("certification_basis", "UNVERIFIED"),
        basis=(f"{qco.get('name', '')} ({qco.get('notification', '')})".strip(" ()") if gov.get("certification_basis") == "VERIFIED" else ""),
        source_url=gov.get("source_url", ""),
    )
    return RegistryStandard(
        is_number=rec["is_number_clean"],
        title=rec["title"],
        category=rec["category"],
        scope_description=rec["scope_description"],
        latest_version=rec["latest_version"],
        amendment=rec["amendment"],
        certification=cert,
        archive_link=registry.archive_link(rec["is_number"], rec["latest_version"]),
        score=score,
        version_status=gov.get("version_status", "LOCAL_REGISTRY"),
        verification_status=gov.get("verification_status", "UNVERIFIED"),
        gov_edition=gov.get("gov_edition", ""),
        qco=qco,
    )


def _to_allied(entry: dict) -> AlliedStandard:
    cert = entry.get("certification") or {}
    return AlliedStandard(
        code=entry["code"],
        title=entry.get("title", ""),
        category=entry.get("category", ""),
        purpose=entry.get("purpose", "Related standard"),
        latest_version=entry.get("latest_version", ""),
        amendment=entry.get("amendment", ""),
        certification=_cert_info(cert) if cert else None,
        known=entry.get("known", False),
        archive_link=(
            registry.archive_link(entry["code"], entry.get("latest_version", ""))
            if entry.get("known")
            else registry.archive_search_link(entry["code"])
        ),
    )


def _build_tender_block(rec: dict, query: str) -> str:
    """Deterministic draft specification wording from the registry record."""
    parts: list[str] = []
    edition = rec["latest_version"] or ""
    year_m = re.search(r"(19|20)\d{2}", edition)
    edition_str = f":{year_m.group(0)}" if year_m else ""
    amended = f" (as amended — {rec['amendment']})" if rec["amendment"] else ""
    parts.append(f"Supply shall conform to {rec['is_number_clean']}{edition_str}{amended} — {rec['title']}.")

    allied_codes = [
        registry.get_by_is_number(ref)["is_number_clean"]
        for ref in rec.get("normative_refs", [])
        if registry.get_by_is_number(ref)
    ]
    if allied_codes:
        parts.append(f"Allied standards to be considered: {', '.join(allied_codes[:4])}.")

    cert = rec.get("certification", {})
    if cert.get("mandatory"):
        # PROVENANCE-AWARE tender wording (audit item 4): only QCO-backed
        # claims get the firm 'mandatory' clause; unverified claims are
        # worded as 'listed as requiring certification — confirm status'.
        gov = gov_provenance.provenance_for(rec)
        qco = gov.get("qco") or {}
        if gov.get("certification_basis") == "VERIFIED":
            qco_ref = f" under {qco.get('name', 'a Quality Control Order')}"
            if qco.get("notification"):
                qco_ref += f" ({qco['notification']})"
            parts.append(
                f"BIS certification is mandatory{qco_ref}."
                " Bidders must furnish a valid licence covering the specified grade/size."
            )
        else:
            parts.append(
                f"BIS certification is listed as applicable for this product ({cert.get('scheme', 'BIS')}); "
                "the governing notification should be confirmed on the BIS portal before this "
                "requirement is finalised."
            )
    elif cert.get("scheme"):
        parts.append(
            f"BIS certification is not mandatory for this product ({cert['scheme']}); "
            "consider requiring it as a quality condition for government procurement."
        )
    return " ".join(parts)


def _llm_polish_tender_block(rec: dict, query: str, base_block: str) -> str | None:
    """Optional LLM polish; returns None on any failure so the demo never breaks."""
    try:
        system = (
            "You draft concise tender specification clauses for Indian government procurement. "
            "Keep every standard code, edition, amendment and certification requirement EXACTLY as given. "
            "Do not invent standards, grades or values. Reply with only the specification text (2-4 sentences)."
        )
        user = (
            f"Procurement context: {query or 'general procurement'}\n"
            f"Standard: {rec['is_number_clean']} — {rec['title']}\n"
            f"Latest version: {rec['latest_version']}; Amendment: {rec['amendment'] or 'none'}\n"
            f"Certification: {rec['certification']}\n"
            f"Base draft:\n{base_block}\n\n"
            "Polish this into a single flowing tender clause."
        )
        return llm_complete(system, user, max_tokens=300, temperature=0.2).strip()
    except Exception:
        return None


def _llm_clarify(query: str, top_records: list[dict]) -> ClarifyPrompt | None:
    """Ask the LLM to generate disambiguation options from top matches."""
    if not top_records:
        return None
    try:
        system = (
            "You help procurement officials pick the correct Indian Standard (IS). "
            "The user's description is ambiguous. From the candidate standards provided, "
            "write a short question and 2-3 concrete options. Reply as strict JSON: "
            '{"question": "...", "helper": "...", "options": [{"label": "...", "query": "..."}]} '
            "where each 'query' restates the user's need plus that option's distinguishing words. "
            "No markdown, no extra keys."
        )
        cands = "\n".join(
            f"- {r['is_number_clean']}: {r['title']} (category: {r['category']})"
            for r in top_records[:5]
        )
        user = f"User query: {query}\n\nCandidate standards:\n{cands}"
        raw = llm_complete(system, user, max_tokens=350, temperature=0.2).strip()
        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
        import json

        data = json.loads(raw)
        options = [
            ClarifyOption(label=str(o.get("label", ""))[:120], query=str(o.get("query", ""))[:300])
            for o in data.get("options", [])[:4]
            if o.get("label") and o.get("query")
        ]
        if not options:
            return None
        return ClarifyPrompt(
            question=str(data.get("question", "Which of these matches your requirement?"))[:200],
            helper=str(data.get("helper", ""))[:250],
            options=options,
        )
    except Exception:
        return None


# ── Hybrid grounded pipeline (task: LLM + authoritative retrieval) ─────────

@router.post("/grounded-recommend")
async def grounded_recommend(req: ProcureRequest, request: Request) -> dict:
    """Full hybrid flow: LLM requirement understanding (with deterministic
    fallback) → existing local retrieval/scoring → LLM-assisted search plan →
    authoritative external retrieval for planned needs only → reconciliation
    against local data → deterministic ranking → grounded context → optional
    LLM explanation. The LLM never ranks, retrieves, or mutates data."""
    from app.services import pipeline, requirement

    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Query must not be empty.")

    out = pipeline.grounded_recommend(query, top_k=max(req.top_k, 4))
    # Attach a deterministic explanation when the LLM was unavailable.
    if not out.get("explanation"):
        out["explanation"] = pipeline.deterministic_explanation(out)

    # Interpretation-driven clarify (kept from the existing behaviour): if the
    # interpretation found ambiguities and the top candidate is weak, surface
    # the existing deterministic clarify prompt instead of guessing.
    if out.get("interpreted_requirement", {}).get("ambiguities") and not out["recommendations"]:
        rule = registry.clarify_options(query)
        if rule:
            out["clarify"] = rule
    store.record_event(
        session_id=_session_id(request), kind="grounded_recommendation",
        query=query, title=(out["recommendations"][0]["standard"]["is_number"] if out.get("recommendations") else ""),
        payload={
            "llm_used": out.get("explanation_source") == "llm",
            "external_calls": out.get("external_retrieval", {}).get("calls", 0),
            "discrepancies": [d for r in out.get("reconciliations", []) for d in r.get("discrepancies", [])],
            "warnings": out.get("warnings", []),
        },
    )
    return out


@router.get("/requirement-understanding")
async def requirement_understanding(q: str = Query(...)) -> dict:
    """LLM requirement extraction + query expansion (debug/inspection)."""
    from app.services import requirement

    if not q.strip():
        raise HTTPException(status_code=422, detail="Query must not be empty.")
    interpreted = requirement.interpret_requirement(q)
    expansion = requirement.expand_query(q, interpreted)
    return {"interpreted_requirement": interpreted, "query_expansion": expansion}


@router.post("/recommend", response_model=ProcureResponse)
async def procure_recommend(req: ProcureRequest, request: Request) -> ProcureResponse:
    """Semantic standard recommendation for a procurement description."""
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Query must not be empty.")

    # Ambiguity gate — ask one clarifying question instead of guessing.
    if len(query.split()) <= 25:
        rule = registry.clarify_options(query)
        if rule:
            return ProcureResponse(
                query=query,
                product_label="",
                clarify_needed=True,
                clarify=ClarifyPrompt(
                    question=rule["question"],
                    helper=rule["helper"],
                    options=[ClarifyOption(**o) for o in rule["options"]],
                ),
            )

    top = registry.search_registry(query, top_k=max(req.top_k, 4))
    if not top:
        return ProcureResponse(query=query, recommendations=[])

    best = top[0]

    # If the best match is weak and runners-up disagree, offer clarify options.
    # `_score` is the Match Score on a 0-1 scale — the same weighted factor
    # model the card displays (1.0 == perfect card), so the bar reads
    # "best card below 30/100" in every embedding mode: below that the match
    # is genuinely poor; specific product queries score 0.36+ and must NOT
    # be blocked by a clarify prompt. (The old 0.35/0.18 split was calibrated
    # for the retired private blend formula.)
    if best["_score"] < WEAK_MATCH_THRESHOLD and len(top) >= 2:
        prompt = _llm_clarify(query, top) or _fallback_clarify(query, top)
        if prompt:
            return ProcureResponse(query=query, clarify_needed=True, clarify=prompt)

    recommendations: list[ProcureRecommendation] = []
    for rec in top[: req.top_k]:
        base_block = _build_tender_block(rec, query)
        polished = _llm_polish_tender_block(rec, query, base_block) if rec is best else None
        allied = [_to_allied(e) for e in registry.allied_standards_for(rec)]
        recommendations.append(ProcureRecommendation(
            standard=_to_registry_standard(rec, rec["_score"]),
            relevance_score=rec["_score"],
            reason=_reason(rec, query),
            allied=allied,
            tender_block=polished or base_block,
            # P0-1: explainable Match Score from the real pipeline signals.
            match=scoring.score_breakdown(query, rec, rec["_score"]),
            # P0-2: structured, honest citations for the 'why'.
            evidence=evidence_service.build_claim_evidence(
                query, rec, bool(rec.get("certification", {}).get("mandatory"))
            ),
        ))

    response = ProcureResponse(query=query, product_label=best["category"], recommendations=recommendations)

    # P0-4: auditable history — candidates, scores, evidence, generated spec.
    response.history_id = store.record_event(
        session_id=_session_id(request),
        kind="recommendation",
        query=query,
        title=recommendations[0].standard.title if recommendations else "",
        payload={
            "selected": recommendations[0].standard.is_number if recommendations else "",
            "match_score": recommendations[0].match.score if recommendations and recommendations[0].match else None,
            "candidates": [
                {
                    "code": r.standard.is_number,
                    "title": r.standard.title,
                    "relevance_score": r.relevance_score,
                    "match_score": r.match.score if r.match else None,
                    "certification": r.standard.certification.model_dump(),
                }
                for r in recommendations
            ],
            "tender_block": recommendations[0].tender_block if recommendations else "",
            "evidence": [
                c.model_dump()
                for c in evidence_service.build_claim_evidence(
                    query, best, bool(best.get("certification", {}).get("mandatory"))
                )
            ] if recommendations else [],
        },
    )
    return response


def _fallback_clarify(query: str, top_records: list[dict]) -> ClarifyPrompt | None:
    """Category-based clarify when the LLM is unavailable."""
    cats: list[str] = []
    for r in top_records[:4]:
        if r["category"] not in cats:
            cats.append(r["category"])
    if len(cats) < 2:
        return None
    return ClarifyPrompt(
        question="Which of these best matches what you are procuring?",
        helper="Pick the closest category — the applicable standard differs between them.",
        options=[
            ClarifyOption(label=cat, query=f"{query} ({cat})")
            for cat in cats[:3]
        ],
    )


def _reason(rec: dict, query: str) -> str:
    cert = rec.get("certification", {})
    cert_str = (
        f" Certification is {'mandatory' if cert.get('mandatory') else 'voluntary'}"
        f" ({cert.get('scheme', 'BIS')})."
    )
    return (
        f"Matched on semantic similarity to your description (category: {rec['category']})."
        f"{cert_str}"
    )


@router.post("/clarify", response_model=ProcureResponse)
async def procure_clarify(req: ProcureRequest) -> ProcureResponse:
    """Regenerate a clarifying question for a query (used when the user backs out)."""
    top = registry.search_registry(req.query, top_k=5)
    prompt = _llm_clarify(req.query, top) or _fallback_clarify(req.query, top)
    if not prompt:
        rule = registry.clarify_options(req.query)
        if rule:
            prompt = ClarifyPrompt(
                question=rule["question"],
                helper=rule["helper"],
                options=[ClarifyOption(**o) for o in rule["options"]],
            )
    if not prompt:
        raise HTTPException(status_code=404, detail="No clarifying options available for this query.")
    return ProcureResponse(query=req.query, clarify_needed=True, clarify=prompt)


@router.post("/tender-block", response_model=TenderBlockResponse)
async def procure_tender_block(req: TenderBlockRequest) -> TenderBlockResponse:
    """Draft tender-specification wording for a standard (template-first)."""
    rec = registry.get_by_is_number(req.is_number)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"Standard '{req.is_number}' not found in the registry.")
    base = _build_tender_block(rec, req.context)
    polished = _llm_polish_tender_block(rec, req.context, base)
    return TenderBlockResponse(
        is_number=rec["is_number_clean"],
        tender_block=polished or base,
        generated_by="llm" if polished else "template",
    )


@router.post("/bulk-check", response_model=BulkCheckResponse)
async def procure_bulk_check(
    request: Request,
    files: list[UploadFile] = File(..., description="Tender/specification PDFs (max 500, 10 MB each)"),
) -> BulkCheckResponse:
    """Check multiple tender PDFs against the standards registry."""
    if not files:
        raise HTTPException(status_code=422, detail="No files uploaded.")
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=413, detail=f"Too many files — max {MAX_FILES} per request.")
    print(f"[bulk-check] {len(files)} file(s) received")

    results: list[FileCheckResult] = []
    for f in files:
        filename = f.filename or "untitled.pdf"
        if not filename.lower().endswith(".pdf"):
            results.append(FileCheckResult(
                file_name=filename,
                status="error",
                note="Only PDF files are supported in this version.",
            ))
            continue
        payload = await f.read()
        if len(payload) > MAX_FILE_BYTES:
            results.append(FileCheckResult(
                file_name=filename,
                status="error",
                note="File exceeds the 10 MB limit.",
            ))
            continue

        # Primary path: existing text extraction (unchanged behavior).
        text = tender_check.extract_text_from_pdf(payload, filename)
        result = tender_check.check_tender_text(filename, text)

        # P1-8: OCR fallback for scanned documents — only when text is thin.
        if not text.strip() or len(text.strip()) < 200:
            ocr = ocr_service.ocr_pdf(payload)
            ocr_status = OcrStatus(
                attempted=True, used=ocr["used"], pages=ocr["pages"],
                confidence=ocr["confidence"], message=ocr["message"],
            )
            if ocr["used"]:
                scanned = tender_check.check_tender_text(filename, ocr["text"])
                scanned.ocr = ocr_status
                scanned.note = (scanned.note + " " if scanned.note else "") + \
                    f"Text extracted via OCR fallback.{(' Low confidence - manual review recommended.') if (ocr['confidence'] is not None and ocr['confidence'] < 60) else ''}"
                result = scanned
            else:
                result.ocr = ocr_status
                if result.status == "error" and not text.strip():
                    result.note = (result.note + " " if result.note else "") + ocr["message"]
        results.append(result)

    passing = [r for r in results if r.status == "pass"]
    risk = risk_service.assess(results)  # P1-7: deterministic heatmap
    store.record_event(
        session_id=_session_id(request),
        kind="tender_check",
        query=f"{len(files)} tender document(s)",
        title=f"Bulk check - {len(results)} file(s)",
        payload={
            "total": len(results),
            "passing": len(passing),
            "overall_risk": risk.overall,
            "files": [
                {"file_name": r.file_name, "status": r.status, "issues": [i.model_dump() for i in r.issues]}
                for r in results
            ],
        },
    )
    return BulkCheckResponse(
        files=results,
        total=len(results),
        passing=len(passing),
        min_standards=tender_check.minimum_standards_set(results),
        risk=risk,
        # Demand vs availability rating across the batch (advisory analytics).
        demand_rating=demand_rating.rate_demand(results, len(results)),
        # Issues that could not be attributed to any single standard —
        # surfaced at tender/batch level instead of guessed onto a citation.
        batch_issues=demand_rating.batch_level_issues(results),
    )


@router.get("/standard/{is_number_raw:path}", response_model=RegistryStandard)
async def procure_standard_detail(is_number_raw: str) -> RegistryStandard:
    """Registry metadata for one standard (modal detail view)."""
    rec = registry.get_by_is_number(is_number_raw)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"Standard '{is_number_raw}' not found in the registry.")
    return _to_registry_standard(rec)


@router.get("/meta")
async def procure_meta() -> dict:
    """Registry stats — handy for the UI header and the demo."""
    meta = registry.registry_meta()
    cats: dict[str, int] = {}
    for r in registry.all_standards():
        cats[r["category"]] = cats.get(r["category"], 0) + 1
    return {
        "registry": meta,
        "categories": cats,
        "evidence_index": {
            "available": evidence_service.index_available(),
            "documents": len(evidence_service.indexed_codes()),
        },
        "ocr": ocr_service.availability(),
    }


@router.get("/health")
async def procure_health() -> dict:
    return {
        "status": "healthy",
        "registry_count": registry.registry_size(),
    }


# ── Explore: browse the registry by number or category ──────────────────────

@router.get("/browse")
async def procure_browse() -> dict:
    """Full browsable registry summary for the Explore tab.

    Powers (a) 'what is IS 1786?' number/title search and (b) the category
    grid. Read-only, cache-friendly, no auth.
    """
    standards = []
    for r in registry.all_standards():
        gov = gov_provenance.provenance_for(r)
        cert_basis = gov.get("certification_basis", "UNVERIFIED")
        standards.append({
            "code": r["is_number_clean"],
            "title": r["title"],
            "category": r["category"],
            "latest_version": r["latest_version"],
            "amendment": r["amendment"],
            "certification": {
                "mandatory": bool(r["certification"].get("mandatory")),
                "scheme": r["certification"].get("scheme", ""),
                "verification_status": cert_basis,
                "basis": (
                    f"{(gov.get('qco') or {}).get('name', '')} ({(gov.get('qco') or {}).get('notification', '')})".strip(" ()")
                    if cert_basis == "VERIFIED" else ""
                ),
            },
            "version_status": gov.get("version_status", "LOCAL_REGISTRY"),
            "archive_link": registry.archive_link(r["is_number"], r["latest_version"]),
        })
    categories: dict[str, int] = {}
    for r in registry.all_standards():
        categories[r["category"]] = categories.get(r["category"], 0) + 1
    return {"standards": standards, "categories": categories, "total": len(standards)}


# ── P0-2: clause/page evidence for the detail modal ─────────────────────────

@router.get("/evidence/{is_number_raw:path}", response_model=list[ClaimEvidence])
async def procure_evidence(is_number_raw: str, query: str = Query(default="")) -> list[ClaimEvidence]:
    """Structured, honest citations for one standard ('clause/page not indexed'
    when the corpus does not pin them down — never invented)."""
    rec = registry.get_by_is_number(is_number_raw)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"Standard '{is_number_raw}' not found in the registry.")
    return evidence_service.build_claim_evidence(
        query or rec["title"], rec, bool(rec["certification"].get("mandatory"))
    )


# ── Verification-audit reports (SIH26108 audit) ─────────────────────────

@router.get("/verification-report")
async def verification_report() -> dict:
    """Machine-readable government-verification report (audit item 14).

    Counts every registry standard by verification status, lists confirmed
    discrepancies and the certification-provenance of each standard.
    """
    from app.services import audit_report
    return audit_report.build_report()


@router.get("/manual-review")
async def manual_review() -> dict:
    """Worklist of fields a human must verify against official sources."""
    from app.services import audit_report
    return audit_report.build_manual_review()


# ── P0-3: BIS licence verification ──────────────────────────────────────────

@router.post("/verify", response_model=VerifyResponse)
async def procure_verify(req: VerifyRequest, request: Request) -> VerifyResponse:
    """Verify a supplier BIS licence against the official portal.

    Honest states only: valid / invalid / expired / not_found /
    unable_to_verify / source_unavailable — every response carries a
    'last verified' timestamp and says whether it came from cache.
    """
    result = verify_service.verify_licence(req.licence_number, req.supplier_name, req.is_number)
    store.record_event(
        session_id=_session_id(request),
        kind="verification",
        query=req.licence_number,
        title=req.supplier_name or req.licence_number,
        payload={"status": result["status"], "is_number": req.is_number, "detail": result["detail"]},
    )
    return VerifyResponse(**result)


# ── P0-4: audit / search history ────────────────────────────────────────────

@router.get("/history", response_model=HistoryListResponse)
async def procure_history(
    request: Request,
    limit: int = Query(default=50, ge=1, le=500),
    kind: str | None = Query(default=None, description="recommendation | clarify | tender_check | verification"),
) -> HistoryListResponse:
    """Audit history. With a session header, only that session's entries;
    without one, the local/demo store (single-user mode)."""
    sid = _session_id(request)
    events = store.list_history(limit=limit, kind=kind)
    if sid != "local":
        events = [e for e in events if e.get("session_id") in (sid, "local")]
    return HistoryListResponse(entries=[HistoryEntry(**e) for e in events], total=len(events))


@router.get("/history/{event_id}", response_model=HistoryEntry)
async def procure_history_detail(event_id: str) -> HistoryEntry:
    event = store.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="History entry not found.")
    return HistoryEntry(**event)


# ── P0-5: watchlist + change notifications ──────────────────────────────────

@router.get("/watchlist", response_model=WatchlistResponse)
async def procure_watchlist(
    check: bool = Query(default=True, description="Run deterministic change detection against the registry"),
) -> WatchlistResponse:
    if check:
        store.check_watchlist()
    items = [WatchlistItem(**i) for i in store.watchlist()]
    return WatchlistResponse(
        items=items,
        notifications=store.notifications(),
        total=len(items),
        checked_at=store.watchlist()[0]["last_checked"] if store.watchlist() else "",
    )


@router.post("/watchlist", response_model=WatchlistItem)
async def procure_watch_add(req: WatchRequest, request: Request) -> WatchlistItem:
    rec = registry.get_by_is_number(req.is_number)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"Standard '{req.is_number}' not found in the registry.")
    snapshot = {"title": rec["title"], "latest_version": rec["latest_version"], "amendment": rec["amendment"]}
    item = store.add_watch(rec["is_number_clean"], snapshot, req.note)
    store.record_event(
        session_id=_session_id(request),
        kind="watchlist",
        query=f"Watch {item['is_number']}",
        title=item.get("title", ""),
        payload={"action": "watch", "is_number": item["is_number"]},
    )
    return WatchlistItem(**item)


@router.delete("/watchlist/{is_number}")
async def procure_watch_remove(is_number: str, request: Request) -> dict:
    if not store.remove_watch(is_number):
        raise HTTPException(status_code=404, detail=f"'{is_number}' is not on the watchlist.")
    store.record_event(
        session_id=_session_id(request),
        kind="watchlist",
        query=f"Unwatch {is_number}",
        payload={"action": "unwatch", "is_number": is_number},
    )
    return {"removed": is_number}


# ── Privacy: session data deletion ───────────────────────────────────────────

@router.delete("/session-data")
async def procure_clear_session_data(request: Request) -> dict:
    """Delete all history/notifications tied to the caller's session id.

    Fired by the frontend on tab close / refresh (navigator.sendBeacon) so the
    promise made in the Terms & Conditions popup is actually enforced.
    """
    sid = _session_id(request)
    removed = store.clear_session_history(sid)
    return {"cleared": True, "session_id": sid if sid != "local" else "(local)", "removed": removed}


@router.get("/notifications", response_model=NotificationsResponse)
async def procure_notifications() -> NotificationsResponse:
    return NotificationsResponse(notifications=store.notifications(), unread=store.unread_count())


@router.post("/notifications/read")
async def procure_notifications_read(req: NotificationActionRequest) -> dict:
    if not store.mark_notification_read(req.id):
        raise HTTPException(status_code=404, detail="Notification not found.")
    return {"read": req.id}


# ── P1-1: comparison matrix ─────────────────────────────────────────────────

@router.post("/compare", response_model=CompareResponse)
async def procure_compare(req: CompareRequest) -> CompareResponse:
    codes = [c for c in dict.fromkeys(code.strip() for code in req.codes) if c]
    if len(codes) < 2:
        raise HTTPException(status_code=422, detail="Provide at least 2 standards to compare.")
    if len(codes) > 5:
        raise HTTPException(status_code=422, detail="Compare up to 5 standards at a time.")
    columns, attributes = compare_service.compare_columns(codes, req.query)
    if not any(c.found for c in columns):
        raise HTTPException(status_code=404, detail="None of the requested standards are in the registry.")
    return CompareResponse(columns=columns, attributes=attributes, query=req.query)


# ── P1-9: version comparison (only from indexed sources) ────────────────────

@router.get("/versions/{is_number_raw:path}", response_model=VersionCompareResponse)
async def procure_versions(
    is_number_raw: str,
    from_year: str | None = Query(default=None),
    to_year: str | None = Query(default=None),
) -> VersionCompareResponse:
    return versions_service.compare_versions(is_number_raw, from_year, to_year)


# ── P1-10: unified recommendation report ────────────────────────────────────

@router.post("/report", response_model=ReportResponse)
async def procure_report(req: ReportRequest) -> ReportResponse:
    report = report_service.build_report(req.query, req.code)
    if report is None:
        raise HTTPException(status_code=404, detail="No recommendation available for this requirement.")
    return report
