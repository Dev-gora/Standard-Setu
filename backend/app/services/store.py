"""P0-4 / P0-5 — Local persistence for audit history, watchlist, notifications.

No database in this stack, by design: state lives in backend/data/app_state.json
(one JSON file, atomic writes, thread-safe via a process-wide lock). The store
is intentionally tiny and dependency-free so it survives the demo machine.

Change detection (P0-5) is deterministic: when a standard is watched we snapshot
its registry lifecycle fields (latest_version, amendment, title). A check pass
compares the snapshot to the current registry record and emits structured
notifications for: new edition, new amendment, title change. Nothing is
"detected" that the registry does not actually say.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.services import standards_registry as registry

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
STATE_FILE = DATA_DIR / "app_state.json"

_LOCK = threading.RLock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _empty() -> dict:
    return {"history": [], "watchlist": {}, "notifications": []}


def _load() -> dict:
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    else:
        data = {}
    for k, v in _empty().items():
        data.setdefault(k, v)
    return data


def _save(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(STATE_FILE)


# ---------------------------------------------------------------- history ----

def record_event(kind: str, query: str = "", title: str = "", payload: dict | None = None,
                 status: str = "completed", session_id: str = "local") -> str:
    """Append one auditable event; returns its id."""
    event_id = uuid.uuid4().hex[:12]
    with _LOCK:
        data = _load()
        _purge_stale_sessions(data)
        data["history"].append({
            "id": event_id,
            "ts": _now_iso(),
            "kind": kind,                    # recommendation | clarify | tender_check | verification
            "query": query,
            "title": title,
            "status": status,
            "session_id": session_id,
            "payload": payload or {},
        })
        data["history"] = data["history"][-1000:]  # cap: demo-scale retention
        _save(data)
    return event_id


_STALE_SESSION_HOURS = 12


def _purge_stale_sessions(data: dict) -> None:
    """Privacy net: drop activity from sessions that never said goodbye.

    Covers crashed/closed tabs where the browser beacon never fired. Runs
    opportunistically before every write.
    """
    try:
        cutoff = (datetime.now(timezone.utc).astimezone()
                  - timedelta(hours=_STALE_SESSION_HOURS)).isoformat(timespec="seconds")
    except Exception:
        return
    data["history"] = [
        e for e in data["history"]
        if e.get("session_id") in ("local", "", None)  # legacy/local entries stay
        or e.get("ts", "") >= cutoff
    ]
    data["notifications"] = [
        n for n in data.get("notifications", [])
        if n.get("session_id") in ("local", "", None) or n.get("ts", "") >= cutoff
    ]


def list_history(limit: int = 100, kind: str | None = None) -> list[dict]:
    with _LOCK:
        data = _load()
    events = list(reversed(data["history"]))
    if kind:
        events = [e for e in events if e.get("kind") == kind]
    return events[:limit]


def get_event(event_id: str) -> dict | None:
    with _LOCK:
        data = _load()
    for e in data["history"]:
        if e["id"] == event_id:
            return e
    return None


def clear_session_history(session_id: str) -> int:
    """Delete all history/notifications for one browser session (privacy).

    Returns the number of events removed. Watchlist entries are NOT removed:
    they are a deliberate persistence feature the user opted into.
    """
    if not session_id or session_id == "local":
        return 0
    with _LOCK:
        data = _load()
        before = len(data["history"])
        data["history"] = [e for e in data["history"] if e.get("session_id") != session_id]
        data["notifications"] = [
            n for n in data["notifications"] if n.get("session_id") != session_id
        ]
        removed = before - len(data["history"])
        _save(data)
    return removed


# -------------------------------------------------------------- watchlist ----

def add_watch(is_number: str, snapshot: dict, note: str = "") -> dict:
    """Watch a standard. Snapshot = the registry lifecycle fields at add time."""
    with _LOCK:
        data = _load()
        item = {
            "is_number": is_number,
            "title": snapshot.get("title", ""),
            "latest_version": snapshot.get("latest_version", ""),
            "amendment": snapshot.get("amendment", ""),
            "added_at": _now_iso(),
            "last_checked": _now_iso(),
            "note": note,
            "baseline": dict(snapshot),
            "changed": False,
        }
        data["watchlist"][is_number] = item
        _save(data)
        return dict(item)


def remove_watch(is_number: str) -> bool:
    with _LOCK:
        data = _load()
        existed = is_number in data["watchlist"]
        data["watchlist"].pop(is_number, None)
        _save(data)
        return existed


def is_watched(is_number: str) -> bool:
    with _LOCK:
        return is_number in _load()["watchlist"]


def watchlist() -> list[dict]:
    with _LOCK:
        items = list(_load()["watchlist"].values())
    return sorted(items, key=lambda i: i.get("added_at", ""), reverse=True)


def _diff_label(old: dict, new: dict) -> str:
    changes = []
    if old.get("latest_version") != new.get("latest_version"):
        changes.append(f"new edition {new.get('latest_version', '?')}")
    if old.get("amendment") != new.get("amendment"):
        changes.append(f"amendment now '{new.get('amendment', 'none')}'")
    if old.get("title") != new.get("title"):
        changes.append("title updated")
    return "; ".join(changes) if changes else ""


def check_watchlist() -> list[dict]:
    """Re-snapshot every watched standard; emit notifications for real changes.

    Deterministic: compares stored baseline vs current registry values only.
    Returns the list of new notifications (also persisted).
    """
    new_notifications: list[dict] = []
    with _LOCK:
        data = _load()
        for is_number, item in list(data["watchlist"].items()):
            rec = registry.get_by_is_number(is_number)
            if rec is None:
                continue
            current = {
                "title": rec.get("title", ""),
                "latest_version": rec.get("latest_version", ""),
                "amendment": rec.get("amendment", ""),
            }
            label = _diff_label(item.get("baseline", {}), current)
            item["last_checked"] = _now_iso()
            if label and not item.get("changed"):
                item["changed"] = True
                notif = {
                    "id": uuid.uuid4().hex[:12],
                    "ts": _now_iso(),
                    "is_number": is_number,
                    "title": current.get("title", ""),
                    "change": label,
                    "previous": {
                        "latest_version": item.get("latest_version", ""),
                        "amendment": item.get("amendment", ""),
                    },
                    "current": dict(current),
                    "read": False,
                }
                new_notifications.append(notif)
                data["notifications"].insert(0, notif)
            # Always advance the baseline so the change is only alerted once.
            item["baseline"] = dict(current)
            item["latest_version"] = current.get("latest_version", "")
            item["amendment"] = current.get("amendment", "")
        _save(data)
    return new_notifications


def refresh_watch_row(is_number: str) -> dict | None:
    """Current registry state for one watched item + whether it differs from the stored row."""
    with _LOCK:
        item = _load()["watchlist"].get(is_number)
    if not item:
        return None
    rec = registry.get_by_is_number(is_number)
    return {
        "item": item,
        "registry": {
            "title": rec.get("title", "") if rec else "",
            "latest_version": rec.get("latest_version", "") if rec else "",
            "amendment": rec.get("amendment", "") if rec else "",
        } if rec else None,
    }


# ----------------------------------------------------------- notifications ----

def notifications() -> list[dict]:
    with _LOCK:
        return list(_load()["notifications"])


def unread_count() -> int:
    with _LOCK:
        return sum(1 for n in _load()["notifications"] if not n.get("read"))


def mark_notification_read(notification_id: str) -> bool:
    with _LOCK:
        data = _load()
        for n in data["notifications"]:
            if n["id"] == notification_id:
                n["read"] = True
                _save(data)
                return True
    return False
