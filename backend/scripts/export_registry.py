#!/usr/bin/env python3
"""
Export standards_metadata.pkl → backend/data/standards_registry.json

One-time (rerunnable) migration step. The runtime app never touches the
pickle or pandas — it only reads the generated JSON.

Usage:
    python scripts/export_registry.py [--pkl PATH]

Source: SIH26108 curated dataset (130 standards) with fields:
    IS_number, title, category, scope_description, latest_version,
    amendment, normative_refs, certification_required, combined_text
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_PKL = Path.home() / "OneDrive" / "Desktop" / "standards_metadata.pkl"
OUTPUT = DATA_DIR / "standards_registry.json"

REQUIRED_FIELDS = [
    "IS_number", "title", "category", "scope_description",
    "latest_version", "amendment", "normative_refs",
    "certification_required", "combined_text",
]


def core_number(is_number: str) -> str:
    """'IS 1239 (Part 1):2004' → '1239'."""
    m = re.search(r"IS\s*:?\s*(\d+)", is_number or "")
    return m.group(1) if m else ""


def clean_is_number(is_number: str) -> str:
    """'IS 269:2015' → 'IS 269' (drop edition suffix, keep part info)."""
    s = (is_number or "").strip()
    s = re.sub(r":\s*\d{4}\s*$", "", s)  # trailing :YYYY
    return s.strip()


def split_refs(raw: str) -> list[str]:
    """'IS 3535; IS 4031' → ['IS 3535', 'IS 4031']."""
    if not raw or not str(raw).strip():
        return []
    parts = re.split(r"[;,\n]+", str(raw))
    return [p.strip() for p in parts if p.strip()]


def parse_certification(raw: str) -> dict:
    """'Yes - ISI Mark (mandatory under Cement QCO 2023)' → structured dict."""
    s = str(raw or "").strip()
    mandatory = s.lower().startswith("yes")
    rest = s
    for sep in (" - ", " – ", ": "):
        if sep in rest:
            rest = rest.split(sep, 1)[1]
            break
    scheme, note = rest, ""
    m = re.match(r"(.+?)\s*\((.+)\)\s*$", rest)
    if m:
        scheme, note = m.group(1).strip(), m.group(2).strip()
    if not scheme:
        scheme = "BIS certification" if mandatory else "Not applicable"
    return {"mandatory": mandatory, "scheme": scheme, "note": note}


def main() -> int:
    parser = argparse.ArgumentParser(description="Export standards registry JSON")
    parser.add_argument("--pkl", type=str, default=str(DEFAULT_PKL))
    args = parser.parse_args()

    pkl_path = Path(args.pkl)
    if not pkl_path.exists():
        print(f"ERROR: Pickle not found: {pkl_path}")
        print("   Pass --pkl /path/to/standards_metadata.pkl")
        return 1

    try:
        import pandas as pd  # dev-only dependency
    except ImportError:
        print("ERROR: pandas is required for this one-time export: pip install pandas")
        return 1

    # Restrict unpickling to pandas/numpy/builtins globals.
    import pickle

    allowed = ("pandas", "numpy", "builtins")

    class Safe(pickle.Unpickler):
        def find_class(self, module, name):
            if module.split(".")[0] in allowed:
                mod = __import__(module, fromlist=[name])
                return getattr(mod, name)
            raise pickle.UnpicklingError(f"forbidden global {module}.{name}")

    print(f"Loading {pkl_path.name} ...")
    df = Safe(open(pkl_path, "rb")).load()
    if not isinstance(df, pd.DataFrame):
        print(f"ERROR: Expected a pandas DataFrame, got {type(df).__name__}")
        return 1

    missing = [c for c in REQUIRED_FIELDS if c not in df.columns]
    if missing:
        print(f"ERROR: Missing expected columns: {missing}")
        return 1

    standards: list[dict] = []
    for _, row in df.iterrows():
        cert = parse_certification(row.get("certification_required", ""))
        standards.append({
            "is_number": str(row.get("IS_number", "")).strip(),
            "is_number_clean": clean_is_number(str(row.get("IS_number", ""))),
            "core_number": core_number(str(row.get("IS_number", ""))),
            "title": str(row.get("title", "")).strip(),
            "category": str(row.get("category", "")).strip(),
            "scope_description": str(row.get("scope_description", "")).strip(),
            "latest_version": str(row.get("latest_version", "")).strip(),
            "amendment": str(row.get("amendment", "")).strip(),
            "normative_refs": split_refs(row.get("normative_refs", "")),
            "certification": cert,
            "combined_text": str(row.get("combined_text", "")).strip(),
        })

    bad = [s["is_number"] for s in standards if not s["core_number"]]
    if bad:
        print(f"WARNING: Rows without a parseable IS number (kept anyway): {bad}")

    output = {
        "meta": {
            "source": "SIH26108 curated standards dataset (standards_metadata.pkl)",
            "exported_on": date.today().isoformat(),
            "count": len(standards),
            "disclaimer": "Hand-curated metadata — verify against bis.gov.in before citing in real tenders.",
        },
        "standards": standards,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    cats = {}
    for s in standards:
        cats[s["category"]] = cats.get(s["category"], 0) + 1
    print(f"Wrote {len(standards)} standards -> {OUTPUT}")
    print(f"   Categories: {json.dumps(cats, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
