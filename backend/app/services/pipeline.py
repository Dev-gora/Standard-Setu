"""The hybrid intelligence pipeline (task §1, §16-§17).

Flow: understand (LLM/fallback) → local retrieval (existing engine) →
search planning (LLM/fallback) → authoritative external retrieval (only for
identified needs) → reconciliation → deterministic ranking (existing scoring)
→ grounded context → LLM explanation (optional).

The LLM never retrieves, never ranks, never mutates data. Deterministic
outputs (recommendations, discrepancies, verification states) are computed
by the application and only *explained* by the LLM.
"""

from __future__ import annotations

import logging
import time

from app.services import external_sources, gov_provenance, prompts, reconciliation, requirement
from app.services import standards_registry as registry

log = logging.getLogger("setu.pipeline")


def _plain(rec: dict) -> dict:
    """Slim a candidate for the grounded context (token-frugal)."""
    std = rec.get("standard") or {}
    cert = std.get("certification") or {}
    return {
        "is_number": std.get("is_number"),
        "title": std.get("title"),
        "category": std.get("category"),
        "registry_edition": std.get("latest_version"),
        "amendment": std.get("amendment"),
        "match_score": rec.get("match", {}).get("score") if rec.get("match") else None,
        "match_factors": [
            {"label": f.get("label"), "value": f.get("value")} for f in (rec.get("match", {}) or {}).get("factors", [])[:5]
        ] if rec.get("match") else [],
        "certification": {
            "mandatory": cert.get("mandatory"),
            "verification_status": cert.get("verification_status", "UNVERIFIED"),
            "basis": cert.get("basis", ""),
        },
        "version_status": std.get("version_status", "LOCAL_REGISTRY"),
        "evidence": [
            {"kind": e.get("kind"), "claim": (e.get("claim") or "")[:140],
             "source_type": (e.get("evidence") or {}).get("source_type", ""),
             "page": (e.get("evidence") or {}).get("page"),
             "clause": (e.get("evidence") or {}).get("clause")}
            for e in (rec.get("evidence") or [])[:4]
        ],
    }


