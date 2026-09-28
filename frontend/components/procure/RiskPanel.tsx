"use client";

import { useState } from "react";
import type { RiskResponse, TenderRisk } from "@/lib/api";
import { ink, line, good, seal, sans } from "./theme";

const LEVEL_STYLE: Record<string, { dot: string; color: string; label: string }> = {
  low: { dot: "#3f6b4e", color: good, label: "LOW" },
  medium: { dot: "#a9722f", color: "#a9722f", label: "MEDIUM" },
  high: { dot: "#8a3324", color: seal, label: "HIGH" },
};

/**
 * P1-7 — Specification risk heatmap.
 * Levels come strictly from the deterministic tender-check findings.
 */
export default function RiskPanel({ risk }: { risk: RiskResponse }) {
  const [openFile, setOpenFile] = useState<string | null>(
    risk.files.find((f) => f.overall !== "low")?.file_name || null
  );

  return (
    <div className="mb-6">
      <div className="flex items-center gap-2 mb-3">
        <span style={{ fontSize: 14, color: ink, fontFamily: sans, fontWeight: 600 }}>Tender risk overview</span>
        <span
          style={{
            fontSize: 11.5, fontFamily: sans,
            color: LEVEL_STYLE[risk.overall]?.color,
            border: `1px solid ${LEVEL_STYLE[risk.overall]?.color}`,
            borderRadius: 20, padding: "2px 10px",
          }}
        >
          overall {risk.overall.toUpperCase()}
        </span>
      </div>
      <p style={{ fontSize: 12.5, color: "#6b6650", fontFamily: sans, marginBottom: 12 }}>{risk.summary}</p>

      <div style={{ borderTop: `1px solid ${ink}` }}>
        {risk.files.map((f) => (
          <FileRisk key={f.file_name} file={f} open={openFile === f.file_name} onToggle={() => setOpenFile(openFile === f.file_name ? null : f.file_name)} />
        ))}
      </div>
    </div>
  );
}

function FileRisk({ file, open, onToggle }: { file: TenderRisk; open: boolean; onToggle: () => void }) {
  const st = LEVEL_STYLE[file.overall] || LEVEL_STYLE.low;
  return (
    <div style={{ borderBottom: `1px solid ${line}` }}>
      <button onClick={onToggle} className="w-full flex items-center justify-between gap-3 py-2.5" style={{ background: "none", border: "none", cursor: "pointer", textAlign: "left", padding: "10px 0" }}>
        <span style={{ fontSize: 13.5, color: ink, fontFamily: sans, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{file.file_name}</span>
        <span style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
          <span style={{ width: 9, height: 9, borderRadius: 9, background: st.dot }} />
          <span style={{ fontSize: 11.5, color: st.color, fontFamily: sans }}>{st.label}</span>
        </span>
      </button>

      {open && (
        <div className="pb-4 pl-4 flex flex-col gap-3">
          {file.dimensions.map((d) => {
            const dst = LEVEL_STYLE[d.level] || LEVEL_STYLE.low;
            return (
              <div key={d.dimension} style={{ border: `1px solid ${line}`, borderRadius: 6, background: "rgba(255,255,255,0.5)" }} className="p-3">
                <div className="flex items-center gap-2 mb-1">
                  <span style={{ width: 8, height: 8, borderRadius: 8, background: dst.dot }} />
                  <span style={{ fontSize: 13, color: ink, fontFamily: sans }}>{d.dimension}</span>
                  <span style={{ fontSize: 11, color: dst.color, fontFamily: sans }}>{dst.label}</span>
                </div>
                {d.findings.map((f, i) => (
                  <div key={i} style={{ fontSize: 12.5, color: "#6b6650", marginTop: 2 }}>• {f}</div>
                ))}
                {d.action && (
                  <div style={{ fontSize: 12, color: brassColor(), fontFamily: sans, marginTop: 4 }}>
                    Suggested action: {d.action}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function brassColor() {
  return "#a9722f";
}
