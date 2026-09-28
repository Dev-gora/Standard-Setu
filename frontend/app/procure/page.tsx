"use client";

import { useEffect, useState } from "react";
import { Search, CircleAlert, Info, Languages, Upload, ArrowRight, Loader2, X } from "lucide-react";
import {
  procureRecommend,
  buildReport,
  type ProcureResponse,
  type ProcureRecommendation,
  type ReportResponse,
} from "@/lib/api";
import TermsModal from "@/components/procure/TermsModal";
import { hasAcceptedTerms, acceptTerms, installSessionPurge, installUnsavedDataWarning } from "@/lib/session";
import StandardModal from "@/components/procure/StandardModal";
import ResultView from "@/components/procure/ResultView";
import BulkPanel from "@/components/procure/BulkPanel";
import VerifyPanel from "@/components/procure/VerifyPanel";
import ComparePanel from "@/components/procure/ComparePanel";
import WatchlistPanel from "@/components/procure/WatchlistPanel";
import HistoryPanel from "@/components/procure/HistoryPanel";
import ReportView from "@/components/procure/ReportView";
import CircuitLoader from "@/components/procure/CircuitLoader";
import AgentSearch from "@/components/procure/AgentSearch";
import ExplorePanel from "@/components/procure/ExplorePanel";
import IntroPanel from "@/components/procure/IntroPanel";
import AmbientShell from "@/components/procure/AmbientShell";
import TabDock, { ChatFab, type TabKey } from "@/components/procure/TabDock";
import { ink, paper, line, brass, seal, sans, serif } from "@/components/procure/theme";

const SAMPLE_QUERIES = [
  "Steel for a warehouse structure",
  "PVC insulated electrical cable, 1.1kV",
  "Cement for a bridge deck",
  "Submersible pump for agricultural irrigation",
];

/**
 * Standard Setu — procurement home (/procure).
 * Ported from the POC with its paper/manuscript styling, wired to the
 * real recommend/clarify/bulk-check APIs. Chat remains the app's home page.
 */
export default function ProcurePage() {
  const [query, setQuery] = useState("");
  const [stage, setStage] = useState<"idle" | "loading" | "clarify" | "done" | "none" | "bulk">("idle");
  const [dataset, setDataset] = useState<ProcureResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modalCode, setModalCode] = useState<string | null>(null);
  const [tab, setTab] = useState<TabKey>("home");
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [termsOk, setTermsOk] = useState(true);

  useEffect(() => {
    setTermsOk(hasAcceptedTerms());
    installSessionPurge();
    installUnsavedDataWarning();
  }, []);

  const openReport = async (code: string) => {
    setReportLoading(true);
    try {
      setReport(await buildReport(query || code, code));
    } catch {
      /* report failed — keep the UI quiet, the result view still works */
    } finally {
      setReportLoading(false);
    }
  };

  const runQuery = async (text: string) => {
    setQuery(text);
    setError(null);
    setStage("loading");
    try {
      const d = await procureRecommend(text);
      setDataset(d);
      if (d.clarify_needed && d.clarify) setStage("clarify");
      else if (d.recommendations.length > 0) setStage("done");
      else setStage("none");
    } catch {
      setError("Could not reach the recommendation service — make sure the backend is running.");
      setStage("none");
    }
  };

  const reset = () => {
    setStage("idle");
    setQuery("");
    setDataset(null);
    setError(null);
  };

  if (!termsOk) {
    return (
      <TermsModal onAccept={() => { acceptTerms(); setTermsOk(true); }} />
    );
  }

  if (stage === "bulk") {
    return (
      <div style={{ background: paper, minHeight: "100vh", fontFamily: serif }} className="w-full">
        <style>{`* { box-sizing: border-box; } input, textarea, button { font-family: inherit; } ::placeholder { color: #a5a08c; }`}</style>
        <div style={{ borderBottom: `1px solid ${line}` }} className="px-6 md:px-10 py-4 flex items-center gap-3">
          <img src="/logo.png" alt="Standard Setu logo" width={30} height={30} style={{ flexShrink: 0 }} />
          <div style={{ fontSize: 16, color: ink }}>Standard Setu — bulk check</div>
        </div>
        <div className="px-6 md:px-10 py-8 max-w-3xl mx-auto">
          <BulkPanel onBack={() => setStage("idle")} />
        </div>
      </div>
    );
  }

  return (
    <div style={{ background: paper, minHeight: "100vh", fontFamily: serif }} className="w-full">
      <style>{`* { box-sizing: border-box; } input, textarea, button { font-family: inherit; } ::placeholder { color: #a5a08c; }`}</style>
      {modalCode && <StandardModal code={modalCode} onClose={() => setModalCode(null)} />}

      {reportLoading && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(28,36,56,0.45)", zIndex: 60, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <span style={{ color: paper, fontFamily: sans, fontSize: 14 }}>
            <Loader2 size={15} className="inline animate-spin mr-2" /> Assembling the report…
          </span>
        </div>
      )}
      {report && <ReportView report={report} onClose={() => setReport(null)} />}

      {/* Solid header retired: every tab is immersive — the canvas/photo
          reaches the top and only the floating dock sits above it. */}
      <div
        style={{ display: "none" }}
        className="px-6 md:px-10 py-4 flex items-center justify-between flex-wrap gap-3"
      >
        <div className="flex items-center gap-3">
          <img src="/logo.png" alt="Standard Setu logo" width={34} height={34} style={{ flexShrink: 0 }} />
          <div>
            <div style={{ fontSize: 16, color: ink }}>Standard Setu</div>
            <div style={{ fontSize: 11.5, color: "#8b8570", fontFamily: sans }}>
              Know what to write in your tender, and what you're required to check
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1.5" style={{ fontSize: 12.5, color: "#6b6650", fontFamily: sans }}>
          <Languages size={14} />
          English / हिंदी
        </div>
      </div>

      {/* DISCOVER → VERIFY → ANALYZE → MONITOR workflow tabs (glass dock) */}
      <TabDock active={tab} onChange={(k) => setTab(k)} floating />

      {tab === "home" && (
        <IntroPanel onEnter={() => setTab("recommend")} onJump={(k) => setTab(k as TabKey)} />
      )}

      {/* Recommend = immersive full-viewport conversation over the ambient canvas */}
      {tab === "recommend" && (
        <AgentSearch onOpenStandard={setModalCode} onOpenReport={openReport} />
      )}

      {tab !== "home" && tab !== "recommend" && (
        <AmbientShell>
          {tab === "explore" && <ExplorePanel onOpenStandard={setModalCode} />}

          {tab === "verify" && <VerifyPanel />}

          {tab === "compare" && <ComparePanel onOpenStandard={setModalCode} />}

          {tab === "monitor" && (
            <div className="flex flex-col gap-12">
              <WatchlistPanel onOpenStandard={setModalCode} />
              <HistoryPanel />
            </div>
          )}
        </AmbientShell>
      )}

      {/* Always-available chat — floating bottom-right on every tab */}
      <ChatFab onClick={() => setTab("recommend")} />
    </div>
  );
}