def grounded_recommend(query: str, top_k: int = 4) -> dict:
    """Full hybrid flow for one natural-language requirement."""
    t0 = time.time()
    result: dict = {"query": query}

    # 1. Understand (LLM with deterministic fallback)
    interpreted = requirement.interpret_requirement(query)
    result["interpreted_requirement"] = interpreted

    # 2. Query expansion (hints only — fed into the existing engine)
    expansion = requirement.expand_query(query, interpreted)
    result["query_expansion"] = expansion

    # 3. LOCAL RETRIEVAL — the existing hybrid engine, untouched. Expansion
    #    hints run as extra queries; candidates merge by best score.
    expanded_query = query
    if expansion.get("expansions"):
        expanded_query = f"{query} {' '.join(expansion['expansions'][:3])}"
    hits = registry.search_registry(expanded_query, top_k=max(top_k * 2, 8))
    if not hits:
        hits = registry.search_registry(query, top_k=max(top_k * 2, 8))

    # 4. Deterministic scoring/explanation through the EXISTING path.
    from app.routers.procurement import _reason, _to_registry_standard, scoring
    from app.services import evidence as evidence_service

    candidates = []
    for rec in hits[:top_k]:
        candidates.append({
            "standard": _to_registry_standard(rec, rec["_score"]).model_dump(),
            "relevance_score": rec["_score"],
            "reason": _reason(rec, query),
            "match": scoring.score_breakdown(query, rec, rec["_score"]).model_dump(),
            "evidence": [e.model_dump() for e in evidence_service.build_claim_evidence(
                query, rec, bool(rec.get("certification", {}).get("mandatory"))
            )],
            "registry_record": rec,
        })
    result["candidate_count"] = len(candidates)

    # 5. Search planning — what needs authoritative verification?
    plan = requirement.plan_retrieval(query, interpreted, candidates)
    result["retrieval_plan"] = plan

    # 6. EXTERNAL RETRIEVAL — only for planned needs, only for top candidates.
    reconciliations: list[dict] = []
    facts_by_code: dict[str, list[dict]] = {}
    external_calls = 0
    for cand in candidates[:top_k]:
        code = cand["standard"]["is_number"]
        need_facts: list[dict] = []
        for need in plan.get("needs", []):
            got = external_sources.retrieve_external(need, code)
            external_calls += 1
            need_facts += got
        if need_facts:
            facts_by_code[code] = need_facts
    if facts_by_code:
        reconciliations = reconciliation.reconcile_many(
            [c["registry_record"] for c in candidates], facts_by_code
        )
    result["external_sources"] = external_sources.available_sources()
    result["external_retrieval"] = {"calls": external_calls, "triggered": bool(facts_by_code)}
    result["reconciliations"] = reconciliations

    # 7. Deterministic ranking stands; attach reconciliation to candidates.
    recon_by_code = {r["standard"]: r for r in reconciliations}
    slim = []
    for cand in candidates:
        c = {k: v for k, v in cand.items() if k != "registry_record"}
        c["reconciliation"] = recon_by_code.get(c["standard"]["is_number"])
        slim.append(c)
    result["recommendations"] = slim

    # 8. Warnings aggregated from discrepancies + provenance.
    warnings: list[str] = []
    for r in reconciliations:
        for d in r.get("discrepancies", []):
            warnings.append(f"{d['standard']}: {d['type']} — local '{d['local_value']}' vs external '{d['external_value']}' ({d['status']})")
        if r.get("verification_status") == "SOURCE_UNAVAILABLE":
            warnings.append(f"{r['standard']}: authoritative source unavailable — nothing externally verified")
    unverified_cert = [
        c["standard"]["is_number"] for c in slim
        if (c["standard"]["certification"].get("mandatory")
            and c["standard"]["certification"].get("verification_status") != "VERIFIED")
    ]
    if unverified_cert:
        warnings.append(
            "Mandatory-certification claims not QCO-backed at audit time: "
            + ", ".join(unverified_cert) + " — manual review required."
        )
    result["warnings"] = warnings

    # 9. Verification status summary.
    result["verification_status"] = sorted({r.get("verification_status", "UNVERIFIED") for r in reconciliations}) or \
        (["PARTIALLY_VERIFIED"] if slim else ["UNVERIFIED"])

    # 10. Grounded context + optional LLM explanation.
    grounded = {
        "user_requirement": query,
        "interpreted_requirement": {k: v for k, v in interpreted.items() if k != "source"},
        "candidate_standards": [_plain(c) for c in slim],
        "verified_information": [
            {"standard": r["standard"], "status": r["verification_status"], "notes": r.get("notes", [])}
            for r in reconciliations
        ],
        "external_sources": result["external_sources"],
        "discrepancies": [d for r in reconciliations for d in r.get("discrepancies", [])],
        "verification_status": result["verification_status"],
        "scores": {c["standard"]["is_number"]: c["match"].get("score") for c in slim},
        "warnings": warnings,
    }
    result["grounded_context"] = grounded

    explanation = _explain(grounded, interpreted)
    result["explanation"] = explanation
    result["explanation_source"] = "llm" if explanation else "deterministic_fallback"
    result["generation_time_ms"] = int((time.time() - t0) * 1000)
    log.info("grounded pipeline done", extra={
        "candidates": len(slim), "external_calls": external_calls,
        "llm": bool(explanation), "ms": result["generation_time_ms"],
    })
    return result


def _explain(grounded: dict, interpreted: dict) -> str | None:
    """Final LLM generation — strictly over the grounded context."""
    try:
        from app.services.llm import llm_complete
        return llm_complete(
            prompts.FINAL_ANSWER,
            "Grounded context (the application retrieved everything below):\n"
            + prompts.user_payload(grounded),
            max_tokens=700,
            temperature=0.2,
        ).strip()
    except Exception as exc:  # noqa: BLE001 — deterministic answer path exists
        log.info("llm explanation unavailable", extra={"error": type(exc).__name__})
        return None


def deterministic_explanation(result: dict) -> str:
    """Structured non-LLM answer (task §21 — never fail on missing LLM)."""
    lines: list[str] = []
    top = (result.get("recommendations") or [{}])[0]
    std = top.get("standard") or {}
    if std:
        lines.append(f"Top match: {std.get('is_number')} — {std.get('title')} (Match Score {top.get('match', {}).get('score')}/100).")
        lines.append(f"Why: {top.get('reason', '')}")
    for w in result.get("warnings", [])[:5]:
        lines.append(f"⚠ {w}")
    if result.get("explanation_source") != "llm":
        lines.append("LLM explanation unavailable — the deterministic pipeline produced this answer; retrieval, scoring and verification above are unaffected.")
    return "\n".join(lines)
