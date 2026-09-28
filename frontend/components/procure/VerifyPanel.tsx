"use client";

import { useState } from "react";
import { BadgeCheck, ShieldX, Clock, RefreshCw, ExternalLink, Stamp } from "lucide-react";
import { verifyLicence, type VerifyResponse } from "@/lib/api";
import { ink, paper, line, brass, good, seal, sans } from "./theme";

const STATUS_STYLE: Record<string, { color: string; label: string }> = {
  valid: { color: good, label: "VERIFIED ACTIVE" },
  invalid: { color: seal, label: "INVALID / CANCELLED" },
  expired: { color: seal, label: "VERIFIED EXPIRED" },
  not_found: { color: seal, label: "NOT FOUND (NOT CONCLUSIVE)" },
  unable_to_verify: { color: brass, label: "LOCATED — STATUS NEEDS MANUAL CHECK" },
  source_unavailable: { color: "#8b8570", label: "SOURCE UNAVAILABLE" },
};

/** Exact audit states (backend `state` field) for the secondary badge. */
const STATE_LABEL: Record<string, string> = {
  INVALID_FORMAT: "Invalid format",
  NOT_FOUND: "Not found in automated lookup",
  SOURCE_UNAVAILABLE: "Portal unreachable",
  SOURCE_LOCATED: "Licence seen on portal — active status not established",
  VERIFIED_ACTIVE: "Active",
  VERIFIED_EXPIRED: "Expired",
  VERIFIED_CANCELLED: "Cancelled",
  MANUAL_REVIEW_REQUIRED: "Manual review required",
};

/**
 * P0-3 — Supplier licence verification panel.
 * Never claims "Verified" unless a real verification happened; shows
 * "Last verified" timestamp and cache state on every result.
 */
