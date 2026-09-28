"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { ScoreBreakdown } from "@/lib/api";
import { ink, line, brass, good, sans } from "./theme";

const CONFIDENCE_COLOR: Record<string, string> = {
  High: good,
  Medium: brass,
  Low: "#8a3324",
};

/**
 * P0-1 — Explainable Match Score ("Match Score", never "confidence %").
 * Every factor is traceable to a real pipeline signal.
 */
export default function MatchScore({ match }: { match: ScoreBreakdown | null }) {
  const [open, setOpen] = useState(false);
  if (!match) return null;

  const confColor = CONFIDENCE_COLOR[match.confidence] || brass;

  return (
    <div className="mb-5">
      <div className="flex items-center gap-3 flex-wrap">
        <div>
          <div style={{ fontSize: 11.5, color: "#8b8570", fontFamily: sans, marginBottom: 2 }}>
            MATCH SCORE
          </div>
          <div style={{ fontSize: 26, color: ink, fontFamily: sans, fontWeight: 600, lineHeight: 1 }}>
            {match.score}
            <span style={{ fontSize: 14, color: "#8b8570", fontWeight: 400 }}> / 100</span>
          </div>
        </div>
        <div
          style={{
            fontSize: 11.5,
            color: confColor,
            border: `1px solid ${confColor}`,
            borderRadius: 20,
            padding: "2px 10px",
            fontFamily: sans,
            marginTop: 14,
          }}
          title="Qualitative confidence derived from the same matching signals"
        >
          Confidence: {match.confidence}
        </div>
        <button
          onClick={() => setOpen(!open)}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
            fontSize: 12.5,
            color: brass,
            background: "none",
            border: "none",
            cursor: "pointer",
            fontFamily: sans,
            marginTop: 14,
          }}
        >
          Why this score? {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>
      </div>

      {open && (
        <div
          style={{ border: `1px solid ${line}`, borderRadius: 6, background: "rgba(255,255,255,0.5)" }}
          className="mt-3 p-4"
        >
          {match.factors.map((f) => (
            <div key={f.label} className="mb-3 last:mb-0">
              <div className="flex items-center justify-between mb-1">
                <span style={{ fontSize: 13, color: ink, fontFamily: sans }}>{f.label}</span>
                <span style={{ fontSize: 12.5, color: "#6b6650", fontFamily: sans }}>{f.value}%</span>
              </div>
              <div style={{ height: 6, background: "#e7e3d4", borderRadius: 3 }}>
                <div
                  style={{
                    height: 6,
                    width: `${f.value}%`,
                    background: f.label === "Certification" ? (f.value > 0 ? "#a9722f" : "#c9c3ab") : brass,
                    borderRadius: 3,
                  }}
                />
              </div>
              {f.detail && (
                <div style={{ fontSize: 11.5, color: "#8b8570", fontFamily: sans, marginTop: 3 }}>
                  {f.detail}
                </div>
              )}
            </div>
          ))}
          <div style={{ borderTop: `1px solid ${line}`, marginTop: 12, paddingTop: 8, fontSize: 11, color: "#a5a08c", fontFamily: sans }}>
            Signals: {Object.entries(match.signals)
              .map(([k, v]) => `${k} ${v === null ? "n/a" : v}`)
              .join(" · ")}
            {" · "}mode: {match.embedding_mode === "semantic" ? "semantic + keyword" : "keyword-only"}
            {" — "}a matching heuristic, not a calibrated probability.
          </div>
        </div>
      )}
    </div>
  );
}
