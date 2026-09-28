"use client";

import * as React from "react";
import { ClipboardList, Search, FileSearch, ShieldCheck, FileText } from "lucide-react";
import { CircuitBoard } from "./CircuitBoard";
import { ink, sans, serif } from "./theme";

const STAGE_TEXTS = [
  "Reading your requirement…",
  "Matching against 130 Indian Standards…",
  "Resolving clause/page evidence…",
  "Checking certification requirements…",
  "Drafting tender wording…",
];

/**
 * Loading screen for recommend flows: the pipeline drawn as a live circuit.
 * Requirements pulse through Match -> Evidence -> Certify -> Specify.
 */
export default function CircuitLoader({ query }: { query?: string }) {
  const [tick, setTick] = React.useState(0);

  React.useEffect(() => {
    const id = setInterval(() => setTick((t) => (t + 1) % STAGE_TEXTS.length), 1600);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex flex-col items-center gap-6 py-6">
      {query && (
        <p style={{ fontSize: 15.5, color: ink, fontStyle: "italic", maxWidth: 640, textAlign: "center" }}>
          {query}
        </p>
      )}

      <CircuitBoard
        width={560}
        height={260}
        gridSize={22}
        pulseSpeed={1.8}
        nodes={[
          { id: "req", x: 55, y: 130, label: "Requirement", status: "active", icon: <ClipboardList size={15} /> },
          { id: "match", x: 200, y: 75, label: "Match", status: "processing", size: "md", icon: <Search size={14} /> },
          { id: "evid", x: 200, y: 185, label: "Evidence", status: "processing", size: "md", icon: <FileSearch size={14} /> },
          { id: "cert", x: 370, y: 130, label: "Certify", status: "active", size: "md", icon: <ShieldCheck size={15} /> },
          { id: "spec", x: 505, y: 130, label: "Specify", status: "active", icon: <FileText size={15} /> },
        ]}
        connections={[
          { from: "req", to: "match", animated: true },
          { from: "req", to: "evid", animated: true },
          { from: "match", to: "cert", animated: true },
          { from: "evid", to: "cert", animated: true },
          { from: "cert", to: "spec", animated: true, bidirectional: true },
        ]}
      />

      <div style={{ minHeight: 22, textAlign: "center" }}>
        <span key={tick} style={{ fontSize: 13.5, color: "#6b6650", fontFamily: sans }}>
          {STAGE_TEXTS[tick]}
        </span>
      </div>

      <div style={{ fontSize: 11, color: "#a5a08c", fontFamily: sans, letterSpacing: 1 }}>
        DISCOVER · VERIFY · ANALYZE · MONITOR
      </div>
    </div>
  );
}
