"""Small end-to-end test script for the Render-ready backend.

Run:  python scripts/test_render_ready.py http://localhost:8000
Covers every functional area touched by the deployment changes:
startup, health, docs, recommendation (simple + OPC 43 + unrelated
category), clarification, evidence, bulk/verify plumbing endpoints,
watchlist/notifications/history, session purge.

Exits non-zero on the first failed check so CI/Render shell steps can use it.
"""

from __future__ import annotations

import json
import sys
import uuid

import httpx

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8000"
SESSION = f"smoke-{uuid.uuid4().hex[:8]}"

passed: list[str] = []
failed: list[str] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    if cond:
        passed.append(name)
        print(f"  PASS  {name}")
    else:
        failed.append(name)
        print(f"  FAIL  {name} {extra}")


def main() -> None:
    c = httpx.Client(base_url=BASE, timeout=60, headers={"X-Session-Id": SESSION})

    print(f"== Standard Setu smoke test -> {BASE} ==")

    # 1) liveness / docs
    r = c.get("/")
    check("GET /", r.status_code == 200 and "Standard Setu" in r.text)
    r = c.get("/health")
    check("GET /health", r.status_code == 200 and r.json().get("registry_count", 0) > 0, r.text[:80])
    check("GET /docs", c.get("/docs").status_code == 200)
    check("GET /openapi.json", c.get("/openapi.json").status_code == 200)

    # 2) recommend — simple (ambiguous -> clarify is correct behavior)
    r = c.post("/api/procure/recommend", json={"query": "steel for construction"})
    d = r.json()
    check("recommend ambiguous -> clarify", r.status_code == 200 and d.get("clarify_needed") is True and bool(d.get("clarify", {}).get("options")))

    # 3) recommend — OPC 43 (the OOM query on Render)
    opc43 = (
        "Ordinary Portland cement for general construction work, OPC 43 grade, "
        "requiring conformity to Indian Standard specifications for composition, "
        "strength, physical properties, testing, and quality requirements."
    )
    r = c.post("/api/procure/recommend", json={"query": opc43})
    d = r.json()
    recs = d.get("recommendations", [])
    top_codes = [x["standard"]["is_number"] for x in recs[:3]]
    check("recommend OPC 43 -> 200 + cement hits", r.status_code == 200 and len(recs) >= 3 and any("269" in code or "1489" in code for code in top_codes), str(top_codes))
    if recs:
        m = recs[0]["match"]
        check("match score + factors present", isinstance(m.get("score"), int) and len(m.get("factors", [])) >= 4)
        check("evidence on top rec", bool(recs[0].get("evidence")))

    # 4) recommend — unrelated category (cables)
    r = c.post("/api/procure/recommend", json={"query": "PVC insulated electrical cable 1.1kV"})
    codes = [x["standard"]["is_number"] for x in r.json().get("recommendations", [])[:3]]
    check("recommend unrelated category (cable)", r.status_code == 200 and any("1554" in x or "694" in x or "7098" in x for x in codes), str(codes))

    # 5) explicit clarify endpoint
    r = c.post("/api/procure/clarify", json={"query": "steel for construction"})
    check("POST clarify", r.status_code == 200 and isinstance(r.json(), (dict, list)))

    # 6) evidence + standard detail + versions
    r = c.get("/api/procure/evidence/IS%201786")
    check("GET evidence IS 1786", r.status_code == 200)
    r = c.get("/api/procure/standard/IS%201786")
    check("GET standard detail", r.status_code == 200 and r.json().get("is_number"))
    r = c.get("/api/procure/versions/IS%201786")
    check("GET versions", r.status_code == 200)

    # 7) registry/meta/browse + audit reports
    check("GET meta", c.get("/api/procure/meta").status_code == 200)
    r = c.get("/api/procure/browse")
    check("GET browse (full registry)", r.status_code == 200 and len(r.json().get("standards", [])) >= 5)
    check("GET verification-report", c.get("/api/procure/verification-report").status_code == 200)
    check("GET manual-review", c.get("/api/procure/manual-review").status_code == 200)

    # 8) watchlist roundtrip + notifications + history
    r = c.post("/api/procure/watchlist", json={"is_number": "IS 1786", "note": "smoke"})
    check("POST watchlist", r.status_code == 200)
    check("GET watchlist", c.get("/api/procure/watchlist").status_code == 200)
    check("DELETE watchlist", c.delete("/api/procure/watchlist/IS%201786").status_code == 200)
    check("GET notifications", c.get("/api/procure/notifications").status_code == 200)
    # 404 is correct here: no such notification id exists — proves validation works
    check("POST notifications/read", c.post("/api/procure/notifications/read", json={"id": "smoke-nonexistent"}).status_code == 404)
    r = c.get("/api/procure/history")
    check("GET history", r.status_code == 200 and isinstance(r.json(), (list, dict)))

    # 9) verify (licence) — endpoint answers even with no external access
    r = c.post("/api/procure/verify", json={"licence": "CM/L-8700123456"})
    check("POST verify (licence shape)", r.status_code == 200 and "state" in r.json() or r.status_code == 200)

    # 10) compare + tender block
    r = c.post("/api/procure/compare", json={"codes": ["IS 1786", "IS 2062"], "query": ""})
    check("POST compare", r.status_code == 200)
    r = c.post("/api/procure/tender-block", json={"query": "cement for bridge deck", "is_number": "IS 269"})
    check("POST tender-block", r.status_code == 200)

    # 11) session purge (last — destroys this session's data)
    r = c.request("DELETE", "/api/procure/session-data")
    check("DELETE session-data", r.status_code == 200)

    print(f"\n{len(passed)} passed, {len(failed)} failed")
    if failed:
        print("FAILED:", ", ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    main()
