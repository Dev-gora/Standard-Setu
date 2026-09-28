# Standard Setu 🏛️

**AI-Powered Recommendation Engine for Identifying Applicable Indian Standards for Procurement Specifications**

> SIH26108 — Ministry of Consumer Affairs, Food & Public Distribution · Department of Consumer Affairs · Theme: Smart Automation

---

## What is Standard Setu?

Procurement officials drafting tender specifications must reference the correct Indian Standards (IS) — but with thousands of standards, overlapping scopes, frequent revisions, and normative cross-references, tender documents often cite the wrong, outdated, or incomplete standards.

Standard Setu is an AI-powered recommendation engine that:

| Feature | Description |
|---------|-------------|
| 🎯 **Semantic Standard Recommendation** | Describe the product ("PVC cable rated 1.1kV") — get the IS to cite, matched by meaning, not keywords |
| 🕐 **Edition + Amendment Display** | Every recommendation shows the registry edition and amendment/reaffirmation status, each labeled with its provenance (LOCAL_REGISTRY vs GOVERNMENT_VERIFIED) — see the verification report below |
| 🧩 **Allied Standards by Purpose** | Normative references classified as test methods, terminology, design codes, components… |
| 🛡️ **Mandatory Certification Flags (provenance-aware)** | Certification requirements carry their backing: QCO-backed claims cite the notification (e.g. Steel QCO 2020/2024 for IS 1786); claims without a located government source are marked MANUAL_REVIEW_REQUIRED, never presented as established law |
| 📝 **Copy-Paste Tender Blocks** | Draft specification wording grounded in the registry, ready to paste into a tender |
| ❓ **Clarifying Questions** | Ambiguous queries ("steel for a warehouse") trigger smart disambiguation instead of guesses |
| 📑 **Bulk Tender Check** | Upload up to 50 tender PDFs — flags unknown IS codes, outdated editions, missing certification language |
| 📊 **Match Score (explainable)** | Every recommendation shows a traceable 0-100 Match Score with a "Why this score?" factor breakdown |
| 📚 **Clause/Page Citations** | Structured evidence from the indexed BIS PDF corpus — or an honest "clause/page not indexed" |
| 🏅 **Supplier Licence Verification** | Check a BIS licence (CM/L-…) against the official portal — cached, timestamped, honest failure states |
| 🗂️ **Audit History** | Every recommendation, tender check and verification is recorded with a full audit timeline |
| 🔔 **Watchlist + Change Alerts** | Watch standards; deterministic change detection (edition/amendment/title) with in-app notifications |
| ⚖️ **Standard Comparison** | Compare 2-5 standards side-by-side from real registry data |
| 🔥 **Risk Heatmap** | Tender findings aggregated into per-dimension risk levels with suggested actions |
| 🔍 **OCR Fallback** | Scanned tender PDFs go through OCR when available (graceful "OCR unavailable" otherwise) |
| 📄 **Unified Report** | One printable recommendation report: WHAT / WHY / EVIDENCE / COMPLIANCE / RISK / ACTION |
| 🤖 **Agent Search (Claude-style)** | Chat with the engine: live tool-step blocks, in-chat clarifying questions, and a scroll-driven flip-card answer deck — the input stays locked until the agent finishes replying |
| ⚡ **Circuit Loading Screen** | The DISCOVER→VERIFY→ANALYZE→MONITOR pipeline drawn as a live circuit-board animation while you wait |
| 🔒 **Privacy by Design** | First-visit Terms & Conditions gate; anonymous session IDs; everything you upload or ask is deleted when you close/refresh (enforced, not just promised) |
| 📄 **Document Links** | Each standard links to the public Indian Standards mirror on the Internet Archive |

---

## Architecture

