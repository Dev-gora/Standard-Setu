"""Score reconciliation — the card total must be the weighted average of the
factors shown, and ranking must use the same factor model (no drift between
the search engine's `_score` and the displayed Match Score).

Regression for: "total score and parameter scores don't add up — everything
around 60 still showing 83" (the total came from a private engine blend while
the factors were separate diagnostics).
"""

from fastapi.testclient import TestClient

from app.main import app
from app.services import scoring
from app.services import standards_registry as registry

client = TestClient(app)

QUERIES = [
    "Reinforcement bars for concrete works",
    "OPC 43 grade cement for bridge construction",
    "Structural steel plates for bridge girders",
    "Galvanized iron sheets for roofing",
    "OPC 33 grade cement for plastering work",
    "Brass fittings for plumbing",
    "PVC insulated cables for internal wiring",
    "Copper wiring for house electrics",
]


def test_card_total_is_weighted_average_of_factors():
    """The displayed Match Score must be reproducible from the factor list."""
    for query in QUERIES:
        r = client.post("/api/procure/recommend", json={"query": query, "top_k": 3})
        assert r.status_code == 200, query
        recs = r.json()["recommendations"]
        assert recs, query
        for rec in recs:
            match = rec["match"]
            factors = [f for f in match["factors"] if f["weight"] > 0]
            assert factors, "at least one weighted factor expected"
            total_w = sum(f["weight"] for f in factors)
            expected = round(sum(f["value"] * f["weight"] for f in factors) / total_w)
            assert match["score"] == expected, (
                f"card total {match['score']} != weighted average {expected} "
                f"for {query!r} / {rec['standard']['code']}"
            )


def test_certification_excluded_from_average():
    """Certification is a status line (weight 0), not part of the average."""
    r = client.post("/api/procure/recommend", json={"query": QUERIES[0], "top_k": 1})
    match = r.json()["recommendations"][0]["match"]
    certs = [f for f in match["factors"] if f["label"] == "Certification"]
    assert certs, "certification status line expected"
    assert all(f["weight"] == 0 for f in certs)
    assert any(f["weight"] > 0 for f in match["factors"])


def test_rank_order_matches_card_totals_no_inversions():
    """Ranking uses the displayed factor model, so card totals never invert."""
    for query in QUERIES:
        r = client.post("/api/procure/recommend", json={"query": query, "top_k": 4})
        recs = r.json()["recommendations"]
        totals = [rec["match"]["score"] for rec in recs]
        assert totals == sorted(totals, reverse=True), (query, totals)


def test_engine_rank_score_matches_displayed_total():
    """`_score` (0-1) and the card total (0-100) are the same model, scaled."""
    for query in QUERIES:
        hits = registry.search_registry(query, top_k=1)
        assert hits, query
        top = hits[0]
        expected = scoring.weighted_total(scoring._factor_values(query, top))
        assert abs(top["_score"] * 100 - expected) <= 1, (query, top["_score"], expected)


def test_rebar_crushed_tender_case_reconciles():
    """The original repro: IS 1786 showed total 83 with all factors ~60.

    Now the total is the weighted average of the very factors on the card.
    """
    hits = registry.search_registry("Reinforcement bars for concrete works", top_k=3)
    top = hits[0]
    assert top["is_number"].startswith("IS 1786"), [h["is_number"] for h in hits]
    breakdown = scoring.score_breakdown(
        "Reinforcement bars for concrete works", top, top["_score"]
    )
    weighted = [f for f in breakdown.factors if f.weight > 0]
    total = round(sum(f.value * f.weight for f in weighted) / sum(f.weight for f in weighted))
    assert breakdown.score == total


def test_weights_renormalize_in_keyword_only_mode():
    """Weights always sum to 100 over the factors actually present."""
    hits = registry.search_registry(QUERIES[0], top_k=2)
    factors = scoring._factor_values(QUERIES[0], hits[0])
    semantic_present = hits[0].get("_semantic") is not None
    keys = {f["key"] for f in factors}
    assert ("semantic" in keys) == semantic_present
    assert sum(f["weight"] for f in factors) == 100


def test_weak_match_clarify_gate_pinned():
    """The clarify gate reads the card scale: only genuinely weak matches
    (< 30/100) with disagreeing runners-up trigger a clarify prompt."""
    from app.routers import procurement as proc

    assert proc.WEAK_MATCH_THRESHOLD == 0.30
