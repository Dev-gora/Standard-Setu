"""P0-3 — BIS supplier licence verification.

Reality check (verified during development): BIS does not publish an open JSON
API. Licence lookup lives on the official Manakonline portal
(https://www.manakonline.in/MANAK/ApplicationLicenceRelatedrpt), an ASP.NET
form application. There is no documented API to call.

Design therefore follows the honesty rules from the product brief:

1. FORMAT VALIDATION — CM/L-XXXXXXXXXX is validated locally first. A malformed
   licence never hits the network and is reported as `invalid`.
2. POLITE LOOKUP — at most ONE GET against the official portal per verification,
   short timeout, no retries, no scraping of paginated lists.
3. HONEST STATES — if the portal cannot be reached, or the response cannot be
   interpreted with certainty, we return `source_unavailable` /
   `unable_to_verify`. We NEVER claim "valid" without a real positive response.
4. CACHE + TIMESTAMP — results are cached in backend/data/verify_cache.json with
   a "last verified" ISO timestamp so the UI can always show provenance.
"""

from __future__ import annotations

import json
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
CACHE_FILE = DATA_DIR / "verify_cache.json"

CACHE_TTL_SECONDS = 6 * 60 * 60  # re-verify after 6h
LOOKUP_TIMEOUT_SECONDS = 8.0
MIN_REQUEST_INTERVAL = 3.0       # politeness: never hammer the portal

BIS_PORTAL_URL = "https://www.manakonline.in/MANAK/ApplicationLicenceRelatedrpt"
BIS_PORTAL_BASE = "https://www.manakonline.in"

_LOCK = threading.Lock()
_LAST_REQUEST_TS = 0.0

# CM/L-XXXXXXXXXX — licence numbers are CM/L- followed by ~10 digits
LICENCE_RE = re.compile(r"^CM\s*/\s*L\s*[-–]?\s*(\d{8,12})$", re.IGNORECASE)


def normalize_licence(raw: str) -> str:
    """Normalize 'cml 8700123456' / 'CM/L-8700123456' -> 'CM/L-8700123456'."""
    s = (raw or "").strip().upper().replace("–", "-")
    # Common compact typing 'CML 8700123456' -> 'CM/L-8700123456'
    s = re.sub(r"^CML\s*", "CM/L-", s)
    m = LICENCE_RE.search(s)
    if not m:
        return s
    return f"CM/L-{m.group(1)}"


