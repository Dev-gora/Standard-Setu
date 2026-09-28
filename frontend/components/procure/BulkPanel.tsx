"use client";

import { useEffect, useRef, useState } from "react";
import {
  Search, CheckCircle2, AlertTriangle, ChevronDown,
  ChevronRight, FolderUp, X, TrendingUp, FileWarning,
} from "lucide-react";
import { procureBulkCheck, type BulkCheckResponse } from "@/lib/api";
import { setUnsavedSessionData } from "@/lib/session";
import CircuitLoader from "./CircuitLoader";
import RiskPanel from "./RiskPanel";
import { ink, paper, paperDeep, line, brass, good, seal, sans } from "./theme";

const MAX_FILES = 500;

/** Bulk mode — upload up to 50 tender PDFs, checked against the registry. */
export default function BulkPanel({ onBack }: { onBack: () => void }) {
  const [files, setFiles] = useState<File[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [stage, setStage] = useState<"collect" | "loading" | "done">("collect");
  const [results, setResults] = useState<BulkCheckResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [onlyPass, setOnlyPass] = useState(false);
  const [expanded, setExpanded] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Session-data-loss guard: uploaded files / batch results live only in this
  // tab's memory. Track their presence so the beforeunload warning in
  // lib/session.ts fires ONLY while temporary data actually exists (a normal
  // search or an explicitly cleared session never triggers it). The panel's
  // state dies with it, so leaving bulk mode clears the flag too.
  useEffect(() => {
    setUnsavedSessionData(files.length > 0 || stage === "done");
    return () => setUnsavedSessionData(false);
  }, [files.length, stage]);

  const addFiles = (list: FileList | null) => {
    if (!list) return;
    const incoming = Array.from(list).filter(
      (f) => f.name.toLowerCase().endsWith(".pdf") || f.type === "application/pdf"
    );
    setFiles((prev) => [...prev, ...incoming].slice(0, MAX_FILES));
  };

  const removeFile = (idx: number) => setFiles((prev) => prev.filter((_, i) => i !== idx));

  const analyze = async () => {
    if (!files.length) return;
    setStage("loading");
    setError(null);
    try {
      const data = await procureBulkCheck(files);
      setResults(data);
      setStage("done");
    } catch {
      setError("The check failed — make sure the backend is running, then try again.");
      setStage("collect");
    }
  };

  const reset = () => {
    setFiles([]);
    setResults(null);
    setError(null);
    setStage("collect");
  };

  if (stage === "done" && results) {
    const visible = onlyPass ? results.files.filter((r) => r.status === "pass") : results.files;
    return (
      <div>
        <button onClick={reset} style={{ fontSize: 12.5, color: "#8b8570", background: "none", border: "none", cursor: "pointer", marginBottom: 16, fontFamily: sans }}>
          ← Check more tenders
        </button>

        <div style={{ border: `1px solid ${line}`, borderRadius: 6, background: "rgba(255,255,255,0.5)" }} className="p-5 mb-6">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle2 size={17} style={{ color: good }} />
            <span style={{ fontSize: 15, color: ink }}>
              {results.passing} of {results.total} tenders meet the checked quality requirements
            </span>
          </div>
          {results.min_standards.length > 0 && (
            <p style={{ fontSize: 13, color: "#6b6650", fontFamily: sans }}>
              Minimum set of standards covering every compliant item:{" "}
              {results.min_standards.map((c, i) => (
                <span key={c}>
                  <span style={{ color: "#a9722f", fontFamily: "Georgia, serif" }}>{c}</span>
                  {i < results.min_standards.length - 1 ? ", " : ""}
                </span>
              ))}
            </p>
          )}
        </div>

        {results.risk && results.risk.files.length > 0 && (
          <RiskPanel risk={results.risk} />
        )}

        {/* Demand vs availability rating across the batch */}
        {(results.demand_rating?.length || 0) > 0 && (
          <div style={{ border: `1px solid ${line}`, borderRadius: 6, background: "rgba(255,255,255,0.5)" }} className="p-5 mb-6">
            <div className="mb-1 flex items-center gap-2">
              <TrendingUp size={16} style={{ color: brass }} />
              <span style={{ fontSize: 14.5, color: ink, fontFamily: sans, fontWeight: 600 }}>
                Demand vs availability rating
              </span>
            </div>
            <p style={{ fontSize: 12, color: "#8b8570", fontFamily: sans, marginBottom: 12 }}>
              Tender demand = the number of uploaded tenders citing the standard ·
              tender share = the percentage of uploaded tenders citing it ·
              level = relative frequency within this uploaded batch.
              Availability is inferred only from certification/QCO provenance signals —
              it is not a supplier-count or market statistic.
            </p>
            <div style={{ overflowX: "auto" }}>
              <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 12.5 }}>
                <thead>
                  <tr>
                    {["Standard", "Tender demand", "Tender share", "Level", "Certification", "Availability"].map((h) => (
                      <th key={h} style={{ textAlign: "left", padding: "6px 8px", borderBottom: `2px solid ${ink}`, color: "#8b8570", fontFamily: sans, fontWeight: 500, whiteSpace: "nowrap" }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {results.demand_rating!.map((d) => {
                    const levelColor = d.demand_level === "HIGH" ? seal : d.demand_level === "MEDIUM" ? brass : "#8b8570";
                    return (
                      <tr key={d.standard}>
                        <td style={{ padding: "7px 8px", borderBottom: `1px solid ${line}` }}>
                          <span style={{ fontFamily: "Georgia, serif", color: "#a9722f" }}>{d.standard}</span>
                          {d.title && <div style={{ fontSize: 11, color: "#8b8570", fontFamily: sans }}>{d.title.slice(0, 52)}</div>}
                        </td>
                        <td style={{ padding: "7px 8px", borderBottom: `1px solid ${line}`, fontFamily: sans, color: ink, whiteSpace: "nowrap" }}>
                          {d.demanded_by} tender{d.demanded_by > 1 ? "s" : ""}
                        </td>
                        <td style={{ padding: "7px 8px", borderBottom: `1px solid ${line}`, fontFamily: sans, color: ink }}>
                          {d.share_pct}%
                        </td>
                        <td style={{ padding: "7px 8px", borderBottom: `1px solid ${line}` }}>
                          <span style={{
                            fontSize: 10.5, fontWeight: 700, fontFamily: sans, letterSpacing: "0.06em",
                            color: levelColor, border: `1px solid ${levelColor}55`, borderRadius: 10, padding: "1px 8px",
                          }}>
                            {d.demand_level}
                          </span>
                        </td>
                        <td style={{ padding: "7px 8px", borderBottom: `1px solid ${line}`, fontFamily: sans, fontSize: 11.5 }}>
                          {d.verified_mandatory ? (
                            <span style={{ color: seal }}>Mandatory (QCO-backed)</span>
                          ) : d.certification_status === "MANUAL_REVIEW_REQUIRED" ? (
                            <span style={{ color: "#8b8570" }}>Mandatory per registry — unverified</span>
                          ) : (
                            <span style={{ color: good }}>Not mandatory</span>
                          )}
                        </td>
                        <td style={{ padding: "7px 8px", borderBottom: `1px solid ${line}`, fontFamily: sans, fontSize: 11.5, color: "#4a4636", minWidth: 200 }}>
                          {d.availability_note}
                          <span style={{ color: "#a5a08c" }}> · confidence {d.availability_confidence}</span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p style={{ fontSize: 11, color: "#a5a08c", fontFamily: sans, marginTop: 10 }}>
              Based on the uploaded tender batch; not external market-demand data.
              Low tender demand does not imply low supplier availability.
            </p>
          </div>
        )}

        {/* Batch-level findings — issues that could NOT be tied to any
            standard. Shown separately so per-standard views stay honest
            instead of pinning them to the first cited code. */}
        {(results.batch_issues?.length || 0) > 0 && (
          <div style={{ border: `1px dashed ${brass}`, borderRadius: 6, background: "rgba(246,236,218,0.55)" }} className="p-5 mb-6">
            <div className="mb-1 flex items-center gap-2">
              <FileWarning size={16} style={{ color: brass }} />
              <span style={{ fontSize: 14.5, color: ink, fontFamily: sans, fontWeight: 600 }}>
                Batch-level findings
              </span>
            </div>
            <p style={{ fontSize: 12, color: "#8b8570", fontFamily: sans, marginBottom: 12 }}>
              Issues that concern the documents themselves rather than any cited standard.
            </p>
            <div className="flex flex-col gap-3">
              {results.batch_issues!.map((b) => (
                <div key={b.kind} style={{ fontSize: 12.5, color: "#4a4636", fontFamily: sans }}>
                  <span style={{ fontWeight: 600, color: ink }}>
                    {b.count} document{b.count > 1 ? "s" : ""}:
                  </span>{" "}
                  {b.detail}
                  <div style={{ marginTop: 4, color: "#8b8570", fontSize: 11.5 }}>
                    {b.files.map((f, i) => (
                      <span key={f + i}>{f}{i < b.files.length - 1 ? ", " : ""}</span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <label className="flex items-center gap-2 mb-4" style={{ fontSize: 13, color: "#6b6650", fontFamily: sans }}>
          <input type="checkbox" checked={onlyPass} onChange={(e) => setOnlyPass(e.target.checked)} />
          Show only items that pass
        </label>

        <div style={{ borderTop: `1px solid ${ink}` }}>
          {visible.map((r, i) => {
            const pass = r.status === "pass";
            const errored = r.status === "error";
            return (
              <div key={r.file_name + i} style={{ borderBottom: `1px solid ${line}` }} className="py-3">
                <button
                  onClick={() => setExpanded(expanded === i ? null : i)}
                  className="w-full flex items-center justify-between gap-3"
                  style={{ background: "none", border: "none", cursor: "pointer", padding: 0, textAlign: "left" }}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    {pass ? (
                      <CheckCircle2 size={15} style={{ color: good, flexShrink: 0 }} />
                    ) : errored ? (
                      <X size={15} style={{ color: "#8b8570", flexShrink: 0 }} />
                    ) : (
                      <AlertTriangle size={15} style={{ color: seal, flexShrink: 0 }} />
                    )}
                    <span style={{ fontSize: 13.5, color: ink, fontFamily: sans, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {r.file_name}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <span style={{ fontSize: 12.5, color: "#6b6650", fontFamily: sans }}>{r.product_label || r.status}</span>
                    {expanded === i ? <ChevronDown size={14} style={{ color: "#8b8570" }} /> : <ChevronRight size={14} style={{ color: "#8b8570" }} />}
                  </div>
                </button>
                {expanded === i && (
                  <div className="mt-3 pl-6 flex flex-col gap-2">
                    {r.standards_cited.length > 0 && (
                      <div style={{ fontSize: 13.5 }}>
                        Standards cited:{" "}
                        {r.standards_cited.map((c, j) => (
                          <span key={c}>
                            <span style={{ fontFamily: "Georgia, serif", color: "#a9722f" }}>{c}</span>
                            {j < r.standards_cited.length - 1 ? ", " : ""}
                          </span>
                        ))}
                      </div>
                    )}
                    {r.note && <div style={{ fontSize: 13, color: pass ? good : "#6b6650", fontFamily: sans }}>{r.note}</div>}
                    {r.ocr && (r.ocr.attempted || r.ocr.used) && (
                      <div style={{ fontSize: 12.5, color: r.ocr.used ? good : "#8b8570", fontFamily: sans }}>
                        {r.ocr.used
                          ? `OCR used - ${r.ocr.pages} page(s) processed${r.ocr.confidence !== null ? `, confidence ${r.ocr.confidence}%` : ""}${r.ocr.confidence !== null && r.ocr.confidence < 60 ? " - low confidence, manual review recommended" : ""}`
                          : `Scanned document detected - ${r.ocr.message || "OCR unavailable on server"}`}
                      </div>
                    )}
                    {r.issues.map((iss, k) => (
                      <div key={k} style={{ fontSize: 12.5, color: seal, fontFamily: sans }}>
                        • {iss.detail}
                        {iss.standard && !iss.batch_level && (
                          <span
                            style={{
                              marginLeft: 8, fontSize: 10.5, letterSpacing: "0.05em",
                              color: brass, border: `1px solid ${brass}55`,
                              borderRadius: 10, padding: "1px 8px", whiteSpace: "nowrap",
                              fontFamily: "Georgia, serif",
                            }}
                          >
                            {iss.standard}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  if (stage === "loading") {
    return (
      <CircuitLoader
        query={`Checking ${files.length} document${files.length === 1 ? "" : "s"} against Indian Standards…`}
      />
    );
  }

  return (
    <div>
      <button onClick={onBack} style={{ fontSize: 12.5, color: "#8b8570", background: "none", border: "none", cursor: "pointer", marginBottom: 16, fontFamily: sans }}>
        ← Back
      </button>
      <h1 style={{ fontSize: 22, color: ink, marginBottom: 6, fontWeight: 400 }}>Check multiple tenders at once</h1>
      <p style={{ fontSize: 14, color: "#6b6650", marginBottom: 18, fontFamily: sans }}>
        Upload up to 500 tender or product-specification PDFs. Each is checked for the standards it cites — unknown
        codes, outdated editions, and missing mandatory-certification language.
      </p>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => { e.preventDefault(); setDragOver(false); addFiles(e.dataTransfer.files); }}
        style={{
          border: `1.5px dashed ${dragOver ? "#a9722f" : line}`,
          borderRadius: 6,
          background: dragOver ? "rgba(169,114,47,0.06)" : "rgba(255,255,255,0.4)",
        }}
        className="flex flex-col items-center justify-center gap-2 py-12 mb-4"
      >
        <FolderUp size={22} style={{ color: brass }} />
        <span style={{ fontSize: 13.5, color: "#6b6650", fontFamily: sans }}>Drag and drop files here, or</span>
        <button
          onClick={() => inputRef.current?.click()}
          style={{ fontSize: 13, color: seal, background: "none", border: "none", textDecoration: "underline", cursor: "pointer", fontFamily: sans }}
        >
          browse your computer
        </button>
        <span style={{ fontSize: 11.5, color: "#a5a08c", fontFamily: sans }}>Up to 500 files · PDF · 10 MB each</span>
        <p style={{ fontSize: 11.5, color: "#8b8570", fontFamily: sans, marginTop: 8 }}>
          Uploaded tender data is temporary and may be lost when this session ends.
        </p>
        <input ref={inputRef} type="file" multiple hidden accept=".pdf,application/pdf" onChange={(e) => addFiles(e.target.files)} />
      </div>

      {error && (
        <div style={{ border: `1px solid ${seal}`, borderRadius: 6, background: "#f3e6e2" }} className="p-4 mb-4">
          <p style={{ fontSize: 13.5, color: seal, fontFamily: sans }}>{error}</p>
        </div>
      )}

      {files.length > 0 && (
        <div style={{ border: `1px solid ${line}`, borderRadius: 6, background: "rgba(255,255,255,0.5)" }} className="mb-4">
          <div className="flex items-center justify-between px-4 py-2.5" style={{ borderBottom: `1px solid ${line}` }}>
            <span style={{ fontSize: 12.5, color: "#6b6650", fontFamily: sans }}>
              {files.length} file{files.length > 1 ? "s" : ""} added {files.length >= MAX_FILES ? "(limit reached)" : ""}
            </span>
            <button onClick={() => setFiles([])} style={{ fontSize: 12, color: seal, background: "none", border: "none", cursor: "pointer", fontFamily: sans }}>
              Clear all
            </button>
          </div>
          <div style={{ maxHeight: 220, overflowY: "auto" }}>
            {files.map((f, i) => (
              <div key={f.name + i} className="flex items-center justify-between px-4 py-2" style={{ borderTop: i === 0 ? "none" : `1px solid ${paperDeep}` }}>
                <span style={{ fontSize: 13, color: ink, fontFamily: sans, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.name}</span>
                <button onClick={() => removeFile(i)} style={{ background: "none", border: "none", cursor: "pointer", color: "#8b8570", flexShrink: 0 }} aria-label={`Remove ${f.name}`}>
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <button
        disabled={files.length === 0}
        onClick={analyze}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          background: files.length ? ink : "#b8b39d",
          color: paper,
          border: "none",
          borderRadius: 4,
          padding: "10px 18px",
          fontSize: 14,
          cursor: files.length ? "pointer" : "not-allowed",
          fontFamily: sans,
        }}
      >
        <Search size={15} /> Check {files.length || ""} tender{files.length === 1 ? "" : "s"}
      </button>
    </div>
  );
}