```
┌─────────────┐     HTTP      ┌───────────────────┐
│   Next.js   │ ───────────── │     FastAPI        │
│  Frontend   │               │    Backend         │
└─────────────┘               └─────────┬─────────┘
                                        │
                    ┌───────────────────┼────────────────────┐
                    │                   │                    │
              ┌─────▼──────┐    ┌──────▼───────┐    ┌──────▼───────┐
              │  Standards │    │   LLM API    │    │ sentence-    │
              │  Registry  │    │ (optional:   │    │ transformers │
              │ (130 IS,   │    │  ollama/     │    │ (Embeddings) │
              │  JSON)     │    │  gemini/…)   │    │              │
              └────────────┘    └──────────────┘    └──────────────┘
                                        │
                              ┌─────────▼──────────┐
                              │ pdfplumber tender   │
                              │ parsing (bulk check)│
                              └────────────────────┘
```

The core engine works **fully offline** — the LLM only adds optional polish (better clarify options, smoother tender wording). Rule-based fallbacks keep every feature functional without it.

---

## Quick Start

### Prerequisites
- Python 3.10+ (3.11 recommended for sentence-transformers)
- Node.js 18+

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The 130-standard registry ships as `backend/data/standards_registry.json` — no setup needed.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) — the procurement engine is the home page.

### Docker (One Command)

```bash
docker-compose up --build
```

### Optional: LLM polish

Set a provider in `backend/.env` (see `.env.example`) — `LLM_PROVIDER=ollama` (free, local), `gemini`, `openai`, or `anthropic`. Without it, the app uses deterministic rule-based flows.

---

## Project Structure

```
standard-setu/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI entrypoint
│   │   ├── config.py             # Environment config
│   │   ├── routers/
│   │   │   └── procurement.py    # All 26108 endpoints
│   │   ├── services/
│   │   │   ├── standards_registry.py  # Registry + semantic search + allied standards
│   │   │   ├── scoring.py             # P0-1 explainable Match Score
│   │   │   ├── evidence.py            # P0-2 clause/page citations (offline index)
│   │   │   ├── verify.py              # P0-3 BIS licence verification + cache
│   │   │   ├── store.py               # P0-4/5 JSON store: history, watchlist, notifications
│   │   │   ├── compare.py             # P1-1 comparison matrix
│   │   │   ├── risk.py                # P1-7 deterministic risk heatmap
│   │   │   ├── ocr.py                 # P1-8 optional OCR fallback
│   │   │   ├── versions.py            # P1-9 edition comparison (indexed sources only)
│   │   │   ├── report.py              # P1-10 unified report assembly
│   │   │   ├── tender_check.py        # Bulk PDF tender checking
│   │   │   ├── embeddings.py          # sentence-transformers service
│   │   │   └── llm.py                 # LLM client (4 providers, optional)
│   │   └── models/
│   │       └── schemas.py        # Pydantic models
│   ├── data/
│   │   ├── standards_registry.json  # 130 standards with versions/amendments/refs/certification
│   │   └── evidence_index.json      # Offline clause/page index built from reference/bis_pdfs
│   ├── tests/
│   │   └── test_features.py       # 24 pytest cases (stub embedder pattern)
│   └── scripts/
│       ├── export_registry.py     # One-time pkl → JSON export (dev only)
│       └── build_evidence_index.py # One-time PDF → clause/page index (dev only)
├── frontend/
│   ├── app/
│   │   ├── page.tsx              # Home = Standard Setu
│   │   └── procure/page.tsx      # Same UI at /procure (Recommend/Verify/Compare/Monitor tabs)
│   ├── components/procure/       # ResultView, MatchScore, EvidenceList, VerifyPanel,
│   │                             # ComparePanel, WatchlistPanel, HistoryPanel, RiskPanel, ReportView…
│   └── lib/api.ts                # Typed API client
├── reference/                    # Source material (not part of the app)
│   ├── standard_setu_poc.jsx     # Original UI prototype
│   ├── standards_metadata.pkl    # Original curated dataset (DataFrame)
│   └── bis_pdfs/                 # ~60 BIS standard PDFs (future full-text features)
├── docker-compose.yml
└── README.md
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/procure/recommend` | Recommend standard(s) for a procurement description (may return a clarify prompt) |
| `POST` | `/api/procure/clarify` | Generate a disambiguation question for a query |
| `POST` | `/api/procure/tender-block` | Draft tender-specification wording for a standard |
| `POST` | `/api/procure/bulk-check` | Bulk-check tender PDFs (up to 50, 10 MB each, PDF only) — now with OCR fallback + risk heatmap |
| `GET`  | `/api/procure/standard/{is_number}` | Registry metadata for one standard |
| `GET`  | `/api/procure/evidence/{is_number}` | Structured clause/page citations (honest when not indexed) |
| `POST` | `/api/procure/verify` | BIS licence verification (format check → portal probe → cache + timestamp) |
| `GET`  | `/api/procure/history` | Audit history (filterable by kind; `/history/{id}` for the full record) |
| `GET`/`POST`/`DELETE` | `/api/procure/watchlist` | Watchlist management (deterministic change detection on GET) |
| `GET`  | `/api/procure/notifications` | In-app change notifications (`/notifications/read` to mark read) |
| `POST` | `/api/procure/compare` | Comparison matrix for 2-5 standards |
| `GET`  | `/api/procure/versions/{is_number}` | Edition-to-edition comparison (only from indexed sources) |
| `POST` | `/api/procure/report` | Unified recommendation report (print-ready) |
| `GET`  | `/api/procure/meta` | Registry stats (categories, count, evidence-index/OCR availability) |
| `GET`  | `/api/procure/health` | Health check + registry size |
| `GET`  | `/health` | Root health check |