def licence_format_valid(raw: str) -> bool:
    return bool(LICENCE_RE.match((raw or "").strip().upper().replace("–", "-")))


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_cache(cache: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")


def _cache_get(licence: str) -> dict | None:
    entry = _load_cache().get(licence)
    if not entry:
        return None
    try:
        age = time.time() - datetime.fromisoformat(entry["last_verified"]).timestamp()
    except Exception:
        return None
    if age > CACHE_TTL_SECONDS:
        return None
    return entry


def _cache_put(licence: str, result: dict) -> None:
    with _LOCK:
        cache = _load_cache()
        cache[licence] = result
        _save_cache(cache)


def _throttle() -> None:
    global _LAST_REQUEST_TS
    with _LOCK:
        wait = MIN_REQUEST_INTERVAL - (time.time() - _LAST_REQUEST_TS)
        if wait > 0:
            time.sleep(wait)
        _LAST_REQUEST_TS = time.time()


# Explicit licence states (audit item 8). The legacy API statuses
# (invalid / not_found / unable_to_verify / source_unavailable) are preserved
# as a compatibility mapping so existing clients and tests keep working.
LICENCE_STATES = {
    "INVALID_FORMAT": "invalid",
    "NOT_FOUND": "not_found",
    "SOURCE_UNAVAILABLE": "source_unavailable",
    "SOURCE_LOCATED": "unable_to_verify",   # licence seen, but active-status not established
    "VERIFIED_ACTIVE": "valid",
    "VERIFIED_EXPIRED": "expired",
    "VERIFIED_CANCELLED": "invalid",
    "VERIFIED_SCOPE_MATCH": "valid",
    "VERIFIED_SCOPE_MISMATCH": "valid",
    "MANUAL_REVIEW_REQUIRED": "unable_to_verify",
}


def _portal_lookup(licence: str) -> dict:
    """Single polite GET against the official portal.

    Returns {'status': ..., 'detail': ..., 'found_fields': {...}} — the caller
    decides what may be claimed. Only a response that clearly contains the
    licence number allows a non-negative result.

    What this probe CAN honestly establish (audit item 8):
      - the portal was reachable or not
      - whether the licence number appears anywhere in the response
    What it CANNOT establish: active/expired/cancelled status, licensee,
    product scope. Those live behind the portal's interactive form, which this
    tool deliberately does not scrape — so the result stays at SOURCE_LOCATED
    (legacy: unable_to_verify) at best, and the UI says exactly that.
    """
    try:
        import httpx

        _throttle()
        # The portal is form-based; a plain GET with the licence echoed is the
        # most controlled probe available. Anything else (postback scraping)
        # would violate the "no aggressive scraping" rule.
        resp = httpx.get(
            BIS_PORTAL_URL,
            params={"licNo": licence},
            timeout=LOOKUP_TIMEOUT_SECONDS,
            headers={"User-Agent": "StandardSetu/1.0 (procurement verification; contact: demo)"},
            follow_redirects=True,
        )
    except Exception as exc:
        return {
            "status": "SOURCE_UNAVAILABLE",
            "detail": f"BIS portal could not be reached ({type(exc).__name__}). "
                      f"Verify manually at {BIS_PORTAL_URL}.",
        }

    if resp.status_code != 200:
        return {
            "status": "SOURCE_UNAVAILABLE",
            "detail": f"BIS portal returned HTTP {resp.status_code}. "
                      f"Verify manually at {BIS_PORTAL_URL}.",
        }

    body = resp.text or ""
    digits = licence.split("-")[-1]
    present = licence.replace("CM/L-", "") in body.replace("CM/L-", "") or digits in body

    if not present:
        # The portal answered but did not show this licence. Because the portal
        # is form-driven, an empty page is NOT proof of non-existence.
        return {
            "status": "NOT_FOUND",
            "detail": "The BIS portal responded but did not return a record for this "
                      "licence number via automated lookup. This is not conclusive — "
                      f"confirm on the official portal: {BIS_PORTAL_URL}",
        }

    # A page that echoes the licence still doesn't give structured validity
    # fields through this controlled GET; we can honestly say it was seen.
    return {
        "status": "SOURCE_LOCATED",
        "detail": "The licence number appears on the BIS portal, but active/expired status, "
                  "licensee and product scope are behind an interactive form that this tool "
                  "does not scrape. MANUAL REVIEW: confirm the details at " + BIS_PORTAL_URL,
    }


def verify_licence(licence_number: str, supplier_name: str = "", is_number: str = "") -> dict:
    """Verify one BIS licence. Always returns an honest, timestamped result.

    `status` uses the explicit LICENCE_STATES vocabulary internally and is
    mapped to the legacy API vocabulary for compatibility (see _shape).
    """
    licence = normalize_licence(licence_number)
    result: dict

    if not licence:
        result = {
            "status": "INVALID_FORMAT",
            "detail": "No licence number provided. Format: CM/L-XXXXXXXXXX.",
            "last_verified": _now_iso(),
        }
    elif not licence_format_valid(licence):
        result = {
            "status": "INVALID_FORMAT",
            "detail": "Licence number format is not valid. Expected CM/L-XXXXXXXXXX "
                      "(BIS manufacturing licence format).",
            "last_verified": _now_iso(),
        }
    else:
        cached = _cache_get(licence)
        if cached:
            out = dict(cached)
            out["cached"] = True
            out["message"] = "Loaded from cache — re-verify for a fresh check."
            return _shape(out, licence, supplier_name, is_number)
        lookup = _portal_lookup(licence)
        result = {
            "status": lookup["status"],
            "detail": lookup["detail"],
            "product": "",
            "validity": "",
            "last_verified": _now_iso(),
            "cached": False,
        }
        _cache_put(licence, result)

    return _shape(result, licence, supplier_name, is_number)


def _shape(result: dict, licence: str, supplier_name: str, is_number: str) -> dict:
    """Attach request context to a verification result (cache-safe).

    Also maps the explicit state (e.g. SOURCE_LOCATED) to the legacy API status
    (e.g. unable_to_verify) and exposes both: `state` = exact audit state,
    `status` = legacy compatibility value used by the frontend.
    """
    out = dict(result)
    raw_state = out.get("status", "MANUAL_REVIEW_REQUIRED")
    out["state"] = raw_state
    out["status"] = LICENCE_STATES.get(raw_state, raw_state)
    out.setdefault("cached", False)
    out.update({
        "licence_number": licence,
        "supplier_name": supplier_name or out.get("supplier_name", ""),
        "is_number": is_number or out.get("is_number", ""),
        "source": f"BIS portal ({BIS_PORTAL_BASE})",
        "source_url": BIS_PORTAL_URL,
    })
    return out
