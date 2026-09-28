"use client";

import { useState } from "react";
import { Copy } from "lucide-react";
import { line, ink, sans } from "./theme";

/** Copy-paste draft tender specification block. */
export default function SpecBlock({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div style={{ border: `1px solid ${line}`, borderRadius: 6, background: "rgba(255,255,255,0.6)" }}>
      <div className="flex items-center justify-between px-4 pt-3">
        <span style={{ fontSize: 11.5, color: "#8b8570", fontFamily: sans, letterSpacing: 0.3 }}>
          Draft wording for your tender
        </span>
        <button
          onClick={() => {
            navigator.clipboard?.writeText(text);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          }}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 5,
            fontSize: 12.5,
            color: "#a9722f",
            background: "none",
            border: "none",
            cursor: "pointer",
            fontFamily: sans,
          }}
        >
          <Copy size={13} /> {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <p style={{ fontSize: 14.5, color: ink, padding: "10px 16px 16px", lineHeight: 1.55 }}>{text}</p>
    </div>
  );
}