export default function VerifyPanel() {
  const [licence, setLicence] = useState("");
  const [supplier, setSupplier] = useState("");
  const [isNumber, setIsNumber] = useState("");
  const [result, setResult] = useState<VerifyResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    if (!licence.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const r = await verifyLicence({
        licence_number: licence.trim(),
        supplier_name: supplier.trim(),
        is_number: isNumber.trim(),
      });
      setResult(r);
    } catch {
      setError("Verification request failed - is the backend running?");
    } finally {
      setLoading(false);
    }
  };

  const st = result ? STATUS_STYLE[result.status] || { color: brass, label: result.status } : null;

  return (
    <div>
      <div className="flex items-center gap-3" style={{ marginBottom: 6 }}>
        <span
          className="flex items-center justify-center rounded-full"
          style={{ width: 38, height: 38, background: ink, color: paper, border: `1px solid ${brass}66`, boxShadow: "0 4px 12px rgba(28,36,56,0.18)" }}
        >
          <Stamp size={16} />
        </span>
        <div>
          <h2 style={{ fontSize: 19, color: ink, margin: 0, fontWeight: 400 }}>Supplier verification</h2>
          <p style={{ fontSize: 10, color: brass, fontFamily: sans, margin: 0, letterSpacing: "0.16em", textTransform: "uppercase" }}>
            Live check · Manakonline portal
          </p>
        </div>
      </div>
      <p style={{ fontSize: 13, color: "#6b6650", marginBottom: 14, fontFamily: sans }}>
        Check a BIS manufacturing licence (format CM/L-XXXXXXXXXX) against the official
        BIS portal. Results are cached and timestamped - Standard Setu never claims a
        licence is valid without a real verification.
      </p>

      {/* How the verdict is produced — three steps, no black box */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 mb-4">
        {["Enter the licence", "Live check on the BIS portal", "Timestamped verdict + source"].map((step, i) => (
          <span key={step} className="inline-flex items-center gap-2">
            <span
              className="flex items-center justify-center rounded-full"
              style={{ width: 20, height: 20, border: `1px solid ${brass}`, color: brass, fontSize: 10.5, fontFamily: sans, fontWeight: 600 }}
            >
              {i + 1}
            </span>
            <span style={{ fontSize: 11.5, color: "#6b6650", fontFamily: sans }}>{step}</span>
          </span>
        ))}
      </div>

      <div className="grid gap-3 mb-4" style={{ gridTemplateColumns: "1fr 1fr" }}>
        <div>
          <label style={{ fontSize: 11.5, color: "#8b8570", fontFamily: sans }}>BIS LICENCE NUMBER *</label>
          <input
            value={licence}
            onChange={(e) => setLicence(e.target.value)}
            placeholder="CM/L-8700123456"
            style={inputStyle}
          />
        </div>
        <div>
          <label style={{ fontSize: 11.5, color: "#8b8570", fontFamily: sans }}>SUPPLIER / COMPANY</label>
          <input
            value={supplier}
            onChange={(e) => setSupplier(e.target.value)}
            placeholder="ABC Steel Pvt. Ltd."
            style={inputStyle}
          />
        </div>
        <div>
          <label style={{ fontSize: 11.5, color: "#8b8570", fontFamily: sans }}>RELEVANT IS STANDARD</label>
          <input
            value={isNumber}
            onChange={(e) => setIsNumber(e.target.value)}
            placeholder="IS 1786"
            style={inputStyle}
          />
        </div>
      </div>

      {!result && !loading && (
        <button
          onClick={() => setLicence("CM/L-8700123456")}
          style={{
            marginLeft: 10,
            fontSize: 12,
            color: brass,
            background: "none",
            border: `1px dashed ${brass}88`,
            borderRadius: 20,
            padding: "5px 12px",
            cursor: "pointer",
            fontFamily: sans,
          }}
        >
          Try a sample licence
        </button>
      )}

      <button
        onClick={run}
        disabled={!licence.trim() || loading}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          background: licence.trim() && !loading ? ink : "#b8b39d",
          color: paper,
          border: "none",
          borderRadius: 4,
          padding: "10px 18px",
          fontSize: 14,
          cursor: licence.trim() && !loading ? "pointer" : "not-allowed",
          fontFamily: sans,
        }}
      >
        {loading ? <RefreshCw size={15} className="animate-spin" /> : <BadgeCheck size={15} />}
        Verify licence
      </button>

      {error && (
        <div style={{ border: `1px solid ${seal}`, borderRadius: 6, background: "#f3e6e2" }} className="p-4 mt-4">
          <p style={{ fontSize: 13.5, color: seal, fontFamily: sans }}>{error}</p>
        </div>
      )}

      {/* Empty state — what the verdict will look like, honestly blank */}
      {!result && !loading && (
        <div
          className="mt-5 p-6 text-center"
          style={{ border: `1px dashed ${line}`, borderRadius: 8, background: "rgba(255,255,255,0.35)" }}
        >
          <Stamp size={22} style={{ color: "#b8b39d", margin: "0 auto 8px" }} />
          <p style={{ fontSize: 14.5, color: "#6b6650", fontFamily: "Georgia, serif", fontStyle: "italic", margin: "0 0 6px" }}>
            The verdict gets stamped here
          </p>
          <p style={{ fontSize: 12, color: "#8b8570", fontFamily: sans, margin: 0, maxWidth: 420, marginInline: "auto", lineHeight: 1.55 }}>
            Supplier, licence, product variety and validity — each field filled only when
            the BIS portal answers for it. Anything unverified stays visibly unverified.
          </p>
        </div>
      )}

      {result && st && (
        <div style={{ border: `1px solid ${line}`, borderRadius: 6, background: "rgba(255,255,255,0.6)" }} className="p-5 mt-5">
          <div className="flex items-center justify-between flex-wrap gap-2 mb-4">
            <div className="flex items-center gap-2">
              {result.status === "valid" ? (
                <BadgeCheck size={18} style={{ color: good }} />
              ) : (
                <ShieldX size={18} style={{ color: st.color }} />
              )}
              <span style={{ fontSize: 16, color: st.color, fontFamily: sans, fontWeight: 600 }}>{st.label}</span>
              {result.state && STATE_LABEL[result.state] && (
                <span style={{ fontSize: 10.5, color: "#6b6650", border: `1px solid ${line}`, borderRadius: 20, padding: "1px 8px", fontFamily: sans }}>
                  {STATE_LABEL[result.state]}
                </span>
              )}
              {result.cached && (
                <span style={{ fontSize: 11, color: "#8b8570", border: `1px solid ${line}`, borderRadius: 20, padding: "1px 8px", fontFamily: sans }}>
                  cached
                </span>
              )}
            </div>
            <a
              href={result.source_url}
              target="_blank"
              rel="noreferrer"
              style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 12, color: brass, fontFamily: sans, textDecoration: "none" }}
            >
              Official BIS portal <ExternalLink size={11} />
            </a>
          </div>

          <div style={{ borderTop: `1px solid ${line}` }}>
            {([
              ["Supplier", result.supplier_name],
              ["Licence", result.licence_number],
              ["IS standard", result.is_number],
              ["Product / variety", result.product],
              ["Validity", result.validity],
            ] as [string, string][])
              .filter(([, v]) => v)
              .map(([k, v], i, arr) => (
                <div key={k} className="flex" style={{ borderTop: i === 0 ? "none" : `1px solid ${line}` }}>
                  <div style={{ width: "40%", fontSize: 12.5, color: "#8b8570", fontFamily: sans, padding: "8px 0", background: "transparent" }}>{k}</div>
                  <div style={{ fontSize: 13.5, color: ink, padding: "8px 0" }}>{v}</div>
                </div>
              ))}
          </div>

          <p style={{ fontSize: 13, color: "#5c5843", marginTop: 12, lineHeight: 1.5 }}>{result.detail}</p>

          <div className="flex items-center gap-2 mt-4" style={{ fontSize: 12, color: "#8b8570", fontFamily: sans }}>
            <Clock size={12} />
            Last verified: {result.last_verified ? new Date(result.last_verified).toLocaleString() : "-"}
            {" · "}Source: {result.source}
          </div>

          {/* Honesty boundary (audit item 8): state plainly what this automated
              check can and cannot establish. */}
          <p style={{ fontSize: 11, color: "#8b8570", fontFamily: sans, marginTop: 8, lineHeight: 1.5 }}>
            This automated check can confirm the licence number's format and whether it appears
            on the BIS portal. It cannot establish active/expired/cancelled status, licensee or
            product scope — those require the interactive portal or a manual check.
          </p>
        </div>
      )}
    </div>
  );
}

const inputStyle = {
  width: "100%",
  border: "1px solid #c9c3ab",
  borderRadius: 4,
  background: "rgba(255,255,255,0.5)",
  padding: "9px 12px",
  fontSize: 14,
  color: "#1c2438",
  marginTop: 4,
  fontFamily: "Helvetica, Arial, sans-serif",
} as const;
