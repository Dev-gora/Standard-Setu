"""Standards Registry service — structured metadata layer for SIH26108.

Loads backend/data/standards_registry.json (exported from the curated
standards_metadata.pkl dataset) and provides:

- get_by_is_number: metadata lookup (handles editions, parts, core numbers)
- search_registry: hybrid semantic + keyword search over the registry
- allied_standards_for: normative references joined back to registry entries
  and classified by purpose (test method / terminology / code of practice / …)
- archive_link: deterministic link to the public Indian Standards mirror

No pandas / pickle at runtime — the JSON is the single source of truth.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
REGISTRY_FILE = DATA_DIR / "standards_registry.json"

PURPOSE_RULES: list[tuple[str, str]] = [
    (r"test|method|physical|chemical|analysis|sampling|tensile|soundness", "How it's tested"),
    (r"terminolog|glossary|vocabular|definition", "Terms used"),
    (r"code of practice|design|installation|laying|construction|workmanship", "Design / installation code"),
    (r"safety|protect|helmet|guard", "Safety requirement"),
    (r"part\s*\d|fitting|component|accessor", "Related component"),
    (r"tolerance|dimension|sizes|mass|weight", "Dimensions & tolerances"),
    (r"packag|labell?ing|marking", "Labelling & marking"),
]
DEFAULT_PURPOSE = "Related standard"


@lru_cache
def _load_registry() -> tuple[dict, ...]:
    if not REGISTRY_FILE.exists():
        return tuple()
    data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    recs = []
    for r in data.get("standards", []):
        # Title fallback: never render a blank/hallucinated title. Standards
        # with an IS number but no usable title display this exact sentinel.
        if not (r.get("title") or "").strip():
            r = dict(r)
            r["title"] = "Title unavailable in registry"
        recs.append(r)
    return tuple(recs)


def registry_size() -> int:
    return len(_load_registry())


def registry_meta() -> dict:
    if not REGISTRY_FILE.exists():
        return {"count": 0}
    return json.loads(REGISTRY_FILE.read_text(encoding="utf-8")).get("meta", {})


def all_standards() -> list[dict]:
    return list(_load_registry())


def get_by_is_number(raw: str) -> dict | None:
    """Resolve a loose IS reference to the best registry record.

    Handles 'IS 1786', 'IS 1786:2008', 'IS 1239 (Part 1)', 'IS 1239 Part 1 : 2004'.
    Strategy: exact clean match → part-aware match → core-number match.
    """
    if not raw:
        return None
    s = re.sub(r"\s+", " ", raw.strip().upper())

    def norm(t: str) -> str:
        return re.sub(r"\s+", " ", t.strip().upper())

    # 1) Exact clean match
    for rec in _load_registry():
        if norm(rec["is_number_clean"]) == s:
            return rec

    # 2) Same core number; prefer records whose part spec matches, then any
    core_m = re.search(r"IS\s*:?\s*(\d+)", s)
    part_m = re.search(r"PART\s*:?\s*(\d+)", s)
    if not core_m:
        return None
    core = core_m.group(1)
    candidates = [r for r in _load_registry() if r["core_number"] == core]
    if not candidates:
        return None
    if part_m:
        part = part_m.group(1)
        with_part = [
            r for r in candidates
            if re.search(rf"PART\s*:?\s*{part}\b", r["is_number_clean"].upper())
        ]
        if with_part:
            return with_part[0]
    without_part = [r for r in candidates if "PART" not in r["is_number_clean"].upper()]
    return (without_part or candidates)[0]


def _classify_purpose(ref_title: str) -> str:
    t = ref_title.lower()
    for pattern, purpose in PURPOSE_RULES:
        if re.search(pattern, t):
            return purpose
    return DEFAULT_PURPOSE


def allied_standards_for(record: dict) -> list[dict]:
    """Join a record's normative_refs back to registry entries.

    Returns entries with a purpose label; refs not in the registry are kept
    with their raw reference so the UI can still show them.
    """
    out: list[dict] = []
    seen: set[str] = set()
    for ref in record.get("normative_refs", []):
        key = re.sub(r"\s+", " ", ref.strip())
        if not key or key.lower() in seen:
            continue
        seen.add(key.lower())
        target = get_by_is_number(ref)
        if target:
            out.append({
                "code": target["is_number_clean"],
                "title": target["title"],
                "category": target["category"],
                "purpose": _classify_purpose(target["title"]),
                "latest_version": target["latest_version"],
                "amendment": target["amendment"],
                "certification": target["certification"],
                "known": True,
            })
        else:
            out.append({
                "code": ref,
                "title": "",
                "category": "",
                "purpose": DEFAULT_PURPOSE,
                "latest_version": "",
                "amendment": "",
                "certification": {"mandatory": False, "scheme": "", "note": ""},
                "known": False,
            })
    return out


EMBEDDINGS_AVAILABLE = True

_EMBED_MATRIX = None  # lazy float32 [N, 384] numpy matrix (precomputed offline)
_EMBED_ORDER = None   # is_number_clean per row of the matrix


def _load_precomputed_embeddings():
    """Load the offline-built embedding matrix (built by scripts/build_embeddings.py).

    Stored as one compact float32 .npy — ~200 KB for the whole registry, versus
    encoding all 130 records (plus loading torch) on the first request.
    Falls back to on-the-fly encoding only if the file is missing or its
    model/row-order no longer matches the registry.
    """
    global _EMBED_MATRIX, _EMBED_ORDER
    if _EMBED_MATRIX is not None:
        return _EMBED_MATRIX, _EMBED_ORDER
    import numpy as np

    npy = DATA_DIR / "standards_embeddings.npy"
    meta = DATA_DIR / "standards_embeddings.meta.json"
    if npy.exists() and meta.exists():
        try:
            info = json.loads(meta.read_text(encoding="utf-8"))
            from app.config import get_settings

            if info.get("model") != get_settings().EMBEDDING_MODEL:
                print("[registry] embedding meta model mismatch - rebuilding in memory")
                return None, None
            matrix = np.load(npy)
            order = info.get("order") or []
            records = all_standards()
            codes = [r["is_number_clean"] for r in records]
            if list(order) != codes or matrix.shape[0] != len(records):
                print("[registry] embedding order mismatch - rebuilding in memory")
                return None, None
            _EMBED_MATRIX = matrix
            _EMBED_ORDER = order
            return _EMBED_MATRIX, _EMBED_ORDER
        except Exception as exc:
            print(f"[registry] precomputed embeddings unusable ({type(exc).__name__}) - rebuilding")
    return None, None


@lru_cache(maxsize=1)
def _get_corpora_and_embeddings() -> tuple[list[dict], list[list[float]] | None]:
    """Embedding lookup for every registry record (in-memory, tiny corpus of 130 docs).

    Preferred: precomputed float32 matrix (see _load_precomputed_embeddings).
    Fallback: encode now via the embedding service (ONNX at runtime, or the
    original sentence-transformers path if ONNX artifacts are missing).
    Degrades gracefully: if no embedding engine is available, matching falls
    back to keyword-only scoring instead of crashing.
    """
    global EMBEDDINGS_AVAILABLE
    records = all_standards()
    try:
        import numpy as np

        matrix, order = _load_precomputed_embeddings()
        if matrix is not None:
            EMBEDDINGS_AVAILABLE = True
            return records, matrix

        from app.services.embeddings import embed_texts

        texts = [f"{r['title']}. {r['scope_description']} Category: {r['category']}. {r['combined_text'][:800]}" for r in records]
        embeddings = np.asarray(embed_texts(texts), dtype="float32")
        EMBEDDINGS_AVAILABLE = True
        return records, embeddings
    except Exception as exc:
        print(f"[registry] embeddings unavailable ({type(exc).__name__}) — using keyword-only matching")
        EMBEDDINGS_AVAILABLE = False
        return records, None


def _keyword_score(query: str, record: dict) -> float:
    q_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
    if not q_tokens:
        return 0.0
    hay = " ".join([
        record["title"], record["category"], record["scope_description"],
        record["is_number"],
    ]).lower()
    h_tokens = set(re.findall(r"[a-z0-9]+", hay))
    if not h_tokens:
        return 0.0
    overlap = q_tokens & h_tokens
    return len(overlap) / len(q_tokens)


def search_registry(
    query: str,
    top_k: int = 5,
    threshold: float = 0.12,
) -> list[dict]:
    """Rank candidates with the shared weighted-factor model (see scoring.py).

    Returns records with `_score` (0-1 hybrid = weighted average of the
    similarity factors, identical to the Match Score shown on cards) plus the
    raw `_semantic` / `_keyword` pipeline signals for the breakdown.
    """
    if not query.strip():
        return []
    records, embeddings = _get_corpora_and_embeddings()
    if not records:
        return []

    import numpy as np

    # Ranking uses the SAME weighted-factor model the Match Score card
    # displays (scoring.FACTOR_WEIGHTS), so a card's total is literally the
    # weighted average of its bars. Imported here (not module-level) because
    # scoring imports this module lazily inside its own helpers.
    from app.services import scoring

    q = None
    if embeddings is not None:
        try:
            from app.services.embeddings import embed_query

            q = np.asarray(embed_query(query), dtype="float32")
        except Exception:
            q = None

    results: list[dict] = []
    for i, rec in enumerate(records):
        keyword_score = _keyword_score(query, rec)
        semantic_score: float | None = None
        if q is not None and getattr(embeddings, "shape", None) is not None and embeddings.shape[1] != q.shape[0]:
            # Artifact/query dimension mismatch (e.g. half-updated build):
            # semantic comparison would be meaningless — drop to keyword mode.
            print("[registry] embedding dim mismatch (matrix vs query) - keyword-only")
            q = None
        if q is not None:
            # Matrix is float32 [N, 384]; dot with the query vector directly —
            # no per-record np.array() copies (vectors are unit-normalized, so
            # this IS cosine similarity).
            semantic_score = float(embeddings[i] @ q)
        # Raw pipeline signals, kept for the explainable Match Score (P0-1);
        # in keyword-only mode _semantic stays None (nothing was computed).
        enriched = dict(rec)
        enriched["_semantic"] = round(semantic_score, 4) if semantic_score is not None else None
        enriched["_keyword"] = round(keyword_score, 4)
        # Hybrid score = weighted average of the displayed factors (replaces
        # the old private blend 0.6*semantic + 0.4*keyword that could not be
        # reconciled with the factor list on the card).
        fvals = scoring._factor_values(query, enriched)
        hybrid = scoring.weighted_total(fvals) / 100.0
        if hybrid > threshold:
            enriched["_score"] = round(hybrid, 4)
            results.append(enriched)

    results.sort(key=lambda r: r["_score"], reverse=True)
    return results[:top_k]


def archive_link(record_or_code: str, year: str = "") -> dict:
    """Deterministic link to the public Indian Standards mirror.

    Returns {'url': ..., 'exact': bool} — exact for a guessed document page,
    with the caller free to fall back to the search URL when unsure.
    """
    raw = record_or_code or ""
    num_m = re.search(r"IS\s*:?\s*(\d+)", raw)
    if not num_m:
        return {"url": "https://archive.org/search?query=bureau+of+indian+standards", "exact": False}
    num = num_m.group(1)
    part_m = re.search(r"PART\s*:?\s*(\d+)", raw.upper())
    year = re.sub(r"\D", "", year or "")
    doc_id = f"gov.in.is.{num}.{part_m.group(1)}" if part_m else f"gov.in.is.{num}"
    if year:
        doc_id += f".{year}"
    return {"url": f"https://archive.org/details/{doc_id}", "exact": True}


def archive_search_link(code: str) -> dict:
    q = f"{code} bureau of indian standards"
    return {"url": f"https://archive.org/search?query={q.replace(' ', '+')}", "exact": False}


def clarify_options(query: str) -> dict | None:
    """Rule-based ambiguity resolution — used when the LLM is unavailable.

    Returns {'question', 'helper', 'options': [{'label', 'query'}]} or None.
    """
    q = query.lower()
    if re.search(r"\bsteel\b", q) and not re.search(r"rebar|reinforc|plate|section|beam|sheet|roof|clad|tube|pipe", q):
        return {
            "question": "What is the steel for?",
            "helper": "This changes which standard applies — picking the wrong one is a common tender error.",
            "options": [
                {"label": "Structural framing (plates, beams, sections)", "query": f"{query} — structural framing plates sections"},
                {"label": "Reinforcement bars inside concrete", "query": f"{query} — concrete reinforcement bars rebar"},
                {"label": "Roofing or cladding sheets", "query": f"{query} — roofing cladding galvanized sheets"},
            ],
        }
    if re.search(r"\bcement\b", q) and not re.search(r"grade|opc|ppc|ppc|43|53|33", q):
        return {
            "question": "Which grade / type of cement?",
            "helper": "Each grade has its own standard — citing the wrong grade is a frequent tender defect.",
            "options": [
                {"label": "OPC 33 grade", "query": f"{query} — OPC 33 grade"},
                {"label": "OPC 43 / 53 grade", "query": f"{query} — OPC 53 grade"},
                {"label": "Portland Pozzolana Cement (PPC)", "query": f"{query} — Portland Pozzolana Cement fly ash"},
            ],
        }
    if re.search(r"\bpipe\b|\btube\b", q) and not re.search(r"pvc|steel|gi|galvan|copper|cpvc|swr|duct|hdpe|material", q):
        return {
            "question": "What is the pipe made of?",
            "helper": "Material determines the standard — PVC, steel, HDPE and copper pipes follow different IS codes.",
            "options": [
                {"label": "Galvanized steel (GI) pipe", "query": f"{query} — galvanized steel pipe"},
                {"label": "PVC / plastic pipe", "query": f"{query} — PVC plastic pipe"},
                {"label": "HDPE pipe", "query": f"{query} — HDPE pipe"},
            ],
        }
    return None
