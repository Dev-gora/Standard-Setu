"use client";

import { Printer, X } from "lucide-react";
import type { ReportResponse } from "@/lib/api";
import { ink, paper, paperDeep, line, brass, seal, good, sans, serif } from "./theme";

/**
 * P1-10 — Unified procurement recommendation report.
 * Combines WHAT / WHY / EVIDENCE / COMPLIANCE / RISK / ACTION from the
 * backend report payload. Printable via window.print() with a print
 * stylesheet that hides the app chrome.
 */
export default function ReportView({ report, onClose }: { report: ReportResponse; onClose: () => void }) {
  const s = report.standard;

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(28,36,56,0.45)", zIndex: 60, overflowY: "auto" }}>
      <style>{`
        @media print {
          body * { visibility: hidden; }
          .print-report, .print-report * { visibility: visible; }
          .print-report { position: absolute; left: 0; top: 0; width: 100%; }
          .no-print { display: none !important; }
        }
      `}</style>

      <div className="max-w-3xl mx-auto my-6 px-4">
        <div className="no-print flex items-center justify-between mb-3">
          <span style={{ fontSize: 12.5, color: "#f1efe6", fontFamily: sans }}>Unified recommendation report</span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => window.print()}
              style={{ display: "inline-flex", alignItems: "center", gap: 6, background: paper, color: ink, border: "none", borderRadius: 4, padding: "8px 14px", fontSize: 13.5, cursor: "pointer", fontFamily: sans }}
            >
              <Printer size={14} /> Print / Save as PDF
            </button>
            <button onClick={onClose} style={{ background: paper, border: "none", borderRadius: 4, cursor: "pointer", padding: "8px 10px", color: ink }} aria-label="Close report">
              <X size={16} />
            </button>
          </div>
        </div>

        <div className="print-report" style={{ background: paper, border: `1px solid ${line}`, borderRadius: 8, padding: 32 }}>
          <div style={{ textAlign: "center", borderBottom: `2px solid ${ink}`, paddingBottom: 14, marginBottom: 20 }}>
            <div style={{ fontSize: 11, color: "#8b8570", fontFamily: sans, letterSpacing: 2 }}>PROCUREMENT STANDARD RECOMMENDATION</div>
            <div style={{ fontSize: 12, color: "#a5a08c", fontFamily: sans, marginTop: 4 }}>
              Standard Setu · generated {new Date(report.generated_at).toLocaleString()}
            </div>
          </div>

          {/* Requirement */}
          <Section title="REQUIREMENT">
            <p style={{ fontSize: 15, color: ink, fontStyle: "italic" }}>{report.query}</p>
          </Section>

          {/* Recommended standard + match */}
          {s && (
            <Section title="RECOMMENDED STANDARD">
              <div style={{ fontSize: 22, fontFamily: serif, color: brass }}>{s.is_number}</div>
              <div style={{ fontSize: 14.5, color: ink }}>{s.title}</div>
              <div style={{ fontSize: 12.5, color: "#6b6650", fontFamily: sans, marginTop: 2 }}>
                Edition: {s.latest_version || "unknown"}{s.amendment ? ` · ${s.amendment}` : ""} · Category: {s.category}
              </div>
            </Section>
          )}

          {report.match && (
            <Section title="MATCH SCORE">
              <div style={{ fontSize: 26, fontFamily: sans, fontWeight: 600, color: ink }}>
                {report.match.score} <span style={{ fontSize: 14, fontWeight: 400, color: "#8b8570" }}>/ 100</span>
                <span style={{ fontSize: 12, marginLeft: 10, color: "#8b8570", fontWeight: 400 }}>Confidence: {report.match.confidence}</span>
              </div>
              <div className="mt-2">
                {report.match.factors.map((f) => (
                  <div key={f.label} className="flex items-center gap-2 mb-1">
                    <span style={{ fontSize: 12.5, color: "#42402f", width: 170, fontFamily: sans }}>{f.label}</span>
                    <div style={{ flex: 1, height: 6, background: paperDeep, borderRadius: 3 }}>
                      <div style={{ height: 6, width: `${f.value}%`, background: brass, borderRadius: 3 }} />
                    </div>
                    <span style={{ fontSize: 12, color: "#6b6650", width: 40, textAlign: "right", fontFamily: sans }}>{f.value}%</span>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Compliance */}
          {s && (
            <Section title="CERTIFICATION">
              <span style={{ fontSize: 14, color: s.certification.mandatory ? seal : good, fontFamily: sans, fontWeight: 600 }}>
                {s.certification.mandatory ? "Mandatory" : "Not mandatory"}
              </span>
              {s.certification.scheme && (
                <span style={{ fontSize: 13, color: "#5c5843", fontFamily: sans }}> — {s.certification.scheme}</span>
              )}
              {s.certification.note && <p style={{ fontSize: 12.5, color: "#6b6650", marginTop: 4 }}>{s.certification.note}</p>}
            </Section>
          )}

          {/* Evidence */}
          {report.evidence.length > 0 && (
            <Section title="SUPPORTING EVIDENCE">
              <div className="flex flex-col gap-2">
                {report.evidence.map((c, i) => (
                  <div key={i} style={{ fontSize: 13, color: "#42402f" }}>
                    {c.kind === "certification" ? "\u26A0" : "\u2713"} {c.claim}
                    <span style={{ color: brass, fontFamily: serif, marginLeft: 8 }}>
                      {c.evidence.available
                        ? `— ${c.evidence.clause ? `Clause ${c.evidence.clause}` : "Source"}${c.evidence.page !== null ? `, p.${c.evidence.page}` : ""}`
                        : "— clause/page not indexed"}
                    </span>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Allied */}
          {report.allied.length > 0 && (
            <Section title="ALLIED STANDARDS">
              {report.allied.map((a) => (
                <div key={a.code} style={{ fontSize: 13, color: "#42402f", marginBottom: 3 }}>
                  <span style={{ fontFamily: serif, color: brass }}>{a.code}</span> — {a.title}
                  <span style={{ fontSize: 12, color: "#8b8570", fontFamily: sans }}> ({a.purpose})</span>
                </div>
              ))}
            </Section>
          )}

          {/* Risks */}
          {report.risk_notes.length > 0 && (
            <Section title="RISKS & CAUTIONS">
              {report.risk_notes.map((r, i) => (
                <div key={i} style={{ fontSize: 13, color: seal, marginBottom: 4 }}>
                  {"\u26A0"} {r}
                </div>
              ))}
            </Section>
          )}

          {/* Tender spec */}
          {report.tender_block && (
            <Section title="TENDER SPECIFICATION">
              <p style={{ fontSize: 13.5, color: ink, lineHeight: 1.6, border: `1px solid ${line}`, borderRadius: 4, padding: 12, background: "rgba(255,255,255,0.6)" }}>
                {report.tender_block}
              </p>
            </Section>
          )}

          {/* Sources */}
          {report.sources.length > 0 && (
            <Section title="SOURCES">
              {report.sources.map((ev, i) => (
                <div key={i} style={{ fontSize: 12.5, color: "#6b6650", marginBottom: 3, fontFamily: sans }}>
                  {ev.standard}{ev.document ? ` · ${ev.document}` : ""}
                  {ev.available ? ` · p.${ev.page}` : " · clause/page not indexed"}
                </div>
              ))}
              <p style={{ fontSize: 11, color: "#a5a08c", fontFamily: sans, marginTop: 6 }}>
                Verify current status on the BIS portal before citing in a tender.
              </p>
            </Section>
          )}
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 18 }}>
      <div style={{ fontSize: 10.5, color: "#8b8570", fontFamily: sans, letterSpacing: 1.5, marginBottom: 6, borderBottom: `1px solid ${line}`, paddingBottom: 3 }}>
        {title}
      </div>
      {children}
    </div>
  );
}
