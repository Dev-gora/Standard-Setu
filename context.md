# Standard Setu — Project Context

> The single source of truth for what this project is, why it exists, how it works, and where its limits are. Read this before changing core behaviour.

---

## 1. The Problem (SIH26108)

Procurement officials drafting Indian government tender specifications must cite the correct Indian Standards (IS). With thousands of standards, overlapping scopes, frequent revisions, amendments and normative cross-references, real tender documents routinely cite the **wrong standard, an outdated edition, or omit the mandatory BIS certification condition**. There is no practical tool that answers, for a given purchase description:

- **WHAT** standard applies?
- **WHY** was it selected?
- **EVIDENCE** — which clause/page of the source document supports it?
- **COMPLIANCE** — is BIS certification/licensing mandatory?
- **RISK** — what is wrong with the tender specification I already have?
- **ACTION** — what exact wording should I put in the tender?

**Problem statement ID:** SIH26108 · Ministry of Consumer Affairs, Food & Public Distribution · Department of Consumer Affairs · Theme: Smart Automation.
**Idea submission deadline:** 30 Sep 2026.

---

## 2. The Solution

Standard Setu is an explainable, auditable procurement intelligence engine organized around four stages:

```
DISCOVER → VERIFY → ANALYZE → MONITOR
```

| Stage | What it does | Where it lives |
|-------|--------------|----------------|
| DISCOVER | Natural-language recommendation of Indian Standards, with clarifying questions for ambiguous queries | `standards_registry.py`, `AgentSearch.tsx` |
| VERIFY | Supplier BIS licence verification + structured source evidence | `verify.py`, `evidence.py` |
| ANALYZE | Bulk tender checking, risk heatmap, comparison matrices | `tender_check.py`, `risk.py`, `compare.py` |
| MONITOR | Watchlist change detection, in-app notifications, audit history | `store.py` |

It is **not** a chatbot wrapper. Every feature is grounded in a curated registry and deterministic logic; the optional LLM only polishes wording.

---

## 3. Feature Inventory (all implemented & tested)

### P0
1. **Explainable Match Score** — 0–100 score + expandable factor breakdown (keyword overlap, category/scope/title token fit, certification relevance, semantic similarity when embeddings are available). Always labelled "Match Score", never "confidence %".
2. **Clause/page source citations** — offline index built from actual BIS PDFs (`reference/bis_pdfs`, 38 documents indexed). Structured `EvidenceRef` objects; honest fallbacks: "Source available — clause/page not indexed" / "Source document not indexed". **Never invented.**
3. **BIS licence verification** — CM/L-XXXXXXXXXX format validation → single polite probe of the official Manakonline portal → cached result with "Last verified" timestamp. States: `valid | invalid | expired | not_found | unable_to_verify | source_unavailable`. No fake API, no scraping.
4. **Audit / search history** — every recommendation, tender check, verification and watch action recorded with a full payload; UI shows a 9-step audit timeline answering "why was this recommended?".
5. **Watchlist + change detection** — registry lifecycle snapshots (edition/amendment/title) diffed deterministically; one notification per real change; in-app notification center.

### P1
6. **Standard comparison matrix** — 2–5 standards side-by-side from registry data only; empty cells stay empty; match scores computed by the same engine via raw-query rescoring.
7. **Specification risk heatmap** — deterministic mapping from tender-check findings (unknown/outdated/missing-certification/unparseable) to per-dimension levels with suggested actions.
8. **OCR fallback** — scanned PDFs (thin text layer) fall back to pytesseract when installed; graceful "OCR unavailable on server" otherwise; text parser remains primary.
9. **Version comparison** — only between edition files actually indexed in the corpus; otherwise "Comparison unavailable — source document not indexed". Change classes: added/removed/modified/unchanged/unable_to_determine.
10. **Unified recommendation report** — WHAT/WHY/EVIDENCE/COMPLIANCE/RISK/ACTION on one printable page (`window.print()` → Save as PDF).

### Experience layer
- **Claude-style agent search** (default Recommend view): chat thread, collapsible tool-step blocks ("Searched the registry (5 steps)"), scroll-driven flip-card answer deck instead of paragraphs, in-chat clarify questions, composer **locked until the agent finishes replying**.
- **Circuit-board loading animation** (`CircuitBoard.tsx` + `CircuitLoader.tsx`) themed to the paper/ink/brass palette, wired into recommend and bulk-check loading states.
- **Terms & Conditions gate** on first visit + **enforced privacy model** (see §7).

---

## 4. Architecture

```
Next.js 14 frontend ──HTTP──► FastAPI backend ──► standards_registry.json (130 IS)
   /procure (+ /)                :8000                evidence_index.json (38 docs)
                                                      app_state.json (history/watchlist/notifications)
                                                      verify_cache.json (licence cache)
```

