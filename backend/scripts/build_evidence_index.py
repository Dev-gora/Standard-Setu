"""Build the offline clause/page evidence index from reference/bis_pdfs.

Run once (or whenever the corpus changes):
    python scripts/build_evidence_index.py

- Walks <project>/reference/bis_pdfs for *.pdf
- For each PDF: records the file name, per-page sample text (first 500 chars)
  and clause-style headings found in the text (regex, no ML).
- Writes backend/data/evidence_index.json keyed by the IS core number.

Uses pdfplumber only (already a dependency). Dev-only script: not imported by
the app at runtime; the app reads the JSON produced here.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
DEFAULT_CORPUS = BACKEND_DIR.parent / "reference" / "bis_pdfs"

# Clause-style heading: "4.2 Requirements", "5 STRUCTURE", "Annex B", "9.3.1"
_CLAUSE_RE = re.compile(
    r"^\s*(?P<num>\d{1,2}(?:\.\d{1,2}){0,2})\s+(?P<title>[A-Z][A-Za-z \-,&/()]{3,60})\s*$",
    re.MULTILINE,
)
_ANNEX_RE = re.compile(
    r"^\s*(?P<num>Annex\s+[A-Z])\s*[\-:\u2014]?\s*(?P<title>[A-Z][A-Za-z \-,&/()]{3,60})\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Distributor watermarks (BSB Edge samples embed recipient emails, IPs and
# 'Free Standard provided by...' headers). These lines must never surface as
# evidence text.
_WATERMARK_HINTS = ("@", "bsb edge", "free standard", "licensed copy", "not for resale")
_IP_LINE_RE = re.compile(r"^\s*\d{1,3}(?:\.\d{1,3}){3}\b")
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def _sanitize(text: str) -> str:
    """Drop watermark/licence-header lines from extracted PDF text."""
    out_lines = []
    for line in (text or "").splitlines():
        low = line.lower()
        if any(h in low for h in _WATERMARK_HINTS):
            continue
        if _IP_LINE_RE.match(line) and ("indian standard" in low or _YEAR_RE.search(line)):
            continue
        if re.match(r"^\s*\d{1,3}(?:\.\d{1,3}){3}\s*[.,;]?\s*$", line):
            continue
        out_lines.append(line)
    return "\n".join(out_lines)


def parse_pdf(path: Path) -> dict:
    """Extract pages + clause headings from one PDF. Returns index document."""
    import pdfplumber

    doc: dict = {"document": path.name, "pages": [], "clauses": []}
    try:
        with pdfplumber.open(path) as pdf:
            for pno, page in enumerate(pdf.pages[:120], start=1):  # cap: BIS stds are short
                try:
                    text = page.extract_text() or ""
                except Exception:
                    text = ""
                text = _sanitize(text)
                if not text.strip():
                    continue
                doc["pages"].append({"page": pno, "sample": text[:500]})
                for m in _CLAUSE_RE.finditer(text):
                    doc["clauses"].append({
                        "clause": m.group("num"),
                        "heading": f"{m.group('num')} {m.group('title')}".strip(),
                        "page": pno,
                    })
                for m in _ANNEX_RE.finditer(text):
                    doc["clauses"].append({
                        "clause": m.group("num").title(),
                        "heading": f"{m.group('num').title()} - {m.group('title')}".strip(),
                        "page": pno,
                    })
    except Exception as exc:
        doc["error"] = f"{type(exc).__name__}: {exc}"
    # Keep only the first occurrence of each clause number (title page repeats etc.)
    seen: set[str] = set()
    doc["clauses"] = [
        c for c in doc["clauses"]
        if not (c["clause"] in seen or seen.add(c["clause"]))
    ]
    return doc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS,
                    help="Directory of BIS PDFs (default: reference/bis_pdfs)")
    ap.add_argument("--out", type=Path, default=DATA_DIR / "evidence_index.json")
    args = ap.parse_args()

    if not args.corpus.is_dir():
        print(f"Corpus directory not found: {args.corpus}")
        return 1

    by_core: dict[str, list[tuple[Path, dict]]] = {}
    pdfs = sorted(args.corpus.glob("*.pdf"))
    print(f"Indexing {len(pdfs)} PDFs from {args.corpus} ...")
    for pdf_path in pdfs:
        # Derive the IS core number from the file name (e.g. '1786.pdf',
        # '2062_2011_reff2021 (1).pdf', '1554_1_1988_reff2020.pdf').
        m = re.match(r"(\d{2,6})", pdf_path.name)
        if not m:
            print(f"  skip (no IS number in name): {pdf_path.name}")
            continue
        core = m.group(1)
        doc = parse_pdf(pdf_path)
        doc["core_number"] = core
        by_core.setdefault(core, []).append((pdf_path, doc))
        n_clauses = len(doc["clauses"])
        n_pages = len(doc["pages"])
        status = doc.get("error", "ok")
        print(f"  {pdf_path.name}: {n_pages} pages, {n_clauses} clauses [{status}]")

    # Canonical doc per core (prefer the clean filename) + an editions map so
    # P1-9 version comparison can compare distinct edition files when present.
    def _pref(item: tuple[Path, dict]) -> tuple[int, str]:
        name = item[0].name
        return (1 if re.search(r"\(\d\)", name) else 0, name)

    documents: dict[str, dict] = {}
    for core, items in by_core.items():
        items.sort(key=_pref)
        canonical_name, canonical_doc = items[0][0].name, items[0][1]
        editions: dict[str, dict] = {}
        for path, doc in items:
            stem = path.stem
            ym = re.search(r"(19|20)\d{2}", stem)
            key = ym.group(0) if ym else stem
            editions.setdefault(key, {"document": path.name, "pages": doc["pages"], "clauses": doc["clauses"]})
        canonical_doc["document"] = canonical_name
        canonical_doc["edition_keys"] = sorted(editions.keys())
        canonical_doc["editions"] = editions
        documents[core] = canonical_doc

    out = {
        "built_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "corpus": str(args.corpus),
        "document_count": len(documents),
        "documents": documents,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {args.out} ({len(documents)} documents).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
