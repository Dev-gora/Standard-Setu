"use client";

import { ExternalLink } from "lucide-react";
import type { EvidenceRef } from "@/lib/api";
import { line, brass, sans, good } from "./theme";

/**
 * P0-2 — One structured citation row. Shows page/clause only when the offline
 * index actually resolved them; otherwise the honest
 * "Source available - clause/page not indexed" (or the unindexed-document
 * state). Never invents a citation.
 */
export function EvidenceRow({ ev }: { ev: EvidenceRef }) {
  return (
    <div className="flex items-start gap-2">
      <div className="min-w-0 flex-1">
        {ev.available ? (
          <div style={{ fontSize: 13, color: "#42402f" }}>
            {ev.clause && (
              <span style={{ fontFamily: "Georgia, serif", color: "#a9722f" }}>
                Clause {ev.clause}
                {ev.page !== null ? ", " : ""}
              </span>
            )}
            {ev.page !== null && (
              <span style={{ fontFamily: "Georgia, serif", color: "#a9722f" }}>
                {ev.clause ? "" : "Page "}
                p.{ev.page}
              </span>
            )}
            {ev.evidence && (
              <span style={{ fontSize: 12.5, color: "#6b6650" }}> — {ev.evidence}</span>
            )}
          </div>
        ) : (
          <div style={{ fontSize: 12.5, color: "#8b8570", fontFamily: sans }}>
            {ev.unavailable_reason === "source_document_not_indexed"
              ? "Source document not indexed - citation unavailable"
              : "Source available - clause/page not indexed"}
          </div>
        )}
      </div>
      {ev.url && (
        <a
          href={ev.url}
          target="_blank"
          rel="noreferrer"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            fontSize: 11.5,
            color: brass,
            fontFamily: sans,
            textDecoration: "none",
            flexShrink: 0,
          }}
        >
          {ev.available ? "View source" : "Find document"} <ExternalLink size={11} />
        </a>
      )}
    </div>
  );
}

/**
 * P0-2 — Claim + citation pair ("Why was this standard recommended?").
 */
export default function EvidenceList({ claims }: { claims: { claim: string; kind: string; evidence: EvidenceRef }[] }) {
  return (
    <div style={{ border: `1px solid ${line}`, borderRadius: 6, background: "rgba(255,255,255,0.5)" }} className="p-4">
      <div style={{ fontSize: 11.5, color: "#8b8570", fontFamily: sans, marginBottom: 10 }}>
        WHY WAS THIS RECOMMENDED? — each reason links to its source
      </div>
      <div className="flex flex-col gap-3">
        {claims.map((c, i) => (
          <div key={i}>
            <div style={{ fontSize: 13.5, color: "#42402f", marginBottom: 3 }}>
              {c.kind === "certification" ? "\u26A0" : "\u2713"} {c.claim}
            </div>
            <div className="pl-4">
              <EvidenceRow ev={c.evidence} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
