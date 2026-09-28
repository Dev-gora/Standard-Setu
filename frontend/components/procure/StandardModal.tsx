"use client";

import { useEffect, useState } from "react";
import { X, ExternalLink } from "lucide-react";
import { getRegistryStandard, type RegistryStandard } from "@/lib/api";
import { paper, line, ink, brass, sans, serif } from "./theme";

/**
 * Standard detail modal — metadata now comes from the backend registry
 * (version, amendment, certification) instead of the POC's hardcoded table.
 */
export default function StandardModal({ code, onClose }: { code: string; onClose: () => void }) {
  const [info, setInfo] = useState<RegistryStandard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setInfo(null);
    setError(null);
    getRegistryStandard(code)
      .then((d) => !cancelled && setInfo(d))
      .catch(() => !cancelled && setError("Could not load details for this standard."));
    return () => {
      cancelled = true;
    };
  }, [code]);

  const params: [string, string][] = info
    ? [
        ...(info.latest_version ? [["Latest version", info.latest_version] as [string, string]] : []),
        ...(info.amendment ? [["Amendment / status", info.amendment] as [string, string]] : []),
        ["Certification", info.certification.mandatory ? `Mandatory — ${info.certification.scheme}` : info.certification.scheme || "Not mandatory"],
      ]
    : [];

  return (
    <div
      onClick={onClose}
      style={{ position: "fixed", inset: 0, background: "rgba(28,36,56,0.45)", zIndex: 50, display: "flex", alignItems: "flex-end", justifyContent: "center" }}
      className="md:items-center"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ background: paper, border: `1px solid ${line}`, borderRadius: 8, maxWidth: 480, width: "92%", maxHeight: "80vh", overflowY: "auto" }}
        className="p-6 mb-4 md:mb-0"
      >
        <div className="flex items-start justify-between mb-3">
          <div style={{ fontFamily: serif, fontSize: 20, color: ink }}>{code}</div>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "#8b8570" }} aria-label="Close">
            <X size={18} />
          </button>
        </div>

        {error && <p style={{ fontSize: 14, color: "#8a3324", fontFamily: sans }}>{error}</p>}

        {!info && !error && (
          <p style={{ fontSize: 14, color: "#6b6650", fontFamily: sans }}>Loading standard details…</p>
        )}

        {info && (
          <>
            <p style={{ fontSize: 14, color: "#42402f", marginBottom: 6, lineHeight: 1.5 }}>{info.title}</p>
            <p style={{ fontSize: 13.5, color: "#5c5843", marginBottom: 14, lineHeight: 1.5 }}>{info.scope_description}</p>

            {params.length > 0 && (
              <div style={{ border: `1px solid ${line}`, borderRadius: 6, overflow: "hidden", marginBottom: 14 }}>
                {params.map(([k, v], i) => (
                  <div key={k} className="flex" style={{ borderTop: i === 0 ? "none" : `1px solid ${line}` }}>
                    <div style={{ width: "42%", fontSize: 12.5, color: "#8b8570", fontFamily: sans, padding: "8px 12px", background: "rgba(0,0,0,0.02)" }}>{k}</div>
                    <div style={{ fontSize: 13, color: ink, padding: "8px 12px" }}>{v}</div>
                  </div>
                ))}
              </div>
            )}

            <a
              href={info.archive_link?.url || "#"}
              target="_blank"
              rel="noreferrer"
              style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 13, color: brass, fontFamily: sans, textDecoration: "none" }}
            >
              Open the document <ExternalLink size={13} />
            </a>
            <p style={{ fontSize: 11, color: "#a5a08c", marginTop: 10, fontFamily: sans }}>
              Opens the standard on the Internet Archive's public mirror of Indian Standards. Summary above is from the
              curated registry — always verify current status on the BIS portal before citing in a tender.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
