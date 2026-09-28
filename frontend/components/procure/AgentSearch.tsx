"use client";

import { useCallback, useRef, useState } from "react";
import { motion } from "framer-motion";
import { ArrowUp, CircleAlert, FolderUp } from "lucide-react";
import { procureRecommend, type ProcureResponse } from "@/lib/api";
import BulkPanel from "./BulkPanel";
import AmbientShell from "./AmbientShell";
import AgentSteps, { type StepBlock } from "./AgentSteps";
import AnswerDeck from "./AnswerDeck";
import { ink, paper, line, brass, seal, sans, serif } from "./theme";

interface Turn {
  key: string;
  from: "user" | "agent";
  /** user turn */
  text?: string;
  /** agent turn */
  steps?: StepBlock[];
  data?: ProcureResponse;
  error?: string;
}

const SAMPLES = [
  "Reinforcement bars for concrete in a bridge deck",
  "Steel for a warehouse structure",
  "PVC insulated electrical cable, 1.1kV",
  "Cement for a bridge deck",
];

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/**
 * Claude-style agent search for the Recommend tab — full-viewport layout:
 * the dithered ink canvas fills the whole screen as ambient background and
 * the conversation floats over it as centered paper "sheets" (like mail
 * pages over a desk). The flip-card deck renders as the pages themselves.
 */
