"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { CheckCircle2, ChevronDown, ChevronRight, Loader2, CircleAlert } from "lucide-react";
import { cn } from "@/lib/utils";
import { line, sans } from "./theme";

export interface StepBlock {
  key: string;
  label: string;
  detail?: string;
  state: "running" | "done" | "error";
}

/**
 * Claude-style collapsible tool block for one pipeline step.
 * Shows the agent "thinking": Searching -> Reading evidence -> Checking certification.
 */
export default function AgentSteps({ steps, defaultOpen = false }: { steps: StepBlock[]; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const running = steps.some((s) => s.state === "running");
  const errored = steps.some((s) => s.state === "error");
  const doneCount = steps.filter((s) => s.state === "done").length;

  const headline = errored
    ? "Hit a snag mid-search"
    : running
      ? steps.find((s) => s.state === "running")?.label || "Working…"
      : `Searched the registry (${doneCount} step${doneCount === 1 ? "" : "s"})`;

  return (
    <div className="mb-3" style={{ fontFamily: sans }}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 rounded-md px-2 py-1.5 transition-colors"
        style={{ border: `1px solid ${line}`, background: "rgba(255,255,255,0.55)", cursor: "pointer" }}
      >
        {errored ? (
          <CircleAlert size={13} style={{ color: "#8a3324" }} />
        ) : running ? (
          <Loader2 size={13} className="animate-spin" style={{ color: "#a9722f" }} />
        ) : (
          <CheckCircle2 size={13} style={{ color: "#3f6b4e" }} />
        )}
        <span className={cn("text-[12.5px]", running && "animate-pulse")} style={{ color: "#5c5843" }}>
          {headline}
        </span>
        {open ? <ChevronDown size={12} style={{ color: "#8b8570" }} /> : <ChevronRight size={12} style={{ color: "#8b8570" }} />}
      </button>

      {open && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          className="ml-3 mt-2 flex flex-col gap-1.5 overflow-hidden border-l pl-3"
          style={{ borderColor: line }}
        >
          {steps.map((s) => (
            <div key={s.key} className="flex items-start gap-2">
              {s.state === "running" ? (
                <Loader2 size={11} className="mt-1 animate-spin" style={{ color: "#a9722f" }} />
              ) : s.state === "error" ? (
                <CircleAlert size={11} className="mt-1" style={{ color: "#8a3324" }} />
              ) : (
                <CheckCircle2 size={11} className="mt-1" style={{ color: "#3f6b4e" }} />
              )}
              <div>
                <div className="text-[12px]" style={{ color: s.state === "done" ? "#6b6650" : "#1c2438" }}>
                  {s.label}
                </div>
                {s.detail && (
                  <div className="text-[11px]" style={{ color: "#8b8570" }}>
                    {s.detail}
                  </div>
                )}
              </div>
            </div>
          ))}
        </motion.div>
      )}
    </div>
  );
}
