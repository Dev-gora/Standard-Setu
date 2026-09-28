"use client";

import { useEffect, useState } from "react";
import { History as HistoryIcon, Loader2 } from "lucide-react";
import { getHistory, type HistoryEntry } from "@/lib/api";
import { ink, line, brass, seal, sans } from "./theme";

const KIND_LABEL: Record<string, string> = {
  recommendation: "Recommendation",
  clarify: "Clarification",
  tender_check: "Tender check",
  verification: "Licence verification",
};

const KIND_COLOR: Record<string, string> = {
  recommendation: "#3f6b4e",
  clarify: "#a9722f",
  tender_check: "#1c2438",
  verification: "#a9722f",
};

const TIMELINE_STEPS: { key: string; label: string }[] = [
  { key: "query", label: "User query" },
  { key: "clarification", label: "Clarification" },
  { key: "extraction", label: "Requirement extraction" },
  { key: "candidates", label: "Candidate standards" },
  { key: "ranking", label: "Ranking" },
  { key: "recommendation", label: "Recommendation" },
  { key: "evidence", label: "Evidence" },
  { key: "certification", label: "Certification analysis" },
  { key: "tender", label: "Tender specification" },
];

/** Which timeline steps have real recorded data for this entry. */
function stepsFor(entry: HistoryEntry): Record<string, unknown> {
  const p = (entry.payload || {}) as Record<string, unknown>;
  if (entry.kind === "recommendation") {
    return {
      query: entry.query,
      clarification: p.clarified_from ? "clarified selection" : null,
      extraction: entry.query,
      candidates: p.candidates,
      ranking: p.candidates,
      recommendation: p.selected,
      evidence: p.evidence,
      certification: p.candidates,
      tender: p.tender_block,
    };
  }
  if (entry.kind === "tender_check") {
    return {
      query: entry.query,
      extraction: `${p.total ?? "?"} document(s) parsed`,
      candidates: p.files,
      ranking: null,
      recommendation: `${p.passing ?? "?"} passing`,
      evidence: p.files,
      certification: p.files,
      tender: null,
    };
  }
  if (entry.kind === "verification") {
    return {
      query: entry.query,
      recommendation: p.status,
      evidence: p.detail,
    };
  }
  return { query: entry.query };
}

/** P0-4 — Auditable procurement history. */
export default function HistoryPanel() {
  const [entries, setEntries] = useState<HistoryEntry[] | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getHistory(80)
      .then((d) => setEntries(d.entries))
      .catch(() => setError("Could not load history - is the backend running?"));
  }, []);

  if (error) return <p style={{ fontSize: 13.5, color: seal, fontFamily: sans }}>{error}</p>;
  if (!entries) return <Loader2 size={16} className="animate-spin" style={{ color: "#8b8570" }} />;
  if (entries.length === 0) {
    return (
      <p style={{ fontSize: 14, color: "#6b6650", fontFamily: sans }}>
        No procurement activity recorded yet. Recommendations, tender checks and licence
        verifications are logged here automatically.
      </p>
    );
  }

  return (
    <div>
      <h2 style={{ fontSize: 19, color: ink, marginBottom: 14, fontWeight: 400 }}>Procurement history</h2>
      <div style={{ borderTop: `1px solid ${ink}` }}>
        {entries.map((e) => {
          const open = openId === e.id;
          const steps = open ? stepsFor(e) : {};
          return (
            <div key={e.id} style={{ borderBottom: `1px solid ${line}` }}>
              <button
                onClick={() => setOpenId(open ? null : e.id)}
                className="w-full flex items-center justify-between gap-3 py-3"
                style={{ background: "none", border: "none", cursor: "pointer", padding: "10px 0", textAlign: "left" }}
              >
                <div className="min-w-0">
                  <div style={{ fontSize: 13.5, color: ink }}>
                    {new Date(e.ts).toLocaleDateString()} — {e.query || e.title}
                  </div>
                  <div style={{ fontSize: 11.5, color: "#8b8570", fontFamily: sans, marginTop: 2 }}>
                    {KIND_LABEL[e.kind] || e.kind}
                    {e.payload?.selected ? ` — ${(e.payload as { selected: string }).selected}` : ""}
                  </div>
                </div>
                <span
                  style={{
                    fontSize: 11,
                    color: KIND_COLOR[e.kind] || "#8b8570",
                    border: `1px solid ${KIND_COLOR[e.kind] || line}`,
                    borderRadius: 20,
                    padding: "2px 9px",
                    fontFamily: sans,
                    flexShrink: 0,
                  }}
                >
                  {e.status}
                </span>
              </button>

              {open && (
                <div className="pb-4 pl-2">
                  <div style={{ fontSize: 11.5, color: "#8b8570", fontFamily: sans, marginBottom: 10 }}>
                    AUDIT TIMELINE
                  </div>
                  {TIMELINE_STEPS.map((step, i) => {
                    const value = steps[step.key];
                    const has = value !== null && value !== undefined;
                    return (
                      <div key={step.key} className="flex items-start gap-3">
                        <div className="flex flex-col items-center" style={{ width: 14 }}>
                          <div style={{
                            width: 7, height: 7, borderRadius: 7,
                            background: has ? "#a9722f" : "#d9d4c0",
                            marginTop: 5,
                          }} />
                          {i < TIMELINE_STEPS.length - 1 && (
                            <div style={{ width: 1, height: 16, background: "#d9d4c0" }} />
                          )}
                        </div>
                        <div className="pb-2">
                          <div style={{ fontSize: 12.5, color: has ? ink : "#a5a08c", fontFamily: sans }}>
                            {step.label}{!has && " (not applicable)"}
                          </div>
                          {has && typeof value === "string" && value.length < 200 && (
                            <div style={{ fontSize: 12, color: "#6b6650" }}>{value}</div>
                          )}
                          {has && step.key === "candidates" && Array.isArray(value) && (
                            <div style={{ fontSize: 12, color: "#6b6650", fontFamily: sans }}>
                              {(value as { code?: string; file_name?: string }[]).slice(0, 5).map((c, j) => (
                                <div key={j}>· {c.code || c.file_name}</div>
                              ))}
                            </div>
                          )}
                          {has && step.key === "tender" && typeof value === "string" && (
                            <div style={{ fontSize: 12, color: "#6b6650", fontStyle: "italic" }}>
                              {(value as string).slice(0, 160)}…
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                  <details style={{ marginTop: 6 }}>
                    <summary style={{ fontSize: 12, color: brass, cursor: "pointer", fontFamily: sans }}>
                      Raw audit record
                    </summary>
                    <pre style={{
                      fontSize: 10.5, color: "#6b6650", background: "rgba(255,255,255,0.6)",
                      padding: 10, borderRadius: 4, overflowX: "auto", marginTop: 6,
                    }}>
                      {JSON.stringify(e, null, 1)}
                    </pre>
                  </details>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