export default function AgentSearch({
  onOpenStandard,
  onOpenReport,
}: {
  onOpenStandard: (code: string) => void;
  onOpenReport?: (code: string) => void;
}) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [pendingClarify, setPendingClarify] = useState<{ turnKey: string; query: string; options: { label: string; query: string }[] } | null>(null);
  const [bulkMode, setBulkMode] = useState(false);
  const threadRef = useRef<HTMLDivElement>(null);

  const scrollToEnd = () => {
    requestAnimationFrame(() => {
      threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: "smooth" });
    });
  };

  const patchTurn = (key: string, patch: Partial<Turn>) =>
    setTurns((prev) => prev.map((t) => (t.key === key ? { ...t, ...patch } : t)));

  const runAgent = useCallback(async (query: string) => {
    setBusy(true);
    const agentKey = `agent-${Date.now()}`;
    setTurns((prev) => [
      ...prev,
      {
        key: agentKey,
        from: "agent",
        steps: [
          { key: "parse", label: "Reading your requirement", state: "running" },
          { key: "search", label: "Searching 130 Indian Standards", state: "running" },
          { key: "evidence", label: "Resolving clause/page evidence", state: "running" },
          { key: "cert", label: "Checking certification requirements", state: "running" },
          { key: "spec", label: "Drafting tender wording", state: "running" },
        ],
      },
    ]);
    scrollToEnd();

    // Animated step progression (visual only; the API call runs in parallel).
    const timers = [
      setTimeout(() => setTurns((prev) => prev.map((t) => t.key === agentKey ? { ...t, steps: t.steps?.map((s, i) => i <= 0 ? { ...s, state: "done" as const } : s) } : t)), 350),
      setTimeout(() => setTurns((prev) => prev.map((t) => t.key === agentKey ? { ...t, steps: t.steps?.map((s, i) => i === 1 ? { ...s, state: "done" as const } : s) } : t)), 800),
      setTimeout(() => setTurns((prev) => prev.map((t) => t.key === agentKey ? { ...t, steps: t.steps?.map((s, i) => i === 2 ? { ...s, state: "done" as const } : s) } : t)), 1300),
      setTimeout(() => setTurns((prev) => prev.map((t) => t.key === agentKey ? { ...t, steps: t.steps?.map((s, i) => i === 3 ? { ...s, state: "done" as const } : s) } : t)), 1800),
    ];

    try {
      const data = await procureRecommend(query);
      timers.forEach(clearTimeout);

      // Finish all steps, then reveal the answer.
      setTurns((prev) => prev.map((t) => t.key === agentKey ? { ...t, steps: t.steps?.map((s) => ({ ...s, state: "done" as const })) } : t));
      await sleep(420);

      if (data.clarify_needed && data.clarify) {
        patchTurn(agentKey, { data });
        setPendingClarify({ turnKey: agentKey, query, options: data.clarify.options });
        scrollToEnd();
      } else {
        patchTurn(agentKey, { data });
        scrollToEnd();
      }
    } catch {
      timers.forEach(clearTimeout);
      patchTurn(agentKey, {
        error: "Could not reach the recommendation service — make sure the backend is running.",
        steps: [
          { key: "failed", label: "Search failed", detail: "Network or backend error", state: "error" },
        ],
      });
    } finally {
      setBusy(false);
      setDraft("");
    }
  }, []);

  const send = () => {
    const text = draft.trim();
    if (!text || busy) return;
    setTurns((prev) => [...prev, { key: `user-${Date.now()}`, from: "user", text }]);
    setDraft("");
    scrollToEnd();
    void runAgent(text);
  };

  const answerClarify = (optionQuery: string) => {
    if (!pendingClarify) return;
    setPendingClarify(null);
    setTurns((prev) => [...prev, { key: `user-${Date.now()}`, from: "user", text: optionQuery }]);
    scrollToEnd();
    void runAgent(optionQuery);
  };

  const inputLocked = busy || !!pendingClarify;
  const empty = turns.length === 0;

  if (bulkMode) {
    return (
      <AmbientShell mode="raw">
        {/* BulkPanel renders inside a centered paper sheet — same page
            metaphor as every other view, never a full-width raw block. */}
        <div className="mx-auto w-full max-w-[860px] px-4 py-8">
          <div
            className="rounded-[24px] p-[clamp(18px,3vw,36px)]"
            style={{
              background: "rgba(247,245,238,0.96)",
              border: "1px solid rgba(201,195,171,0.9)",
              boxShadow: "0 30px 80px rgba(10,14,24,0.4), inset 0 1px 0 rgba(255,255,255,0.6)",
              backdropFilter: "blur(10px)",
              WebkitBackdropFilter: "blur(10px)",
            }}
          >
            <BulkPanel onBack={() => setBulkMode(false)} />
          </div>
        </div>
      </AmbientShell>
    );
  }

  return (
    <AmbientShell mode="raw">
      {/* Conversation column — a fixed app-shell: thread scrolls and uses
          the whole screen, composer is a true footer at the viewport bottom
          (it must never drift up or float mid-screen after an answer).
          The floating nav is an overlay, so no height is reserved for it. */}
      <div
        className="relative z-10 mx-auto flex h-screen w-full max-w-[860px] flex-col px-4"
        style={{ height: "100dvh" }}
      >
        <div ref={threadRef} data-thread className="min-h-0 flex-1 overflow-y-auto py-6 pr-1">
          {empty && (
            <div className="flex flex-1 flex-col items-center justify-center">
              {/* Landing sheet — the hero page of the conversation */}
              <motion.div
                initial={{ opacity: 0, y: 22 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                className="w-full max-w-[680px] rounded-[26px] p-[clamp(28px,4vw,52px)] text-center"
                style={{
                  background: "rgba(247,245,238,0.96)",
                  border: "1px solid rgba(201,195,171,0.9)",
                  boxShadow: "0 30px 80px rgba(10,14,24,0.45), inset 0 1px 0 rgba(255,255,255,0.6)",
                  backdropFilter: "blur(10px)",
                  WebkitBackdropFilter: "blur(10px)",
                }}
              >
                <h1
                  style={{
                    fontSize: "clamp(28px, 4.4vw, 46px)",
                    color: ink,
                    fontWeight: 700,
                    letterSpacing: "-0.03em",
                    lineHeight: 1.05,
                    marginBottom: 12,
                    fontFamily: serif,
                  }}
                >
                  What are you procuring?
                </h1>
                <p style={{ fontSize: 15, color: "rgba(28,36,56,0.8)", marginBottom: 24, fontFamily: sans, maxWidth: 520, marginInline: "auto", lineHeight: 1.6 }}>
                  Ask in plain language. I&apos;ll search the registry, resolve evidence, check
                  certification, and draft your tender wording — then you can follow up right here.
                </p>
                <div className="flex flex-wrap items-center justify-center gap-2">
                  <span style={{ fontSize: 12, color: "rgba(28,36,56,0.6)", fontFamily: sans }}>Try:</span>
                  {SAMPLES.map((s) => (
                    <button
                      key={s}
                      onClick={() => { setTurns((prev) => [...prev, { key: `user-${Date.now()}`, from: "user", text: s }]); void runAgent(s); }}
                      style={{
                        fontSize: 12.5, color: ink, border: "1px solid rgba(28,36,56,0.25)",
                        borderRadius: 20, padding: "5px 13px", background: "rgba(255,255,255,0.55)",
                        cursor: "pointer", fontFamily: sans,
                      }}
                    >
                      {s}
                    </button>
                  ))}
                </div>
                {/* Bulk tender upload — up to 500 PDFs per batch */}
                <button
                  onClick={() => setBulkMode(true)}
                  className="mx-auto mt-6 flex items-center gap-2 rounded-full px-4 py-2 text-[12.5px] transition-opacity hover:opacity-85"
                  style={{
                    fontFamily: sans,
                    color: ink,
                    border: `1px dashed ${ink}66`,
                    background: "rgba(255,255,255,0.4)",
                    cursor: "pointer",
                  }}
                >
                  <FolderUp size={14} style={{ color: brass }} />
                  Upload tenders instead — check up to 500 PDFs at once
                </button>
              </motion.div>
            </div>
          )}

          {turns.map((t) =>
            t.from === "user" ? (
              <motion.div key={t.key} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="mb-5 flex justify-end">
                <div style={{ background: "#e7e3d4", border: `1px solid ${line}`, borderRadius: 16, maxWidth: "78%", boxShadow: "0 6px 18px rgba(10,14,24,0.12)" }} className="px-4 py-2.5">
                  <p style={{ fontSize: 14.5, color: ink, fontFamily: serif, fontStyle: "italic" }}>{t.text}</p>
                </div>
              </motion.div>
            ) : (
              <motion.div key={t.key} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="mb-7">
                {t.steps && (
                  <div
                    className="mb-3 rounded-2xl p-3"
                    style={{ background: "rgba(247,245,238,0.94)", border: `1px solid ${line}`, boxShadow: "0 10px 30px rgba(10,14,24,0.18)", backdropFilter: "blur(8px)", WebkitBackdropFilter: "blur(8px)" }}
                  >
                    <AgentSteps steps={t.steps} />
                  </div>
                )}
                {t.error && (
                  <div style={{ border: `1px solid ${seal}`, borderRadius: 6, background: "#f3e6e2" }} className="p-4">
                    <p style={{ fontSize: 13.5, color: seal, fontFamily: sans }}>{t.error}</p>
                  </div>
                )}
                {t.data && !t.data.clarify_needed && t.data.recommendations.length > 0 && (
                  <AnswerDeck items={t.data.recommendations} query={t.data.query} onOpenStandard={onOpenStandard} containerRef={threadRef} />
                )}
                {t.data && !t.data.clarify_needed && t.data.recommendations.length === 0 && (
                  <div style={{ border: `1px solid ${line}`, borderRadius: 6, background: "rgba(247,245,238,0.96)" }} className="p-4">
                    <p style={{ fontSize: 14, color: ink }}>
                      Couldn&apos;t confidently match this to a standard. Try adding the material or product type — e.g. &quot;GI pipe&quot;, &quot;cement&quot;, &quot;cable&quot;.
                    </p>
                  </div>
                )}
                {t.data?.clarify_needed && t.data.clarify && (
                  <div style={{ border: `1px solid ${brass}`, borderRadius: 6, background: "#f6ecda" }} className="p-4">
                    <p style={{ fontSize: 14.5, color: ink, marginBottom: 4 }}>{t.data.clarify.question}</p>
                    {t.data.clarify.helper && (
                      <p style={{ fontSize: 12.5, color: "#8b7a55", fontFamily: sans, marginBottom: 12 }}>{t.data.clarify.helper}</p>
                    )}
                    {pendingClarify?.turnKey === t.key ? (
                      <div className="flex flex-col gap-2">
                        {t.data.clarify.options.map((o) => (
                          <button
                            key={o.label}
                            onClick={() => answerClarify(o.query)}
                            style={{ fontSize: 13.5, border: `1px solid ${ink}`, color: ink, borderRadius: 4, padding: "9px 13px", background: "rgba(255,255,255,0.6)", cursor: "pointer", textAlign: "left", fontFamily: sans }}
                          >
                            {o.label}
                          </button>
                        ))}
                      </div>
                    ) : (
                      <p style={{ fontSize: 12.5, color: "#8b8570", fontFamily: sans }}>
                        Answer with the input below — or start a new question.
                      </p>
                    )}
                  </div>
                )}
              </motion.div>
            )
          )}
        </div>

        {/* Composer — footer, always pinned to the bottom of the screen */}
        <div className="z-20 shrink-0 pb-4 pt-2">
          {pendingClarify && (
            <p style={{ fontSize: 12, color: brass, fontFamily: sans, marginBottom: 6, textShadow: "0 1px 6px rgba(241,239,230,0.8)" }}>
              <CircleAlert size={12} className="mr-1 inline" />
              The agent asked a clarifying question — pick an option above to continue.
            </p>
          )}
          <div
            className="flex items-end gap-2 rounded-2xl p-2 transition-shadow"
            style={{
              border: `1px solid ${line}`,
              background: "rgba(247,245,238,0.96)",
              boxShadow: "0 18px 44px rgba(10,14,24,0.35)",
              backdropFilter: "blur(12px)",
              WebkitBackdropFilter: "blur(12px)",
              opacity: inputLocked ? 0.55 : 1,
            }}
          >
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              disabled={inputLocked}
              placeholder={busy ? "Agent is working…" : pendingClarify ? "Answer the question above first" : "Ask about any product…"}
              rows={1}
              className="max-h-28 flex-1 resize-none bg-transparent px-3 py-2 outline-none"
              style={{ fontSize: 14.5, color: ink, fontFamily: sans }}
            />
            <button
              onClick={send}
              disabled={!draft.trim() || inputLocked}
              aria-label="Send"
              style={{
                display: "flex", alignItems: "center", justifyContent: "center",
                width: 36, height: 36, borderRadius: 10,
                background: draft.trim() && !inputLocked ? "#c96442" : "#b8b39d",
                color: paper, border: "none", cursor: !draft.trim() || inputLocked ? "not-allowed" : "pointer",
              }}
            >
              <ArrowUp size={16} />
            </button>
          </div>
          <p
            className="mx-auto mt-2 w-fit rounded-full px-3 py-1"
            style={{ fontSize: 10.5, color: "rgba(28,36,56,0.75)", fontFamily: sans, textAlign: "center", background: "rgba(247,245,238,0.92)", border: "1px solid rgba(201,195,171,0.7)" }}
          >
            Standard Setu can make mistakes — verify on the BIS portal before citing in a tender.
          </p>
        </div>
      </div>
    </AmbientShell>
  );
}
