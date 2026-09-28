"""P0-1 — Explainable Match Score.

The recommendation pipeline (standards_registry.search_registry) actually
computes exactly two similarity signals per candidate:

- semantic:  cosine similarity between the query embedding and the record
             embedding (None when the ML stack is unavailable on this machine)
- keyword:   fraction of query tokens found in the record's title/category/
             scope/number fields

The Match Score is a transparent rescaling of the *real* hybrid score
(`_score`), and the factor breakdown is derived from genuinely computed
overlaps — never invented. Nothing here pretends to be a calibrated
probability: the UI must always label it "Match Score", never "confidence %".
"""

from __future__ import annotations

import re
from functools import lru_cache

from app.models.schemas import ScoreBreakdown, ScoreFactor

# Blend weights — the SINGLE ranking formula. search_registry() ranks with
# exactly these weighted factors, and score_breakdown() displays the same
# factors with the same weights, so the card total is literally the weighted
# average of the bars shown (was: a separate engine formula that could not
# be reconciled with the factor list — "everything ~60 but total 83").
FACTOR_WEIGHTS: dict[str, float] = {
    "semantic": 0.35,
    "keyword": 0.30,
    "category": 0.15,
    "application": 0.15,
    "title": 0.05,
}

# Observably, keyword-only scores cap out much lower than blended ones
# (the router already uses 0.18 vs 0.35 thresholds on the same principle).
# Each signal is rescaled against its own realistic ceiling so the displayed
# factor is comparable across modes without inventing precision.
KEYWORD_CEILING = 0.75
SEMANTIC_CEILING = 0.85

STOPWORDS = {
    "for", "the", "a", "an", "of", "in", "on", "and", "or", "to", "with",
    "is", "are", "be", "by", "as", "at", "from", "that", "this", "it",
}


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if t not in STOPWORDS}


@lru_cache(maxsize=1)
def _category_vocab() -> dict[str, tuple[frozenset[str], int]]:
    """Per-category vocabulary computed from the registry itself (deterministic).

    For each category: token frequencies across the titles + scope descriptions
    of ALL its records; keep the top 40 tokens plus the category-name tokens.

    Why: the old 'Product category' factor measured token overlap against the
    2-3 words of the category NAME ('Steel & Metal Products'), which almost
    never appear in a natural query ('Reinforcement bars for concrete...') and
    therefore read as a useless constant 0%. Measuring against the category's
    actual vocabulary (drawn from real standard descriptions) makes the factor
    meaningful while staying grounded in registry data — nothing invented.
    """
    from collections import Counter

    from app.services import standards_registry as registry

    freqs: dict[str, Counter] = {}
    counts: dict[str, int] = {}
    for rec in registry.all_standards():
        cat = rec.get("category", "") or ""
        if not cat:
            continue
        counts[cat] = counts.get(cat, 0) + 1
        text = f"{rec.get('title', '')} {rec.get('scope_description', '')}"
        toks = [
            t for t in re.findall(r"[a-z0-9]+", text.lower())
            if t not in STOPWORDS and len(t) > 2
        ]
        freqs.setdefault(cat, Counter()).update(toks)

    vocab: dict[str, tuple[frozenset[str], int]] = {}
    for cat, counter in freqs.items():
        top = [t for t, _ in counter.most_common(40)]
        vocab[cat] = (frozenset(top) | _tokens(cat), counts.get(cat, 0))
    return vocab


def _pct(x: float) -> int:
    """Clamp a 0..1 ratio to a display integer 0..100 without fake precision."""
    return max(0, min(100, round(max(0.0, min(1.0, x)) * 100)))


def _factor_values(query: str, record: dict) -> list[dict]:
    """Compute the five similarity factors for one record (shared by ranking
    and display so they can never drift apart).

    Returns dicts: {key, value (0-100 int), weight (effective %, int)}.
    'semantic' is present only when the engine actually computed it.
    """
    q_tokens = _tokens(query)
    semantic = record.get("_semantic")
    keyword = float(record.get("_keyword") or 0.0)

    out: list[dict] = []
    if semantic is not None:
        out.append({"key": "semantic", "value": _pct(semantic / SEMANTIC_CEILING), "weight": FACTOR_WEIGHTS["semantic"]})

    out.append({"key": "keyword", "value": _pct(keyword / KEYWORD_CEILING), "weight": FACTOR_WEIGHTS["keyword"]})

    category = record.get("category", "") or ""
    cat_vocab, _cat_count = _category_vocab().get(category, (frozenset(), 0))
    cat_overlap = len(q_tokens & set(cat_vocab)) / len(q_tokens) if (q_tokens and cat_vocab) else 0.0
    out.append({"key": "category", "value": _pct(cat_overlap), "weight": FACTOR_WEIGHTS["category"]})

    scope_tokens = _tokens(record.get("scope_description", "") or "")
    scope_overlap = len(q_tokens & scope_tokens) / len(q_tokens) if (q_tokens and scope_tokens) else 0.0
    out.append({"key": "application", "value": _pct(scope_overlap), "weight": FACTOR_WEIGHTS["application"]})

    title_tokens = _tokens(record.get("title", "") or "")
    title_overlap = len(q_tokens & title_tokens) / len(q_tokens) if (q_tokens and title_tokens) else 0.0
    out.append({"key": "title", "value": _pct(title_overlap), "weight": FACTOR_WEIGHTS["title"]})

    # Renormalize weights over the factors actually present (keyword-only mode
    # drops 'semantic'; renormalizing keeps the total a true weighted average).
    total_w = sum(f["weight"] for f in out) or 1.0
    for f in out:
        f["weight"] = round(f["weight"] / total_w * 100)
    return out


