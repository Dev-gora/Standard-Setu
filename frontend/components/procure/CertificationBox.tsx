"use client";

import { ShieldCheck, ShieldAlert, ShieldQuestion, ExternalLink } from "lucide-react";
import type { CertificationInfo } from "@/lib/api";
import { seal, good, sans } from "./theme";

/**
 * Provenance-honest certification box (audit items 4/12):
 *  - VERIFIED (QCO-backed): firm wording + the QCO/notification + source link.
 *  - MANUAL_REVIEW_REQUIRED: curated claim, no government proof — says so.
 *  - otherwise: neutral wording, no claim of authority.
 */
export default function CertificationBox({ certification }: { certification: CertificationInfo }) {
  const mandatory = certification.mandatory;
  const status = certification.verification_status || "UNVERIFIED";
  const verified = status === "VERIFIED";
  const needsReview = mandatory && !verified;

  const accent = needsReview ? "#8b8570" : mandatory ? seal : good;
  const bg = needsReview ? "#efece0" : mandatory ? "#f3e6e2" : "#e9f1eb";
  const Icon = needsReview ? ShieldQuestion : mandatory ? ShieldAlert : ShieldCheck;

  const headline = needsReview
    ? "Listed as requiring certification — unverified"
    : mandatory
      ? verified
        ? "Certification is mandatory (QCO-backed)"
        : "Certification is mandatory"
      : "Certification is not mandatory";

  return (
    <div
      style={{
        border: `1px solid ${accent}`,
        background: bg,
        borderRadius: 6,
      }}
      className="p-4 flex gap-3"
    >
      <Icon size={20} style={{ color: accent, flexShrink: 0, marginTop: 1 }} />
      <div>
        <div style={{ fontSize: 14.5, color: accent, fontFamily: sans, fontWeight: 600 }}>
          {headline}
        </div>
        <div style={{ fontSize: 13, color: "#4a4636", marginTop: 2, fontFamily: sans }}>
          {certification.scheme || "BIS certification"}
        </div>
        {verified && certification.basis && (
          <p style={{ fontSize: 13, color: "#5c5843", marginTop: 6, fontFamily: sans }}>
            Backed by: {certification.basis}
          </p>
        )}
        {needsReview && (
          <p style={{ fontSize: 12.5, color: "#6b6650", marginTop: 6, fontFamily: sans, fontStyle: "italic" }}>
            Manual review required — no government notification for this requirement has been
            verified yet. Confirm on the BIS portal before relying on it.
          </p>
        )}
        {certification.note && !needsReview && (
          <p style={{ fontSize: 13.5, color: "#5c5843", marginTop: 6 }}>{certification.note}</p>
        )}
        {verified && certification.source_url && (
          <a
            href={certification.source_url}
            target="_blank"
            rel="noreferrer"
            style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 12, color: "#a9722f", fontFamily: sans, marginTop: 6, textDecoration: "none" }}
          >
            Official BIS source <ExternalLink size={11} />
          </a>
        )}
      </div>
    </div>
  );
}