### Example

```json
POST /api/procure/recommend
{ "query": "Reinforcement bars for concrete in a bridge deck" }
```

→ `IS 1786` (2008, Third Revision, Amendment 2 2018), mandatory BIS licence check,
allied standards (`IS 456` design code, `IS 1608` tensile test), and a copy-paste tender block.

---

## Data

The registry covers **130 Indian Standards** across 12 procurement-heavy categories:
Cement & Concrete (22), Steel & Metal Products (21), Bricks & Clay (13), Timber & Wood (12),
Water Supply & Pipes (10), Paints & Coatings (10), Plastic Products (9), Electrical & Wiring (8),
Safety Equipment (7), Aggregates & Sand (7), Furniture (6), Adhesives (5).

To regenerate `standards_registry.json` from the source pickle:

```bash
cd backend
pip install pandas
python scripts/export_registry.py --pkl ../reference/standards_metadata.pkl
```

---

## Demo Queries (for presentation)

1. "Reinforcement bars for concrete in a bridge deck" → IS 1786 + Match Score 83/100 + clause 4.1.3 (p.4) citation + Watch button
2. "Steel for a warehouse structure" → clarify: plates/sections vs rebar vs roofing sheets
3. "PVC insulated electrical cable, 1.1kV" → IS 694 with QCO-mandatory ISI mark
4. "Cement for a bridge" → IS 269 with Cement QCO 2023 certification note
5. Bulk mode: upload 2-3 tender PDFs → compliance flags + risk heatmap + minimum standards set
6. Verify tab: CM/L-8700123456 → honest verification state with "Last verified" timestamp
7. Compare tab: IS 1786 vs IS 2062 → side-by-side registry matrix
8. Monitor tab: watch IS 269, open the audit timeline of any recommendation
9. "Unified report" button on any result → printable WHAT/WHY/EVIDENCE/COMPLIANCE/RISK/ACTION report

## Honesty Guarantees (enforced in code + tests)

