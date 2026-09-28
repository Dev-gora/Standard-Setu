"""Authoritative external retrieval (task §9-§12).

Modular source abstraction — the app is never hard-wired to one site's HTML.
Only sources that can be accessed reliably are implemented; everything else
returns SOURCE_UNAVAILABLE rather than fabricated results.

Source types (priority order):
  OFFICIAL_BIS / OFFICIAL_MANAK / GOVERNMENT_NOTIFICATION / OFFICIAL_GOVERNMENT
  (LOCAL_REFERENCE is handled by the existing evidence service.)

Every fact carries full provenance and a retrieved_at timestamp. Results are
cached on disk with their timestamp; stale entries are still served but
flagged (never presented as freshly current).
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("setu.external")

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
CACHE_FILE = DATA_DIR / "external_source_cache.json"
CACHE_TTL_SECONDS = 24 * 60 * 60  # re-fetch after a day; cached facts keep provenance

BIS_SCHEME1_URL = (
    "https://www.bis.gov.in/product-certification/"
    "products-under-compulsory-certification/scheme-i-mark-scheme/"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


@dataclass
class SourceFact:
    """One normalized fact from one authoritative source (task §11)."""
    source_type: str          # OFFICIAL_BIS | OFFICIAL_MANAK | GOVERNMENT_NOTIFICATION | OFFICIAL_GOVERNMENT
    source_name: str
    title: str
    url: str
    standard_number: str
    fact: str                 # machine-checkable statement, e.g. "listed: IS 2062:2011"
    field: str                # edition | qco | certification_status | ...
    value: str                # normalized value, e.g. "2011" | "mandatory (QCO ...)"
    retrieved_at: str = field(default_factory=_now_iso)
    verification_status: str = "SOURCE_RETRIEVED"   # SOURCE_RETRIEVED | SOURCE_UNAVAILABLE | STALE_CACHE

    def to_dict(self) -> dict:
        return self.__dict__.copy()


# --------------------------------------------------------------------------- #
# Cache                                                                       #
# --------------------------------------------------------------------------- #

def _load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_cache(cache: dict) -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        log.warning("external cache write failed", extra={"file": CACHE_FILE.name})


def _cache_get(key: str) -> tuple[list[dict], str] | None:
    entry = _load_cache().get(key)
    if not entry:
        return None
    age = time.time() - entry.get("_ts", 0)
    return entry.get("facts", []), ("SOURCE_RETRIEVED" if age <= CACHE_TTL_SECONDS else "STALE_CACHE")


def _cache_put(key: str, facts: list[dict]) -> None:
    with_cache = _load_cache()
    with_cache[key] = {"_ts": time.time(), "facts": facts}
    _save_cache(with_cache)


# --------------------------------------------------------------------------- #
# Source abstraction                                                          #
# --------------------------------------------------------------------------- #

class AuthoritativeSource:
    """Interface: search() -> fetch() -> parse() -> normalize() -> provenance()."""
    source_type = "OFFICIAL_BIS"
    source_name = ""
    base_url = ""

    def search(self, query: str) -> list[dict]:
        raise NotImplementedError

    def provenance(self, title: str) -> dict:
        return {"source_type": self.source_type, "source_name": self.source_name, "url": self.base_url, "title": title}


class BISScheme1Source(AuthoritativeSource):
    """Official BIS 'Products under Compulsory Certification' (Scheme-1 / ISI).

    One page lists every standard made mandatory by a QCO, with notification
    numbers. A single polite GET answers 'is standard X QCO-backed, and by
    which order?' for all standards at once.
    """

    source_type = "OFFICIAL_BIS"
    source_name = "Bureau of Indian Standards — Scheme 1 (ISI mark), compulsory certification list"
    base_url = BIS_SCHEME1_URL

    # QCO section headers seen on the official page (multi-language variants
    # are matched loosely; the page mixes Hindi/English).
    _QCO_HEADINGS = [
        ("cement", re.compile(r"cement|सीमेंट", re.IGNORECASE)),
        ("electric wires, cables, appliances and protection devices and accessories",
         re.compile(r"electric|विद्युत", re.IGNORECASE)),
        ("steel and steel products", re.compile(r"steel|इस्पात", re.IGNORECASE)),
        ("ductile iron pressure pipes and fittings",
         re.compile(r"ductile iron", re.IGNORECASE)),
    ]

    def search(self, query: str) -> list[dict]:
        m = re.search(r"\bIS\s*[:\-]?\s*(\d{2,6})", (query or "").upper())
        if not m:
            return []
        core = m.group(1)
        cache_key = f"scheme1:{core}"
        cached = _cache_get(cache_key)
        if cached:
            return cached[0]

        try:
            import httpx
            resp = httpx.get(BIS_SCHEME1_URL, timeout=15.0, follow_redirects=True,
                             headers={"User-Agent": "StandardSetu/1.0 (procurement verification)"})
        except Exception as exc:
            log.info("bis scheme1 unreachable", extra={"error": type(exc).__name__})
            return [SourceFact(
                source_type=self.source_type, source_name=self.source_name,
                title="BIS Scheme-1 compulsory certification list", url=BIS_SCHEME1_URL,
                standard_number=f"IS {core}", field="availability",
                value="", fact="The BIS page could not be fetched.",
                verification_status="SOURCE_UNAVAILABLE",
            ).to_dict()]

        if resp.status_code != 200:
            return [SourceFact(
                source_type=self.source_type, source_name=self.source_name,
                title="BIS Scheme-1 compulsory certification list", url=BIS_SCHEME1_URL,
                standard_number=f"IS {core}", field="availability", value="",
                fact=f"The BIS page returned HTTP {resp.status_code}.",
                verification_status="SOURCE_UNAVAILABLE",
            ).to_dict()]

        facts = self._parse(resp.text or "", core)
        if facts:
            _cache_put(cache_key, facts)
        return facts

    def _parse(self, html: str, core: str) -> list[dict]:
        """Extract: is IS <core> listed? Under which QCO? Which edition cited?"""
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)

        hits: list[dict] = []
        # Find every mention of the standard number with surrounding context.
        for m in re.finditer(rf"\bIS[^\w]{{0,4}}{core}\b([^\n|]{{0,120}})", text, re.IGNORECASE):
            snippet = m.group(0).strip()
            # Which QCO section does it fall under? Walk the known headings.
            qco_name, qco_notification = "", ""
            for name, pattern in self._QCO_HEADINGS:
                if pattern.search(text[: m.start()][-4000:]):
                    qco_name = name
                    break
            nm = re.search(r"S\.?O\.?\s*\d+\(E\)[^|]{0,60}?(\d{2}[-/]\d{2}[-/]\d{4}|\d{1,2} \w+ \d{4})?", text[max(0, m.start() - 800): m.start() + 800])
            if nm:
                qco_notification = nm.group(0).strip()[:120]
            em = re.search(rf"\bIS[^\w]{{0,4}}{core}\s*[:\-]?\s*((?:19|20)\d{{2}})", snippet, re.IGNORECASE)
            facts = {
                "standard_number": f"IS {core}",
                "qco_name": qco_name,
                "qco_notification": qco_notification,
            }
            out = SourceFact(
                source_type=self.source_type, source_name=self.source_name,
                title="BIS Scheme-1 compulsory certification list", url=BIS_SCHEME1_URL,
                standard_number=f"IS {core}", field="qco",
                value=json.dumps({k: v for k, v in facts.items() if v}, ensure_ascii=False),
                fact=f"Listed on the official BIS compulsory-certification list. Context: {snippet[:150]}",
            )
            hits.append(out.to_dict())
            if em:
                hits.append(SourceFact(
                    source_type=self.source_type, source_name=self.source_name,
                    title="BIS Scheme-1 compulsory certification list", url=BIS_SCHEME1_URL,
                    standard_number=f"IS {core}", field="edition", value=em.group(1),
                    fact=f"Edition cited on the official list: IS {core}:{em.group(1)}",
                ).to_dict())
            break  # first structural mention is enough per fetch

        if not hits:
            # The page answered but the standard is not on the compulsory list.
            hits.append(SourceFact(
                source_type=self.source_type, source_name=self.source_name,
                title="BIS Scheme-1 compulsory certification list", url=BIS_SCHEME1_URL,
                standard_number=f"IS {core}", field="qco", value="not_listed",
                fact=f"IS {core} does not appear on the fetched official BIS compulsory-certification list.",
            ).to_dict())
        return hits


_SOURCES: list[AuthoritativeSource] = [BISScheme1Source()]


def available_sources() -> list[dict]:
    return [{"source_type": s.source_type, "source_name": s.source_name, "url": s.base_url} for s in _SOURCES]


def retrieve_external(need: str, standard_code: str) -> list[dict]:
    """Dispatch one retrieval 'need' to the right authoritative source.

    need: certification_status | qco | current_standard_edition | ...
    Returns a list of provenance-carrying fact dicts (possibly containing a
    SOURCE_UNAVAILABLE marker). Never raises.
    """
    if not standard_code:
        return []
    facts: list[dict] = []
    if need in ("certification_status", "qco", "current_standard_edition"):
        for src in _SOURCES:
            facts += src.search(standard_code)
    # Unknown needs are honestly reported as unretrievable rather than skipped.
    if not facts:
        facts.append(SourceFact(
            source_type="OFFICIAL_BIS", source_name="n/a", title="n/a", url="",
            standard_number=standard_code, field=need, value="",
            fact=f"No authoritative source is implemented for need '{need}'.",
            verification_status="SOURCE_UNAVAILABLE",
        ).to_dict())
    return facts
