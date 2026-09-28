"""LLM Job #1/#2/#3 — requirement understanding, query expansion, search planning.

Contract (task §5-§7, §15):
- The LLM ONLY interprets/plans. Every field it returns is advisory.
- All LLM output is parsed defensively; on ANY failure the deterministic
  fallback (regex/rule-based, matching the existing clarify behaviour) runs,
  so the pipeline works with no LLM at all.
- The LLM never talks to the network and never retrieves anything.
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache

from app.services import prompts
from app.services.llm import llm_complete

log = logging.getLogger("setu.requirement")

# Product vocabulary for the deterministic fallback (extends the existing
# clarify rules in standards_registry.clarify_options).
_PRODUCT_HINTS = {
    "cement": ["cement"],
    "steel": ["steel", "rebar", "reinforcement", "tmt", "beam", "section"],
    "cable": ["cable", "wire", "pvc insulated", "conductor"],
    "pipe": ["pipe", "tube", "hose", "conduit"],
    "brick": ["brick", "masonry"],
    "aggregate": ["aggregate", "gravel", "sand", " grit"],
    "paint": ["paint", "coating", "primer", "emulsion"],
    "plywood": ["plywood", "timber", "wood"],
    "helmet": ["helmet", "headgear"],
    "pump": ["pump", "submersible", "monoblock"],
}

_AMBIGUITY_HINTS = {
    "cement_type": {
        "trigger": re.compile(r"\bcement\b", re.IGNORECASE),
        "guard": re.compile(r"\b(OPC|PPC|PSC|43|53|33|grade|portland pozzolana|sulphate)\b", re.IGNORECASE),
        "reason": "Cement type/grade was not specified",
        "possible_values": ["OPC 33", "OPC 43", "OPC 53", "PPC", "PSC"],
    },
    "steel_form": {
        "trigger": re.compile(r"\bsteel\b", re.IGNORECASE),
        "guard": re.compile(r"\b(rebar|reinforc|beam|plate|section|sheet|tube|pipe|tmt|structural)\b", re.IGNORECASE),
        "reason": "Steel product form was not specified",
        "possible_values": ["reinforcement bars", "structural sections", "plates", "sheets", "tubes"],
    },
    "pipe_material": {
        "trigger": re.compile(r"\b(pipe|tube)\b", re.IGNORECASE),
        "guard": re.compile(r"\b(PVC|HDPE|GI|galvan|steel|copper|CPVC|SWR|ductile|cement)\b", re.IGNORECASE),
        "reason": "Pipe material was not specified",
        "possible_values": ["PVC", "HDPE", "GI (galvanized steel)", "CPVC", "ductile iron"],
    },
}


def _extract_json(text: str) -> dict | None:
    """Parse the first JSON object from an LLM reply (defensive)."""
    if not text:
        return None
    s = text.strip()
    # tolerate markdown fences
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.IGNORECASE).strip()
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        out = json.loads(s[start:end + 1])
        return out if isinstance(out, dict) else None
    except json.JSONDecodeError:
        return None


def _llm_json(system: str, user: str, max_tokens: int = 500) -> dict | None:
    try:
        raw = llm_complete(system, user, max_tokens=max_tokens, temperature=0.1)
        return _extract_json(raw)
    except Exception as exc:  # noqa: BLE001 — deterministic fallback is the point
        log.info("llm json call failed", extra={"error": type(exc).__name__})
        return None


# --------------------------------------------------------------------------- #
# Job 1: requirement understanding                                            #
# --------------------------------------------------------------------------- #

def _fallback_interpret(query: str) -> dict:
    """Rule-based requirement interpretation (no LLM)."""
    q = query.lower()
    products = sorted({p for p, hints in _PRODUCT_HINTS.items() if any(h in q for h in hints)})
    procurement_type = "government" if re.search(r"government|public sector|govt|psu|department", q) else ""
    variant = ""
    m = re.search(r"\b(OPC\s*(?:33|43|53)?|PPC|PSC)\b", query, re.IGNORECASE)
    if m:
        variant = m.group(1).upper()
    application = ""
    am = re.search(r"(?:for|in)\s+([a-z ]{4,40}?(?:construction|project|building|road|bridge|water supply|irrigation|housing|pipeline))", q)
    if am:
        application = am.group(1).strip()

    ambiguities = []
    for field, spec in _AMBIGUITY_HINTS.items():
        if spec["trigger"].search(q) and not spec["guard"].search(q):
            ambiguities.append({
                "field": field, "reason": spec["reason"],
                "possible_values": spec["possible_values"],
            })

    explicit = re.findall(r"\bIS\s*[:\-]?\s*\d{2,6}(?:\s*\(\s*Part\s*\w+\s*\))?", query, re.IGNORECASE)
    requested = []
    if re.search(r"tender|specification|draft", q):
        requested += ["applicable standards", "tender requirements"]
    if re.search(r"current|latest|edition|version", q):
        requested.append("current edition")
    if re.search(r"certif|isi|qco|licence", q):
        requested += ["certification requirements"]

    return {
        "product": products[0] if products else "",
        "product_candidates": products,
        "material": "",
        "variant": variant,
        "application": application,
        "procurement_type": procurement_type,
        "technical_requirements": [],
        "requested_information": requested,
        "explicit_standard_numbers": [e.upper().replace("IS ", "IS ").replace("  ", " ") for e in explicit],
        "ambiguities": ambiguities,
        "source": "deterministic_fallback",
    }


def interpret_requirement(query: str) -> dict:
    """LLM-assisted requirement extraction; deterministic fallback on failure."""
    if not (query or "").strip():
        return _fallback_interpret(query or "")
    out = _llm_json(prompts.REQUIREMENT_EXTRACTION, f"User requirement:\n{query}", max_tokens=600)
    if not out or not isinstance(out.get("product", ""), str):
        fb = _fallback_interpret(query)
        fb["llm_available"] = False
        return fb
    out.setdefault("ambiguities", [])
    out.setdefault("explicit_standard_numbers", [])
    out.setdefault("requested_information", [])
    out["source"] = "llm"
    out["llm_available"] = True
    return out


# --------------------------------------------------------------------------- #
# Job 2: query expansion (search hints only)                                  #
# --------------------------------------------------------------------------- #

_EXPANSION_FALLBACK = {
    "steel": ["structural steel", "steel sections", "hot rolled steel"],
    "cement": ["portland cement", "pozzolana cement"],
    "cable": ["pvc cable", "insulated cable", "electrical wire"],
    "pipe": ["water pipe", "steel pipe", "plastic pipe"],
}


def _fallback_expansions(query: str) -> dict:
    q = query.lower()
    expansions: list[str] = []
    for p, hints in _PRODUCT_HINTS.items():
        if any(h in q for h in hints):
            expansions += _EXPANSION_FALLBACK.get(p, [])
    if "road" in q or "construction" in q:
        expansions.append("construction works")
    return {"expansions": list(dict.fromkeys(expansions))[:6], "source": "deterministic_fallback"}


def expand_query(query: str, interpreted: dict | None = None) -> dict:
    """LLM search hints; never facts. Deterministic fallback included."""
    out = _llm_json(
        prompts.QUERY_EXPANSION,
        f"Requirement: {query}\nInterpreted as: {prompts.user_payload(interpreted or {})}",
        max_tokens=300,
    )
    if out and isinstance(out.get("expansions"), list):
        clean = [str(e).strip() for e in out["expansions"] if str(e).strip()][:8]
        return {"expansions": clean, "source": "llm"}
    fb = _fallback_expansions(query)
    fb["llm_available"] = False
    return fb


# --------------------------------------------------------------------------- #
# Job 3: search planning                                                      #
# --------------------------------------------------------------------------- #

_KNOWN_NEEDS = {
    "current_standard_edition", "certification_status", "qco", "effective_date",
    "issuing_authority", "government_notification", "scope_confirmation",
}

def _fallback_plan(query: str, interpreted: dict) -> dict:
    needs: list[str] = []
    if re.search(r"current|latest|edition|version|outdated", query, re.IGNORECASE):
        needs.append("current_standard_edition")
    if re.search(r"certif|mandatory|isi|qco|licence", query, re.IGNORECASE):
        needs += ["certification_status", "qco"]
    if not needs:
        needs.append("certification_status")
    return {"needs": needs, "source": "deterministic_fallback"}


def plan_retrieval(query: str, interpreted: dict, candidates: list[dict] | None = None) -> dict:
    """What the application should verify externally. LLM plans; app acts."""
    needs: list[str] = []
    # Deterministic triggers always run (cheap, reliable).
    det = _fallback_plan(query, interpreted)
    needs += det["needs"]
    # Candidates with weak provenance always need verification.
    for c in (candidates or [])[:5]:
        cert = ((c.get("standard") or {}).get("certification") or {})
        if cert.get("mandatory") and cert.get("verification_status") not in ("VERIFIED",):
            if "certification_status" not in needs:
                needs.append("certification_status")
            if "qco" not in needs:
                needs.append("qco")
    needs = [n for n in dict.fromkeys(needs) if n in _KNOWN_NEEDS]

    llm = _llm_json(
        prompts.SEARCH_PLANNING,
        f"Requirement: {query}\nInterpreted: {prompts.user_payload(interpreted)}\n"
        f"Candidate codes: {[ (c.get('standard') or {}).get('is_number') for c in (candidates or [])[:5] ]}",
        max_tokens=250,
    )
    if llm and isinstance(llm.get("needs"), list):
        for n in llm["needs"]:
            n = str(n).strip().lower()
            if n in _KNOWN_NEEDS and n not in needs:
                needs.append(n)
    return {"needs": needs, "source": "llm+deterministic" if llm else "deterministic_fallback"}
