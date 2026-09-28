"""Reference-data audit (re-runnable, read-only).

Checks, without modifying anything:
  1. reference/bis_pdfs/  — files exist, byte-identical duplicate groups
  2. backend/data/evidence_index.json — entries with/without source PDFs
  3. backend/data/standards_registry.json — count, missing titles
  4. reference/data/product_standards_map.csv — columns/rows vs registry
     (standards only in CSV / only in registry, duplicate mappings)

Usage: python scripts/audit_reference_data.py [repo_root]
Default root: the repo two levels up (backend/scripts -> repo root).
"""
import csv
import hashlib
import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", ".."))
PDF_DIR = os.path.join(ROOT, "reference", "bis_pdfs")
EV_PATH = os.path.join(ROOT, "backend", "data", "evidence_index.json")
REG_PATH = os.path.join(ROOT, "backend", "data", "standards_registry.json")
CSV_PATH = os.path.join(ROOT, "reference", "data", "product_standards_map.csv")


# ---- helpers -----------------------------------------------------------

def norm_core(s: str) -> str:
    """'IS 269', '269', 'IS 269:2015', 'IS 302 Part 2' -> core number."""
    digits = re.findall(r"\d+", str(s or ""))
    return digits[0] if digits else ""


def registry_records() -> list[dict]:
    data = json.load(open(REG_PATH, encoding="utf-8"))
    if isinstance(data, dict) and "standards" in data:
        return data["standards"]
    if isinstance(data, list):
        return data
    return []


def dupes(dirpath: str) -> dict[tuple, list[str]]:
    """Byte-identical duplicate groups by (size, sha256)."""
    groups = defaultdict(list)
    for fn in os.listdir(dirpath):
        p = os.path.join(dirpath, fn)
        if not os.path.isfile(p):
            continue
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        groups[(os.path.getsize(p), h.hexdigest())].append(fn)
    return {k: v for k, v in groups.items() if len(v) > 1}


# ---- 1. PDFs -----------------------------------------------------------

pdfs = sorted(os.listdir(PDF_DIR)) if os.path.isdir(PDF_DIR) else []
print(f"=== 1. reference/bis_pdfs: {len(pdfs)} files ===")
dups = dupes(PDF_DIR)
if dups:
    print(f"byte-identical duplicate groups: {len(dups)}")
    for k, names in dups.items():
        print(f"  [{k[0]:>9} bytes] " + " | ".join(names))
else:
    print("no byte-identical duplicates")

# ---- 2. evidence vs PDFs ------------------------------------------------

ev = json.load(open(EV_PATH, encoding="utf-8"))
docs = ev.get("documents", {})

print(f"\n=== 2. evidence_index: {len(docs)} documents vs {len(pdfs)} PDFs ===")
missing_pdf = []
for core, d in docs.items():
    fname = d.get("document", "")
    if fname and os.path.exists(os.path.join(PDF_DIR, fname)):
        continue
    stem = os.path.splitext(fname or "")[0].lower()
    if stem and stem in {os.path.splitext(f)[0].lower() for f in pdfs}:
        continue
    if core in {norm_core(f) for f in pdfs}:
        continue
    missing_pdf.append((core, fname))

if missing_pdf:
    print(f"evidence entries with NO matching PDF: {len(missing_pdf)}")
    for core, fname in missing_pdf:
        print(f"  {core} -> {fname}")
else:
    exact = sum(1 for d in docs.values() if d.get("document") in pdfs)
    print(f"all {len(docs)} evidence documents resolve to PDFs on disk ({exact} exact filename matches)")

ev_cores = {str(c) for c in docs}
pdfs_without_ev = [f for f in pdfs if norm_core(f) not in ev_cores]
if pdfs_without_ev:
    print(f"PDFs with no evidence entry (by core number): {len(pdfs_without_ev)}")
    for f in pdfs_without_ev:
        print("  ", f)

# ---- 3. registry ---------------------------------------------------------

recs = registry_records()
no_title = [r for r in recs if not (r.get("title") or "").strip()]
print(f"\n=== 3. standards_registry: {len(recs)} standards ===")
print(f"records with empty/missing title: {len(no_title)}")
for r in no_title[:10]:
    print("  ", r.get("is_number_clean") or r.get("core_number"), "| title:", repr((r.get("title") or "")[:50]))

# ---- 4. CSV vs registry --------------------------------------------------

if not os.path.exists(CSV_PATH):
    print(f"\n=== 4. CSV: NOT FOUND at {CSV_PATH} ===")
    csv_rows = []
else:
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        csv_rows = list(csv.DictReader(f))
    cols = list(csv_rows[0].keys()) if csv_rows else []
    print(f"\n=== 4. CSV: {len(csv_rows)} rows, columns: {cols} ===")

reg_by_core = defaultdict(list)
for r in recs:
    reg_by_core[norm_core(r.get("is_number_clean") or r.get("core_number"))].append(r)

csv_by_core = defaultdict(list)
for row in csv_rows:
    core = norm_core(row.get("is_number", ""))
    if core:
        csv_by_core[core].append(row)

only_csv = sorted(c for c in csv_by_core if c and c not in reg_by_core)
only_reg = sorted(c for c in reg_by_core if c and c not in csv_by_core)
print(f"standards in CSV but NOT in registry ({len(only_csv)}): {only_csv}")
print(f"standards in registry but NOT in CSV ({len(only_reg)}): {only_reg}")
print(f"CSV duplicate mappings (same core number twice): {sum(1 for v in csv_by_core.values() if len(v) > 1)}")
for core, rows_ in csv_by_core.items():
    if len(rows_) > 1:
        print(f"  {core}: {[r_.get('is_number') for r_ in rows_]}")

# Naming mismatches: same core, clearly different title wording
print("\nnaming/title spot-check for shared cores (first 12):")
shared = [c for c in sorted(csv_by_core) if c in reg_by_core][:12]
for c in shared:
    csv_title = (csv_by_core[c][0].get("title") or "")[:48]
    reg_title = (reg_by_core[c][0].get("title") or "")[:48]
    flag = "" if csv_title.lower() in reg_title.lower() or reg_title.lower() in csv_title.lower() else "  <-- wording differs"
    print(f"  {c:>6}  CSV: {csv_title!r} | REG: {reg_title!r}{flag}")
