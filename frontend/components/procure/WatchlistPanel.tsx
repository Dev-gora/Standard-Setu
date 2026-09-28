"use client";

import { useCallback, useEffect, useState } from "react";
import { Bell, BellOff, Plus, RefreshCw, X } from "lucide-react";
import {
  getWatchlist, addWatch, removeWatch, markNotificationRead,
  type WatchlistResponse, type StandardChangeNotification,
} from "@/lib/api";
import { ink, paper, line, brass, good, seal, sans } from "./theme";

/**
 * P0-5 — Standard watchlist + in-app change notifications.
 * Detection is deterministic on the backend (registry snapshot diffing).
 */
export default function WatchlistPanel({ onOpenStandard }: { onOpenStandard: (code: string) => void }) {
  const [data, setData] = useState<WatchlistResponse | null>(null);
  const [newCode, setNewCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback((check: boolean) => {
    setBusy(true);
    getWatchlist(check)
      .then(setData)
      .catch(() => setError("Could not load the watchlist - is the backend running?"))
      .finally(() => setBusy(false));
  }, []);

  useEffect(() => {
    load(true);
  }, [load]);

  const add = async () => {
    if (!newCode.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await addWatch(newCode.trim());
      setNewCode("");
      await load(true);
    } catch {
      setError("Could not watch that code - is it in the registry?");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (code: string) => {
    await removeWatch(code);
    await load(false);
  };

  const markRead = async (n: StandardChangeNotification) => {
    await markNotificationRead(n.id);
    await load(false);
  };

  return (
    <div>
      <h2 style={{ fontSize: 19, color: ink, marginBottom: 4, fontWeight: 400 }}>Standard watchlist</h2>
      <p style={{ fontSize: 13, color: "#6b6650", marginBottom: 16, fontFamily: sans }}>
        Watch standards you procure often. Standard Setu compares each watched standard's
        lifecycle fields (edition, amendment, title) against its recorded baseline and alerts
        you in-app when the registry changes.
      </p>

      {/* Notifications */}
      {data?.notifications && data.notifications.length > 0 && (
        <div className="mb-5 flex flex-col gap-2">
          {data.notifications.slice(0, 8).map((n) => (
            <div
              key={n.id}
              style={{
                border: `1px solid ${n.read ? line : brass}`,
                background: n.read ? "rgba(255,255,255,0.4)" : "#f6ecda",
                borderRadius: 6,
              }}
              className="p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div style={{ fontSize: 13.5, color: ink }}>
                    {n.read ? <BellOff size={13} style={{ display: "inline", marginRight: 6, color: "#8b8570" }} /> : <Bell size={13} style={{ display: "inline", marginRight: 6, color: brass }} />}
                    {n.is_number} changed — {n.change}
                  </div>
                  <div style={{ fontSize: 12, color: "#6b6650", fontFamily: sans, marginTop: 4 }}>
                    Previous: {n.previous.latest_version || "unknown"}{n.previous.amendment ? ` + ${n.previous.amendment}` : ""}
                    {" · "}Current: {n.current.latest_version || "unknown"}{n.current.amendment ? ` + ${n.current.amendment}` : ""}
                  </div>
                  <div style={{ fontSize: 11, color: "#a5a08c", fontFamily: sans, marginTop: 2 }}>
                    {new Date(n.ts).toLocaleString()}
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <button onClick={() => onOpenStandard(n.is_number)} style={{ fontSize: 12, color: brass, background: "none", border: "none", textDecoration: "underline", cursor: "pointer", fontFamily: sans }}>
                    View changes
                  </button>
                  {!n.read && (
                    <button onClick={() => markRead(n)} style={{ background: "none", border: "none", cursor: "pointer", color: "#8b8570" }} aria-label="Mark read">
                      <X size={13} />
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add row */}
      <div className="flex items-center gap-2 mb-4">
        <input
          value={newCode}
          onChange={(e) => setNewCode(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add()}
          placeholder="Add a standard, e.g. IS 1786"
          style={{
            flex: 1,
            border: `1px solid ${line}`,
            borderRadius: 4,
            background: "rgba(255,255,255,0.5)",
            padding: "9px 12px",
            fontSize: 14,
            color: ink,
            fontFamily: sans,
          }}
        />
        <button
          onClick={add}
          disabled={!newCode.trim() || busy}
          style={{
            display: "flex", alignItems: "center", gap: 6,
            background: newCode.trim() ? ink : "#b8b39d", color: paper,
            border: "none", borderRadius: 4, padding: "9px 14px",
            fontSize: 13.5, cursor: newCode.trim() ? "pointer" : "not-allowed", fontFamily: sans,
          }}
        >
          <Plus size={14} /> Watch
        </button>
        <button
          onClick={() => load(true)}
          disabled={busy}
          style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12.5, color: "#6b6650", background: "none", border: `1px solid ${line}`, borderRadius: 4, padding: "9px 12px", cursor: "pointer", fontFamily: sans }}
        >
          <RefreshCw size={13} className={busy ? "animate-spin" : ""} /> Check changes
        </button>
      </div>

      {error && <p style={{ fontSize: 13, color: seal, fontFamily: sans, marginBottom: 10 }}>{error}</p>}

      {/* Items */}
      {data && data.items.length === 0 && (
        <p style={{ fontSize: 14, color: "#6b6650", fontFamily: sans }}>
          Nothing watched yet — add a standard above or from any recommendation.
        </p>
      )}
      <div style={{ borderTop: `1px solid ${ink}` }}>
        {data?.items.map((it) => (
          <div key={it.is_number} className="flex items-center justify-between gap-3 py-3" style={{ borderBottom: `1px solid ${line}` }}>
            <div className="min-w-0">
              <button onClick={() => onOpenStandard(it.is_number)} style={{ fontSize: 14.5, color: brass, background: "none", border: "none", cursor: "pointer", fontFamily: "Georgia, serif", textDecoration: "underline", textDecorationColor: "rgba(169,114,47,0.4)", padding: 0 }}>
                {it.is_number}
              </button>
              <span style={{ fontSize: 13.5, color: ink }}> — {it.title}</span>
              <div style={{ fontSize: 12, color: "#6b6650", fontFamily: sans, marginTop: 2 }}>
                {it.latest_version}{it.amendment ? ` — ${it.amendment}` : ""}
                {it.changed && <span style={{ color: seal }}> · changed since added</span>}
                {" · "}Last checked: {it.last_checked ? new Date(it.last_checked).toLocaleDateString() : "-"}
              </div>
            </div>
            <button onClick={() => remove(it.is_number)} style={{ background: "none", border: "none", cursor: "pointer", color: "#8b8570", flexShrink: 0 }} aria-label={`Unwatch ${it.is_number}`}>
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