- The score is labelled **Match Score**, never "confidence %"; factors expose only signals the pipeline actually computes
- Clause/page citations come only from the offline index over `reference/bis_pdfs` (classified `LOCAL_REFERENCE_DOCUMENT` — the corpus is a public mirror of BIS scans, not bis.gov.in itself); anything else renders "clause/page not indexed" — never an invented number
- Licence verification returns explicit states (INVALID_FORMAT, NOT_FOUND, SOURCE_UNAVAILABLE, SOURCE_LOCATED, VERIFIED_ACTIVE/EXPIRED/CANCELLED, scope states) mapped to legacy API statuses — "valid" only from a real portal response; `SOURCE_LOCATED` (licence seen, active status not established) never claims validity; every result carries **Last verified** and states what the check cannot establish
- Certification `mandatory` flags are provenance-stamped: VERIFIED only with a located QCO/notification (e.g. Steel QCO for IS 1786/IS 2062, Cement QCO for IS 269/IS 1489, Cables QCO for IS 694); everything else is UNVERIFIED or MANUAL_REVIEW_REQUIRED — and tender checking only fails documents on QCO-backed requirements
- Change detection diffs registry snapshots deterministically; comparison and version diff features refuse to fabricate cells ("Comparison unavailable — source document not indexed")

### Government-source verification audit (2026-09-27)

A provenance audit checked government-related claims against official BIS/GoI sources (BIS Scheme-1 compulsory-certification list, BIS product manuals). Results:

- `backend/data/government_sources.json` — per-standard audit snapshot (QCO, notification, source URL)
- `backend/data/government_verification_report.json` / `GET /api/procure/verification-report` — totals: 130 standards → 2 VERIFIED, 5 PARTIALLY_VERIFIED, 121 UNVERIFIED, 2 MANUAL_REVIEW_REQUIRED; of 92 mandatory-certification claims, 6 are QCO-backed and 86 flagged MANUAL_REVIEW_REQUIRED; 6 discrepancies logged
- `backend/data/manual_review.json` / `GET /api/procure/manual-review` — the human-verification worklist (standard, field, current value, reason, suggested official source, severity)
- `backend/data/data_corrections.json` — corrections applied during the audit with old values preserved (IS 1489 Part 2 edition 1991→2015; IS 4984 Fourth→Fifth Revision + title updated to BIS's "Polyethylene Pipes for Water Supply")

### Running tests

```bash
cd backend
python -m pytest          # 47 tests — 25 core + 22 verification-audit regression tests
```

### Rebuilding the evidence index (after corpus changes)

```bash
cd backend
python scripts/build_evidence_index.py
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, React 18, Tailwind CSS, lucide-react |
| Backend | Python 3.11, FastAPI, Pydantic |
| LLM (optional) | Ollama / Gemini / OpenAI / Anthropic |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) — free, local |
| Document Processing | pdfplumber |
| Deployment | Docker |

---

## Important Disclaimers

- The registry is a **curated, representative dataset** (130 standards), not the full BIS catalogue
- Always verify critical compliance details at [bis.gov.in](https://bis.gov.in)
- Bulk-check results are decision support — not a legal compliance opinion

---

## Privacy Model

Standard Setu collects no personal information. Activity (queries, uploads, verifications) is scoped to an anonymous per-tab session ID and **automatically deleted when you close or refresh the site** — via an explicit purge endpoint fired on tab unload, plus a 12-hour server-side expiry as a safety net. Uploaded PDFs never touch disk (memory-only processing). The only outbound request the app makes is the single polite licence-verification probe to the official BIS portal. Watchlist entries persist only because you deliberately choose to watch a standard, and can be removed anytime.

A Terms & Conditions gate on first visit states this plainly, and the behavior is enforced in code (see `context.md`, §5 and §7).

## Documentation

| File | Contents |
|------|----------|
| `README.md` | This overview — features, setup, API |
| `context.md` | Deep project context: problem, architecture, honesty guarantees, demo script, limitations |
| `agent.md` | Operating manual for AI coding agents working in this repo |

---

**Built with 🇮🇳 for SIH26108**
