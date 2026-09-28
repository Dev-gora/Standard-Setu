"use client";

import { useState } from "react";
import { Columns3, Loader2, X, Table2 } from "lucide-react";
import { compareStandards, type CompareResponse } from "@/lib/api";
import { ink, paper, line, brass, good, seal, sans } from "./theme";

/**
 * P1-1 — Standard comparison matrix (2-5 standards, real registry data only).
 * Cells the backend cannot support stay empty — nothing is invented to fill them.
 */
export default function ComparePanel({ onOpenStandard }: { onOpenStandard: (code: string) => void }) {
  const [codes, setCodes] = useState<string[]>([]);
  const [draft, setDraft] = useState("");
  const [result, setResult] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const addCode = () => {
    const c = draft.trim();
    if (!c) return;
    if (codes.length >= 5) {
      setError("Compare up to 5 standards at a time.");
      return;
    }
    if (!codes.includes(c)) setCodes([...codes, c]);
    setDraft("");
    setError(null);
  };

  const removeCode = (c: string) => setCodes(codes.filter((x) => x !== c));

  const run = async () => {
    if (codes.length < 2) {
      setError("Add at least 2 standards to compare.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setResult(await compareStandards(codes));
    } catch {
      setError("Comparison failed - is the backend running?");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="flex items-center gap-3" style={{ marginBottom: 6 }}>
        <span
          className="flex items-center justify-center rounded-full"
          style={{ width: 38, height: 38, background: ink, color: paper, border: `1px solid ${brass}66`, boxShadow: "0 4px 12px rgba(28,36,56,0.18)" }}
        >
          <Table2 size={16} />
        </span>
        <div>
          <h2 style={{ fontSize: 19, color: ink, margin: 0, fontWeight: 400 }}>Compare standards</h2>
          <p style={{ fontSize: 10, color: brass, fontFamily: sans, margin: 0, letterSpacing: "0.16em", textTransform: "uppercase" }}>
            2-5 standards · registry facts only
          </p>
        </div>
      </div>
      <p style={{ fontSize: 13, color: "#6b6650", marginBottom: 14, fontFamily: sans }}>
        Side-by-side attributes for 2-5 Indian Standards, straight from the registry.
        Empty cells mean the registry records nothing for that attribute.
      </p>

      {/* Popular pairings — one click fills the matrix */}
      {codes.length === 0 && !result && (
        <div className="mb-4">
          <p style={{ fontSize: 11, color: "#8b8570", fontFamily: sans, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.14em" }}>
            Popular pairings
          </p>
          <div className="flex flex-wrap gap-2">
            {[
              ["IS 1786", "IS 432 (Part 1)"],
              ["IS 456", "IS 13920"],
              ["IS 1239 (Part 1)", "IS 3589"],
            ].map((pair) => (
              <button
                key={pair.join("+")}
                onClick={() => setCodes(pair)}
                className="inline-flex items-center gap-1.5"
                style={{
                  fontSize: 12.5,
                  color: ink,
                  background: "rgba(255,255,255,0.5)",
                  border: `1px solid ${line}`,
                  borderRadius: 20,
                  padding: "5px 12px",
                  cursor: "pointer",
                  fontFamily: "Georgia, serif",
                }}
              >
                {pair.join(" vs ")}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="flex items-center gap-2 mb-3 flex-wrap">
        {codes.map((c) => (
          <span key={c} style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 13, color: ink, border: `1px solid ${brass}`, borderRadius: 20, padding: "4px 10px", fontFamily: "Georgia, serif" }}>
            {c}
            <button onClick={() => removeCode(c)} style={{ background: "none", border: "none", cursor: "pointer", color: "#8b8570", padding: 0 }} aria-label={`Remove ${c}`}>
              <X size={12} />
            </button>
          </span>
        ))}
        {codes.length < 5 && (
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addCode()}
            placeholder="Add IS code…"
            style={{ border: `1px solid ${line}`, borderRadius: 20, background: "rgba(255,255,255,0.5)", padding: "5px 12px", fontSize: 13, color: ink, width: 150, fontFamily: sans }}
          />
        )}
        <button
          onClick={run}
          disabled={codes.length < 2 || loading}
          style={{
            display: "flex", alignItems: "center", gap: 6,
            background: codes.length >= 2 ? ink : "#b8b39d", color: paper,
            border: "none", borderRadius: 4, padding: "8px 14px",
            fontSize: 13.5, cursor: codes.length >= 2 ? "pointer" : "not-allowed", fontFamily: sans,
          }}
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : <Columns3 size={14} />} Compare selected
        </button>
      </div>

      {error && <p style={{ fontSize: 13, color: seal, fontFamily: sans, marginBottom: 10 }}>{error}</p>}

      {/* Empty state — the ledger awaits */}
      {!result && (
        <div
          className="mt-5 p-6 text-center"
          style={{ border: `1px dashed ${line}`, borderRadius: 8, background: "rgba(255,255,255,0.35)" }}
        >
          <Columns3 size={22} style={{ color: "#b8b39d", margin: "0 auto 8px" }} />
          <p style={{ fontSize: 14.5, color: "#6b6650", fontFamily: "Georgia, serif", fontStyle: "italic", margin: "0 0 6px" }}>
            The comparison ledger opens here
          </p>
          <p style={{ fontSize: 12, color: "#8b8570", fontFamily: sans, margin: 0, maxWidth: 440, marginInline: "auto", lineHeight: 1.55 }}>
            Add two or more IS codes above — the matrix lists edition, certification,
            normative references and scope for each, and leaves any cell the registry
            cannot answer visibly blank rather than guessing.
          </p>
          <div className="mt-4 flex flex-wrap items-center justify-center gap-x-5 gap-y-1.5">
            {[
              ["#8a3324", "Mandatory certification"],
              ["#3f6b4e", "Not mandatory"],
              ["#a5a08c", "Registry has no record"],
            ].map(([color, label]) => (
              <span key={label} className="inline-flex items-center gap-1.5" style={{ fontSize: 11, color: "#6b6650", fontFamily: sans }}>
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: color, display: "inline-block" }} />
                {label}
              </span>
            ))
            }
          </div>
        </div>
      )}

      {result && (
        <div style={{ overflowX: "auto" }}>
          <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 13 }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left", padding: "8px 10px", borderBottom: `2px solid ${ink}`, color: "#8b8570", fontFamily: sans, fontWeight: 400, width: 170 }}>Attribute</th>
                {result.columns.map((col) => (
                  <th key={col.code} style={{ textAlign: "left", padding: "8px 10px", borderBottom: `2px solid ${ink}`, color: ink, fontWeight: 600 }}>
                    {col.found ? (
                      <button onClick={() => onOpenStandard(col.code)} style={{ fontFamily: "Georgia, serif", fontSize: 14.5, color: brass, background: "none", border: "none", cursor: "pointer", textDecoration: "underline", padding: 0 }}>
                        {col.code}
                      </button>
                    ) : (
                      <span style={{ color: "#a5a08c", fontFamily: sans, fontWeight: 400 }}>{col.code}</span>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <Row label="Title" columns={result.columns} render={(c) => c.title} />
              <Row label="Current edition" columns={result.columns} render={(c) => c.latest_version} />
              <Row label="Amendment" columns={result.columns} render={(c) => c.amendment} />
              <Row label="Category" columns={result.columns} render={(c) => c.category} />
              <Row
                label="Certification"
                columns={result.columns}
                render={(c) =>
                  c.certification
                    ? `${c.certification.mandatory ? "Mandatory" : "Not mandatory"}${c.certification.scheme ? ` — ${c.certification.scheme}` : ""}`
                    : ""
                }
                colorize={(c) => (c.certification ? (c.certification.mandatory ? seal : good) : undefined)}
              />
              <Row
                label="Match score (for your query)"
                columns={result.columns}
                render={(c) => (c.match_score !== null && c.match_score !== undefined ? `${c.match_score}/100` : "n/a — not retrieved for this query")}
              />
              <Row label="Source document" columns={result.columns} render={(c) => c.attributes["Source document"] || ""} />
              <Row label="Normative references" columns={result.columns} render={(c) => c.attributes["Normative references"] || ""} />
              <Row label="Scope" columns={result.columns} render={(c) => (c.scope_description || "").slice(0, 140)} />
            </tbody>
          </table>
          {result.columns.some((c) => !c.found) && (
            <p style={{ fontSize: 12, color: "#8b8570", fontFamily: sans, marginTop: 10 }}>
              Columns marked as not found are not in the registry — they are shown for honesty, not compared.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function Row({
  label, columns, render, colorize,
}: {
  label: string;
  columns: CompareResponse["columns"];
  render: (c: CompareResponse["columns"][number]) => string;
  colorize?: (c: CompareResponse["columns"][number]) => string | undefined;
}) {
  return (
    <tr>
      <td style={{ padding: "8px 10px", borderBottom: `1px solid ${line}`, color: "#8b8570", fontFamily: sans, fontSize: 12.5 }}>{label}</td>
      {columns.map((c) => (
        <td key={c.code} style={{ padding: "8px 10px", borderBottom: `1px solid ${line}`, color: colorize?.(c) || (c.found ? "#42402f" : "#a5a08c"), verticalAlign: "top" }}>
          {render(c) || "—"}
        </td>
      ))}
    </tr>
  );
}