def weighted_total(factors: list[dict]) -> int:
    """The Match Score: weighted average of the displayed factors, rounded.

    Certification is deliberately NOT part of this total — it is a mandatory/
    voluntary status flag, not a similarity; showing it inside an average
    would let a status bit move a 'fit' score up and down.
    """
    tw = sum(f["weight"] for f in factors) or 1
    return round(sum(f["value"] * f["weight"] for f in factors) / tw)


def _confidence(score: float, semantic_available: bool, keyword_score: float) -> str:
    """Qualitative confidence derived from the same real signals (not a fake %)."""
    if semantic_available:
        if score >= 0.45:
            return "High"
        if score >= 0.25:
            return "Medium"
        return "Low"
    # keyword-only mode: overlap fractions are directly interpretable
    if keyword_score >= 0.6:
        return "High"
    if keyword_score >= 0.3:
        return "Medium"
    return "Low"


def score_breakdown(query: str, record: dict, hybrid_score: float) -> ScoreBreakdown:
    """Build the explainable breakdown for one candidate record.

    `record` must carry the `_semantic` / `_keyword` raw signals injected by
    search_registry(). The five similarity factors come from ONE shared
    computation (_factor_values) that ranking also uses — with the same
    weights — so the displayed total is exactly the weighted average of the
    bars on the card. Certification is shown as a status line, not folded
    into the average. Nothing here is invented.
    """
    query = (query or "").strip()
    semantic = record.get("_semantic")          # float | None
    keyword = float(record.get("_keyword") or 0.0)
    semantic_available = semantic is not None

    signals: dict[str, float | None] = {
        "hybrid": round(hybrid_score, 4),
        "semantic": round(semantic, 4) if semantic_available else None,
        "keyword": round(keyword, 4),
    }

    raw = _factor_values(query, record)
    display_score = weighted_total(raw)

    DETAIL = {
        "semantic": "Cosine similarity between your requirement and the standard's "
                    "title + scope text (MiniLM sentence embeddings).",
        "keyword": "Share of meaningful words from your requirement found in the "
                   "standard's title, category, scope and code.",
        "category": None,  # needs the dynamic category count — filled below
        "application": "Words from your requirement appearing in the standard's "
                       "scope description.",
        "title": "Words from your requirement appearing in the standard's title.",
    }
    LABEL = {
        "semantic": "Semantic relevance",
        "keyword": "Keyword match",
        "category": "Product category",
        "application": "Application fit",
        "title": "Title specificity",
    }

    category = record.get("category", "") or ""
    _cv, cat_count = _category_vocab().get(category, (frozenset(), 0))
    cat_detail = (
        f"Words from your requirement found in the working vocabulary of "
        f"the '{category}' category ({cat_count} standards' titles and scopes)."
        if category else "No category recorded for this standard."
    )

    factors = [
        ScoreFactor(
            label=LABEL[f["key"]],
            value=f["value"],
            weight=f["weight"],
            detail=cat_detail if f["key"] == "category" else DETAIL[f["key"]],
        )
        for f in raw
    ]

    # --- Certification: status line, NOT part of the weighted average -------
    # Real signal: whether the registry says certification applies to this
    # product — a mandatory/voluntary flag, not a similarity; putting it in
    # the average would let a status bit move a 'fit' score up and down.
    # PROVENANCE-AWARE (audit item 4): the detail line states whether the
    # mandatory claim is QCO-backed or unverified.
    cert = record.get("certification", {}) or {}
    cert_applicable = bool(cert.get("mandatory"))
    from app.services import gov_provenance
    gov = gov_provenance.provenance_for(record)
    qco = gov.get("qco") or {}
    if cert_applicable:
        if gov.get("certification_basis") == "VERIFIED":
            cert_detail = (
                f"BIS certification is mandatory for this product "
                f"under {qco.get('name') or 'a Quality Control Order'}"
                + (f" ({qco.get('notification')})" if qco.get("notification") else "")
                + "."
            )
        else:
            cert_detail = (
                f"Curated data lists BIS certification ({cert.get('scheme') or 'BIS'}) for this "
                "product, but no government notification backing the requirement has been "
                "verified — manual review required."
            )
    else:
        cert_detail = "Certification is not flagged mandatory for this product in the registry."
    factors.append(ScoreFactor(
        label="Certification",
        value=100 if cert_applicable else 0,
        weight=0,  # excluded from the weighted average (status, not similarity)
        detail=cert_detail,
    ))

    return ScoreBreakdown(
        score=display_score,
        factors=factors,
        signals=signals,
        embedding_mode="semantic" if semantic_available else "keyword_only",
        confidence=_confidence(hybrid_score, semantic_available, keyword),
    )


def rescore_record(query: str, record: dict) -> tuple[dict, float] | None:
    """Re-score an existing record through the REAL pipeline for a raw query.

    Used by comparison/report so a displayed Match Score is exactly what the
    recommendation engine would produce for that query — no title-boosting,
    no separate formula. Returns (record_with_signals, hybrid_score) or None
    when the record does not surface for the query at all.
    """
    from app.services import standards_registry as registry

    hits = registry.search_registry(query, top_k=15)
    for h in hits:
        if h["core_number"] == record["core_number"]:
            return h, h["_score"]
    return None
