"use client";

import { useState } from "react";
import { ThumbsUp, ThumbsDown, Clock, Star, FileText } from "lucide-react";
import type { ProcureRecommendation } from "@/lib/api";
import { addWatch } from "@/lib/api";
import CodeLink from "./CodeLink";
import CertificationBox from "./CertificationBox";
import SpecBlock from "./SpecBlock";
import MatchScore from "./MatchScore";
import EvidenceList from "./EvidenceList";
import { ink, line, brass, good, seal, sans } from "./theme";

/**
 * Result view — the POC's single-card layout, driven by real API data.
 * Standard card: cited standard + edition note, certification box,
 * copy-paste tender block, allied standards by purpose, feedback.
 */
export default function ResultView({
  data,
  onOpenStandard,
  onNewSearch,
  onOpenReport,
}: {
  data: ProcureRecommendation;
  onOpenStandard: (code: string) => void;
  onNewSearch: () => void;
  onOpenReport?: (code: string) => void;
}) {
  const [feedback, setFeedback] = useState<string | null>(null);
  const [watched, setWatched] = useState(false);
  const s = data.standard;

  const watch = async () => {
    try {
      await addWatch(s.is_number);
      setWatched(true);
    } catch {
      /* keep silent; the Monitor tab shows authoritative state */
    }
  };

  return (
    <div>
      <h2 style={{ fontSize: 21, color: ink, fontWeight: 400, marginBottom: 2 }}>{s.title}</h2>
      <p style={{ fontSize: 13.5, color: "#6b6650", fontFamily: sans, marginBottom: 18 }}>{data.reason}</p>

      <div className="flex items-start justify-between flex-wrap gap-3 mb-5 pb-5" style={{ borderBottom: `1px solid ${line}` }}>
        <div>
          <div style={{ fontSize: 11.5, color: "#8b8570", fontFamily: sans, marginBottom: 3 }}>STANDARD TO CITE</div>
          <div style={{ fontSize: 19 }}>
            <CodeLink code={s.is_number} onOpen={onOpenStandard} />
          </div>
          <div style={{ fontSize: 14, color: "#42402f", marginTop: 2 }}>{s.category}</div>
        </div>
        <div className="flex items-start gap-1.5" style={{ maxWidth: 240 }}>
          <Clock size={14} style={{ color: brass, marginTop: 2, flexShrink: 0 }} />
          <span style={{ fontSize: 12.5, color: "#6b6650", fontFamily: sans }}>
            {s.latest_version}
            {s.amendment ? ` — ${s.amendment}` : ""}
          </span>
        </div>
      </div>

      <MatchScore match={data.match} />

      {data.evidence && data.evidence.length > 0 && (
        <div className="mb-5">
          <EvidenceList claims={data.evidence} />
        </div>
      )}

      <div className="mb-5">
        <CertificationBox certification={s.certification} />
      </div>
      <div className="mb-6">
        <SpecBlock text={data.tender_block} />
      </div>

      {data.allied.length > 0 && (
        <div className="mb-6">
          <div style={{ fontSize: 11.5, color: "#8b8570", fontFamily: sans, marginBottom: 10 }}>
            ALSO WORTH REFERENCING — tap a code to read what it covers
          </div>
          <div className="flex flex-col gap-3">
            {data.allied.map((r) => (
              <div key={r.code} className="flex items-start gap-3">
                <div
                  style={{
                    fontSize: 11,
                    color: brass,
                    border: `1px solid ${brass}`,
                    borderRadius: 4,
                    padding: "2px 6px",
                    fontFamily: sans,
                    flexShrink: 0,
                    marginTop: 1,
                    whiteSpace: "nowrap",
                  }}
                >
                  {r.purpose}
                </div>
                <div style={{ fontSize: 14.5 }}>
                  <CodeLink code={r.code} onOpen={onOpenStandard} />
                  {r.title && <span style={{ fontSize: 13.5, color: "#6b6650" }}> — {r.title}</span>}
                  {r.amendment && <span style={{ fontSize: 12, color: "#8b8570", fontFamily: sans }}> ({r.amendment})</span>}
                  {!r.known && (
                    <span style={{ fontSize: 12, color: seal, fontFamily: sans }}> · not in registry — verify manually</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex items-center gap-3 pt-2 flex-wrap" style={{ borderTop: `1px solid ${line}` }}>
        <button
          onClick={watch}
          disabled={watched}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 5,
            fontSize: 12.5,
            color: watched ? good : brass,
            background: "none",
            border: `1px solid ${watched ? good : line}`,
            borderRadius: 4,
            padding: "5px 10px",
            cursor: watched ? "default" : "pointer",
            fontFamily: sans,
            marginTop: 10,
          }}
        >
          <Star size={13} fill={watched ? good : "none"} />
          {watched ? "Watching — see Monitor" : `Watch ${s.is_number}`}
        </button>
        {onOpenReport && (
          <button
            onClick={() => onOpenReport(s.is_number)}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              fontSize: 12.5,
              color: ink,
              background: "none",
              border: `1px solid ${line}`,
              borderRadius: 4,
              padding: "5px 10px",
              cursor: "pointer",
              fontFamily: sans,
              marginTop: 10,
            }}
          >
            <FileText size={13} /> Unified report
          </button>
        )}
        <span style={{ fontSize: 12.5, color: "#8b8570", fontFamily: sans, marginTop: 10 }}>Does this look right?</span>
        <div className="flex gap-2 mt-2">
          <button
            onClick={() => setFeedback("up")}
            style={{
              border: `1px solid ${feedback === "up" ? good : line}`,
              background: feedback === "up" ? "#e7efe9" : "transparent",
              color: feedback === "up" ? good : "#6b6650",
              borderRadius: 4,
              padding: "4px 7px",
              cursor: "pointer",
            }}
            aria-label="Helpful"
          >
            <ThumbsUp size={13} />
          </button>
          <button
            onClick={() => setFeedback("down")}
            style={{
              border: `1px solid ${feedback === "down" ? seal : line}`,
              background: feedback === "down" ? "#f3e6e2" : "transparent",
              color: feedback === "down" ? seal : "#6b6650",
              borderRadius: 4,
              padding: "4px 7px",
              cursor: "pointer",
            }}
            aria-label="Not helpful"
          >
            <ThumbsDown size={13} />
          </button>
        </div>
        {feedback && (
          <span style={{ fontSize: 12, color: "#8b8570", fontFamily: sans, marginTop: 10 }}>Thanks — noted.</span>
        )}
      </div>

      <div>
        <button
          onClick={onNewSearch}
          style={{
            marginTop: 18,
            fontSize: 13,
            color: ink,
            background: "none",
            border: `1px solid ${line}`,
            borderRadius: 4,
            padding: "8px 14px",
            cursor: "pointer",
            fontFamily: sans,
          }}
        >
          ← New search
        </button>
      </div>
    </div>
  );
}
