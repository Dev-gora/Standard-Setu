"use client";

import type { ReactNode } from "react";
import HeroGeometric from "./HeroGeometric";

/**
 * AmbientShell — the shared ambient interface: the dithered ink canvas
 * (wavy lines) fills the viewport as THE background — everywhere, never
 * removed — and content floats over it.
 *
 * mode "sheet": content wrapped in a centered paper card (Explore, Verify,
 *               Compare, Monitor).
 * mode "raw":   children rendered as-is over the canvas — for tabs that
 *               compose their own sheets (Recommend's conversation, Home's
 *               hero plate + manuscript).
 */
export default function AmbientShell({
  children,
  mode = "sheet",
}: {
  children: ReactNode;
  mode?: "sheet" | "raw";
}) {
  return (
    <div className="relative" style={{ minHeight: "calc(100vh - 96px)" }}>
      {/* Wavy ink canvas — the background everywhere, never removed */}
      <div aria-hidden className="fixed inset-0 top-0 z-0" style={{ pointerEvents: "none" }}>
        <HeroGeometric speed={0.9} className="h-full w-full" />
      </div>

      {mode === "sheet" ? (
        <div className="relative z-10 mx-auto w-full max-w-3xl px-4 py-8">        <div
          className="rounded-[24px] p-[clamp(18px,3vw,36px)]"
          style={{
            /* Near-solid paper: enough body that ink text stays crisp over
               the dark waves, while the canvas still ghosts through. */
            background: "rgba(247,245,238,0.96)",
            border: "1px solid rgba(201,195,171,0.9)",
            boxShadow: "0 30px 80px rgba(10,14,24,0.4), inset 0 1px 0 rgba(255,255,255,0.6)",
            backdropFilter: "blur(10px)",
            WebkitBackdropFilter: "blur(10px)",
          }}
        >
            {children}
        </div>
        </div>
      ) : (
        <div className="relative z-10 flex w-full flex-1 flex-col">{children}</div>
      )}
    </div>
  );
}
