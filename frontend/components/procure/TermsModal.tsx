"use client";

import { ShieldCheck, FileText, RefreshCw } from "lucide-react";
import { ink, paper, line, brass, seal, good, sans, serif } from "./theme";

/**
 * Terms & Conditions gate (shown before the app is usable).
 * States the privacy model truthfully:
 *  - uploads/queries stay private, scoped to your browser session
 *  - everything except watchlist items is deleted when you close/refresh
 *  - the licence check contacts the official BIS portal
 */
export default function TermsModal({ onAccept }: { onAccept: () => void }) {
  return (
    <div
      style={{ position: "fixed", inset: 0, background: "rgba(28,36,56,0.55)", zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center" }}
      role="dialog"
      aria-modal="true"
      aria-label="Terms and Conditions"
    >
      <div
        style={{ background: paper, border: `1px solid ${line}`, borderRadius: 8, maxWidth: 520, width: "92%", maxHeight: "86vh", overflowY: "auto", boxShadow: "0 18px 50px rgba(28,36,56,0.35)" }}
        className="p-6"
      >
        <div className="flex items-center gap-2 mb-3">
          <FileText size={18} style={{ color: seal }} />
          <span style={{ fontSize: 11, color: "#8b8570", fontFamily: sans, letterSpacing: 1.5 }}>STANDARD SETU</span>
        </div>
        <h2 style={{ fontSize: 20, color: ink, fontWeight: 400, marginBottom: 12 }}>Terms &amp; Conditions</h2>

        <div className="flex flex-col gap-3" style={{ fontSize: 13.5, color: "#42402f", lineHeight: 1.55 }}>
          <p>
            <strong style={{ color: ink }}>Your uploads stay private.</strong> Tender documents,
            queries and verification details you provide are used only to produce your results.
            They are not shared, sold, or used to train any model.
          </p>
          <p>
            <strong style={{ color: ink }}>Everything is deleted when you leave.</strong> When you
            refresh or close this site, your session ends: uploaded files and activity history are
            erased automatically from the server.
            <span style={{ color: "#6b6650", fontSize: 12.5 }}> (Watchlist entries you deliberately
            save are kept — remove them anytime in the Monitor tab.)</span>
          </p>
          <p>
            <strong style={{ color: ink }}>What this tool is.</strong> Standard Setu is a decision-support
            assistant built on a curated registry of 130 Indian Standards. Match Scores are
            heuristics, not legal advice — always verify citations and certification status on
            the official BIS portal before using them in a tender.
          </p>
          <p>
            <strong style={{ color: ink }}>External lookups.</strong> Supplier licence verification
            sends your query to the official BIS portal (manakonline.in) to check the licence
            number you enter. No other data leaves this application.
          </p>
        </div>

        <div style={{ borderTop: `1px solid ${line}`, margin: "16px 0 14px" }} />

        <div className="flex items-start gap-2 mb-4" style={{ fontSize: 12, color: "#6b6650", fontFamily: sans }}>
          <ShieldCheck size={14} style={{ color: good, flexShrink: 0, marginTop: 1 }} />
          <span>
            Session id: anonymous random identifier — no accounts, no cookies for tracking,
            no personal information collected.
          </span>
        </div>

        <button
          onClick={onAccept}
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 8,
            background: ink,
            color: paper,
            border: "none",
            borderRadius: 4,
            padding: "12px 18px",
            fontSize: 14.5,
            cursor: "pointer",
            fontFamily: sans,
          }}
        >
          <RefreshCw size={14} /> I understand — continue
        </button>
        <p style={{ fontSize: 11, color: "#a5a08c", fontFamily: sans, marginTop: 10, textAlign: "center" }}>
          SIH26108 · Standard Setu — discover, verify, analyze, monitor
        </p>
      </div>
    </div>
  );
}