- **Recommendation pipeline:** `search_registry()` — hybrid `0.6 × cosine(embedding) + 0.4 × keyword overlap`; threshold 0.12. Every hit carries raw `_semantic`, `_keyword`, `_score` which `scoring.py` consumes for the Match Score. When sentence-transformers is unavailable the engine degrades to **keyword-only mode** (`EMBEDDINGS_AVAILABLE=False`, weak_threshold 0.18) — by design, not a bug.
- **LLM layer (`llm.py`):** optional, 4 providers (ollama/gemini/openai/anthropic) via `LLM_PROVIDER`. Used only for tender-block polish and clarify generation; every call has a deterministic fallback. Currently unconfigured → fully rule-based operation.
- **No database.** JSON file stores with atomic writes + thread locks. Sessions are anonymous UUIDs from `sessionStorage` sent as `X-Session-Id`.
- **Uploads are memory-only** — never written to disk.

### Key files
| File | Role |
|------|------|
| `backend/app/routers/procurement.py` | All 16 endpoints |
| `backend/app/services/standards_registry.py` | Registry, hybrid search, allied standards, clarify |
| `backend/app/services/scoring.py` | P0-1 Match Score |
| `backend/app/services/evidence.py` | P0-2 citations from the offline index |
| `backend/app/services/verify.py` | P0-3 licence verification + cache |
| `backend/app/services/store.py` | P0-4/5 history, watchlist, notifications, session purge |
| `backend/app/services/{compare,risk,ocr,versions,report}.py` | P1 features |
| `backend/scripts/build_evidence_index.py` | Offline PDF → clause/page index (dev-only) |
| `frontend/components/procure/*` | UI: AgentSearch, AnswerDeck, AgentSteps, CircuitLoader, MatchScore, EvidenceList, VerifyPanel, ComparePanel, WatchlistPanel, HistoryPanel, RiskPanel, ReportView, TermsModal, BulkPanel, StandardModal |
| `backend/tests/test_features.py` | 25 pytest cases |

---

## 5. Honesty Guarantees (enforced in code + tests)

These are product-level invariants. Any change that weakens them is a regression:

1. The score is called **Match Score**; factors expose only signals the pipeline actually computes; qualitative High/Medium/Low confidence is separate.
2. Clause/page numbers come **only** from the built index over the real PDF corpus; anything else renders an explicit "not indexed" state. The index builder sanitizes distributor watermarks (BSB Edge headers, recipient emails, IPs) so they never surface as evidence.
3. Licence verification never claims "valid" without a real portal response; every result carries **Last verified** and cache state.
4. Comparison/version features refuse to fabricate cells or diffs.
5. Risk levels derive strictly from deterministic findings — no LLM judgement.
6. The T&C promise ("data deleted when you close/refresh") is **enforced**: `DELETE /api/procure/session-data` fires on `pagehide` (keepalive), plus a 12h stale-session purge as safety net. Watchlist entries persist only because the user explicitly opted in — the T&C says so.

---

## 6. Demo Script (verified live)

1. Type *"Reinforcement bars for concrete in a bridge deck"* → agent steps animate → flip-card deck with IS 1786 (Match 83, clause 4.1.3 / p.4 citation).
2. *"Steel for a warehouse structure"* → in-chat clarify → pick "Reinforcement bars inside concrete" → IS 1786.
3. Open **Why this score?** → factor bars traceable to real signals.
4. **Verify** tab → CM/L-8700123456 → honest `unable_to_verify` + Last verified timestamp.
5. **Compare** tab → IS 1786 vs IS 2062 vs IS 269 → registry matrix.
6. **Monitor** tab → watch IS 269, open audit timeline of any recommendation.
7. **Bulk check** → upload real tender PDFs (up to 500) → risk heatmap + OCR status.
8. **Unified report** → print-ready WHAT/WHY/EVIDENCE/COMPLIANCE/RISK/ACTION.

---

## 7. Data & Privacy Model

- **Registry:** 130 standards, 12 categories (Cement & Concrete 22, Steel & Metal 21, Bricks & Clay 13, Timber & Wood 12, Water Supply & Pipes 10, Paints 10, Plastics 9, Electrical 8, Safety 7, Aggregates 7, Furniture 6, Adhesives 5). Curated, representative — not the full BIS catalogue.
- **Evidence index:** 38 documents from `reference/bis_pdfs`, keyed by core IS number, with per-page text samples, clause headings (regex-detected), and per-edition maps for version comparison.
- **Privacy:** anonymous session IDs (no cookies, no PII); session-scoped history; explicit purge endpoint + unload beacon + 12h TTL; uploads memory-only; the only outbound call is the polite BIS portal probe during verification.

---

## 8. Known Limitations (be upfront, incl. with judges)

- **Python 3.14 machine:** sentence-transformers not installable → matching runs keyword-only. All semantic-mode UI is built and activates automatically if the model becomes available. Rebalancing weights or faking semantic signals is prohibited.
- **OCR stack not installed** on this machine → bulk checks report "OCR unavailable" honestly. Feature code is complete and tested for the graceful path.
- **Version comparison** needs two edition files per standard in the corpus; most standards have one → honest "not indexed" answer is the common case today.
- **BIS verification** cannot return full structured status fields (the official portal is form-based; scraping is out of scope by policy) → `unable_to_verify` with a portal link is the honest terminal state.
- Registry is curated (130), evidence corpus is 38 documents — coverage is representative, not exhaustive.

---

## 9. What "done" means here

A feature is done when: backend logic + tests (25 passing), typed API client, themed UI, live curl/browser verification, README/context updated, and **no honesty guarantee weakened**.
