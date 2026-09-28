# agent.md — Operating Manual for AI Agents in This Repo

You are an AI agent (Codebuff/Claude/Cursor/etc.) working in the **Standard Setu** codebase (SIH26108). This file tells you how to work here without breaking things. Read `context.md` first for what the project is.

---

## Prime directives

1. **Do not rewrite.** This is a working product. Extend it; never rebuild the recommendation engine, replace working components, or swap architectures for taste.
2. **Never weaken the honesty guarantees** (`context.md` §5). Concretely, never:
   - invent clause/page numbers, registry values, or licence statuses;
   - relabel Match Score as "confidence %" or fabricate score factors;
   - fake verification success, scraped data, or risk levels from anything but deterministic findings;
   - fill comparison cells with unsupported values.
3. **No new heavy dependencies** without checking `context.md` §4 first. The stack is intentionally small: FastAPI + JSON stores + pdfplumber; Next.js 14 + Tailwind + framer-motion. OCR (pytesseract/PyMuPDF) stays optional-and-detected.
4. **Match the theme.** All UI uses `frontend/components/procure/theme.ts` (ink `#1c2438`, paper `#f1efe6`, paperDeep `#e7e3d4`, brass `#a9722f`, seal `#8a3324`, line `#c9c3ab`, good `#3f6b4e`, sans Helvetica, serif Georgia). New components import from `./theme`, not hard-coded hexes.
5. **Tests are part of done.** Backend changes need a test in `backend/tests/test_features.py` (currently 25 passing). Frontend changes need `npx tsc --noEmit` clean.

---

## Environment quirks (this machine — hit them once, remember forever)

| Quirk | Rule |
|-------|------|
| Windows + Git Bash | Use POSIX syntax (`mv`, `rm -rf`, heredocs). `/tmp` is invisible to Windows Python — use project-relative temp files. |
| Python 3.14 at `C:\Users\devgo\AppData\Local\Python\pythoncore-3.14-64\python.exe` | sentence-transformers **cannot** install. Do not try. Keyword-only mode is correct behavior. |
| cp1252 console | **No emoji or unicode in Python print statements** — UnicodeEncodeError. ASCII only. |
| `write_file` tool | Requires all three params: `path`, `instructions`, `content`. |
| No git repo | Deletions are permanent. Nothing is recoverable. Be careful with `rm`. |
| Background processes | `process_type: BACKGROUND` errors. Use the detached subshell: `(python -m uvicorn app.main:app --port 8000 > backend.log 2>&1 &)`. |
| Port 3000 occupied | Frontend dev server picks a random port (has been 55262 → 65437 → 61605 → 56938). Always read the actual port from `frontend.log` (`grep -Eo "localhost:[0-9]+" frontend.log`). |
| `next build` vs running dev server | **Never run `next build` while the dev server is up** — it corrupts `.next` (EINVAL readlink under OneDrive) and 404s the dev server. Order: kill dev → build → `rm -rf frontend/.next` → restart dev. |
| OneDrive path | Project root: `C:\Users\devgo\OneDrive\Desktop\SIH\bis-sahayak-main\`. OneDrive locks files — expect occasional EBUSY; retry after a kill. |
| Em-dashes in curl | `curl -d` with unicode dashes → "error parsing the body". ASCII hyphens in JSON payloads. |
| rpgrep tool failures | If `code_search` errors with ENOENT (vendored rg missing), fall back to `grep -n` via terminal. |

---

## Verification protocol (always, in this order)

1. **Backend changes:**
   ```bash
   cd backend && python -m pytest          # must stay green (25 tests)
   # restart uvicorn (kill the :8000 PID first), then curl the touched endpoints
   ```
2. **Frontend changes:**
   ```bash
   cd frontend && npx tsc --noEmit         # must be clean
   ```
   Only build with the dev server stopped (see quirk table).
3. **Live check:** dev frontend via the preview browser; backend via curl. Screenshots may miss fast UI states — verify via DOM (`document.body.innerText`) when a visual state is ephemeral.
4. **Honesty check:** if your change touches scoring, evidence, verification, comparison, versions, or risk — re-read the relevant guarantee in `context.md` §5 and make sure a test pins the honest behavior.

---

## Conventions

- **Backend:** services in `app/services/`, one concern per file; pydantic schemas in `app/models/schemas.py` (watch definition order — models used as fields must be defined before their users); router endpoints in `app/routers/procurement.py` with `store.record_event(...)` for anything auditable. JSON stores go through `store.py` (thread lock, atomic write). Timestamps: `datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")`.
- **Frontend:** typed API client functions in `frontend/lib/api.ts` (always via `apiFetch` so the session header rides along); components in `components/procure/`; "use client" directive; lucide-react icons; framer-motion for animation. Keep components small and themed.
- **Session/privacy:** any new endpoint that records user activity must accept `X-Session-Id`, pass it to `record_event(session_id=...)`, and be covered by the purge path. New state files belong in `backend/data/` and must be monkeypatchable in tests (see `_tmp_state` fixture in `conftest.py`).
- **Test pattern:** FastAPI TestClient + stubbed `sentence_transformers` module (hashing embedder, dim 256) injected via `sys.modules` **before** importing `app.main`; state files redirected to `tmp_path`. Copy the existing fixtures — don't invent a new harness.

---

## Out of scope (do not do without explicit user request)

- Email/SMS/push notification infrastructure (watchlist alerts are in-app only, by design).
- Aggressive scraping of BIS/manakonline (one polite request per verification, cached).
- Any real BIS API (none exists; do not invent one).
- Rewriting the registry data format or the pkl→JSON pipeline.
- Adding a database, auth system, or microservices.
- Replacing the flip-card deck, circuit loader, or agent chat with conventional UI "because it's simpler" — they are deliberate product decisions.

---

## If you must regenerate data artifacts

- Evidence index (after PDFs change): `cd backend && python scripts/build_evidence_index.py` — then restart uvicorn (the index is cached in-process).
- Registry JSON (rare): `python scripts/export_registry.py --pkl ../reference/standards_metadata.pkl`.
- Smoke script for all new endpoints: `python scripts/smoke_new_features.py` (uses the stub embedder internally).

---

## Current state snapshot (update this section when it changes)

- Backend: uvicorn on **:8000**, all 16 endpoints live, 25 tests green.
- Frontend: dev server on a random port (read `frontend.log`), agent chat is the default Recommend view, T&C gate active.
- Data: 130-standards registry; 38-doc evidence index (watermark-sanitized); empty history/watchlist state files are fine.
- Known machine gaps: no sentence-transformers (keyword-only matching), no OCR stack (graceful unavailability).
