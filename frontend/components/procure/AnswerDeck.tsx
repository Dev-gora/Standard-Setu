"use client";

import { useEffect, useRef, type ReactNode } from "react";
import {
  motion,
  useMotionValue,
  useReducedMotion,
  useTransform,
  type MotionValue,
} from "framer-motion";
import type { ProcureRecommendation } from "@/lib/api";
import { sans, serif } from "./theme";

/**
 * Scroll-driven flip deck for recommendations — one card per standard.
 * Progress is split into equal segments, one per card. Inside each segment
 * the current card FLIPS off the deck (slides up with a 3D tilt) while the
 * next card rises into place, then holds dead-still for the rest of the
 * segment. No opacity fades: wherever the user stops, exactly one card sits
 * on top at full clarity.
 */
export default function AnswerDeck({
  items,
  query,
  onOpenStandard,
  containerRef,
}: {
  items: ProcureRecommendation[];
  query: string;
  onOpenStandard?: (code: string) => void;
  /** The scrollable chat thread — the deck tracks ITS scroll, not the window's. */
  containerRef?: React.RefObject<HTMLDivElement>;
}) {
  const stackRef = useRef<HTMLDivElement>(null);
  const reduceMotion = useReducedMotion() ?? false;
  const total = Math.max(items.length, 1);

  // Manual progress tracking: framer-motion's useScroll container tracking is
  // unreliable inside nested scroll containers, so we compute deck progress
  // directly from the chat thread's scroll position. Driven directly (no
  // spring): useSpring on a source MotionValue proved unreliable here —
  // updates stopped propagating and froze the deck at progress 0.
  const rawProgress = useMotionValue(0);

  useEffect(() => {
    const container = containerRef?.current;
    const stack = stackRef.current;
    if (!container || !stack) return;

    // Measure only: where does the deck sit in its scroll range (0..1)?
    let target = 0;
    const measure = () => {
      const stickyEl = stack.firstElementChild as HTMLElement | null;
      if (!stickyEl) return;
      const cRect = container.getBoundingClientRect();
      const sRect = stack.getBoundingClientRect();
      // How far the deck's top has travelled above the container top (it pins at 0).
      const pastStart = cRect.top - sRect.top;
      const pinDistance = Math.max(stack.offsetHeight - stickyEl.offsetHeight, 1);
      target = Math.max(0, Math.min(1, pastStart / pinDistance));
    };

    measure();
    rawProgress.set(target);

    // Choppiness fix: wheel/touch input moves the scroll position in discrete
    // jumps, and 1:1 mapping makes the cards jump with it. Drive the deck from
    // its own rAF loop, easing toward the measured target every frame — one
    // fluid motion regardless of how coarse the input events are. (framer's
    // useSpring proved unreliable here — its updates stopped propagating and
    // froze the deck — so the easing is hand-rolled.)
    let raf = requestAnimationFrame(function tick() {
      const current = rawProgress.get();
      const delta = target - current;
      // Fast enough to feel attached to the scroll, soft enough to hide steps.
      if (Math.abs(delta) > 0.0003) rawProgress.set(current + delta * 0.18);
      raf = requestAnimationFrame(tick);
    });

    container.addEventListener("scroll", measure, { passive: true });
    window.addEventListener("resize", measure);
    return () => {
      cancelAnimationFrame(raf);
      container.removeEventListener("scroll", measure);
      window.removeEventListener("resize", measure);
    };
  }, [containerRef, rawProgress]);

  return (
    <div>
      {/* The question, pinned like a chat turn */}
      <div className="mb-6 flex justify-end">
        <div
          style={{ background: "#e7e3d4", border: "1px solid #c9c3ab", borderRadius: 16, maxWidth: "78%" }}
          className="px-4 py-2.5"
        >
          <p style={{ fontSize: 14.5, color: "#1c2438", fontFamily: serif, fontStyle: "italic" }}>{query}</p>
        </div>
      </div>

      <div
        ref={stackRef}
        data-deck-start
        className="relative"
        style={{ height: `calc(${total + 1} * (100dvh - 128px))` }}
      >
        {/* Stage height = the visible area above the pinned composer (~112px
            + buffer), so a pinned card spans the full screen with no dead
            band underneath. (Was 100vh - 250px from the old static-bar
            layout, which left ~140px of empty space below the card.) */}
        <div
          className="sticky top-0 flex flex-col justify-center overflow-hidden px-1 py-4"
          style={{ height: "calc(100dvh - 128px)" }}
        >
          {/* Card frame takes the stage's free space (above the hint line);
              the card fills it exactly, always fully visible top-to-bottom. */}
          <div className="relative mx-auto min-h-0 w-full max-w-[720px] flex-1 [perspective:1100px]">
            {[...items].reverse().map((rec, reverseIndex) => {
              const index = items.length - reverseIndex - 1;
              return (
                <FlipCard
                  key={rec.standard.is_number + index}
                  rec={rec}
                  index={index}
                  total={total}
                  progress={rawProgress}
                  reduceMotion={reduceMotion}
                  onOpenStandard={onOpenStandard}
                />
              );
            })}
          </div>

          <p className="mt-4 text-center text-[11px]" style={{ color: "#a5a08c", fontFamily: sans }}>
            Scroll — each card flips away, then holds steady · tap a code for details
          </p>
        </div>
      </div>
    </div>
  );
}

function FlipCard({
  rec,
  index,
  total,
  progress,
  reduceMotion,
  onOpenStandard,
}: {
  rec: ProcureRecommendation;
  index: number;
  total: number;
  progress: MotionValue<number>;
  reduceMotion: boolean;
  onOpenStandard?: (code: string) => void;
}) {
  const s = rec.standard;
  // Discrete segments: card i owns [i*seg, (i+1)*seg] of the scroll range.
  // It HOLDS — fully legible, dead still — for the first 60% of its segment,
  // then (unless it is the last card) flips away during the final 40% while
  // the next card rises into place underneath it. Wherever the user stops,
  // exactly one card sits on top at full clarity.
  const segment = 1 / Math.max(total, 1);
  const isLast = index === total - 1;
  const flipStart = Math.min(index * segment + segment * 0.6, 1);
  const flipEnd = Math.min((index + 1) * segment, 1);

  // Flip away: slide up off the deck with a 3D tilt. Under reduced motion
  // this degrades to a pure vertical slide (no 3D, no scale) — still fully
  // opaque, still driven 1:1 by scroll so navigation always works. The last
  // card never flips: it holds to the end of the scroll range.
  const exitYPercent = useTransform(
    progress,
    [flipStart, flipEnd],
    isLast ? ["0%", "0%"] : reduceMotion ? ["0%", "-112%"] : ["0%", "-124%"]
  );
  const rotateX = useTransform(progress, [flipStart, flipEnd], isLast || reduceMotion ? [0, 0] : [0, 24]);
  const exitScale = useTransform(progress, [flipStart, flipEnd], isLast || reduceMotion ? [1, 1] : [1, 0.96]);

  // Rise into place DURING the previous card's flip window (the same 40%),
  // so once the flip finishes both cards are motionless for the rest of the
  // segment — the resting view never drifts. The incoming card comes up from
  // underneath the outgoing one, fully opaque: nothing to fade.
  const prevFlipStart = Math.max(0, (index - 1) * segment + segment * 0.6);
  const prevFlipEnd = Math.min(index * segment, 1);
  const riseFrom = index === 0 || reduceMotion ? 0 : 26;
  const riseY = useTransform(progress, [prevFlipStart, prevFlipEnd], [riseFrom, 0]);

  const certMandatory = s.certification?.mandatory;
  // Paper-plate palette: heavy paper cards with ink text — like stiff board
  // plates lifted from a manuscript — with brass doing the decorating.
  const background = index === 0 ? "#f6f4ea" : index === 1 ? "#f1efe6" : "#e9e5d5";
  const foreground = "#1c2438";
  const brass = "#a9722f";
  const seal = "#8a3324";
  const score = rec.match?.score ?? Math.round(rec.relevance_score * 100);
  const factors = (rec.match?.factors || []).slice(0, 4);
  const evidenceClaims = (rec.evidence || []).filter((e) => e?.evidence).slice(0, 2);
  const kindLabel: Record<string, string> = {
    requirement_match: "Match",
    scope: "Scope",
    certification: "Cert",
    edition: "Edition",
    source: "Source",
  };

  return (
    <motion.article
      className="absolute inset-0 will-change-transform"
      style={{
        y: exitYPercent,
        rotateX,
        scale: exitScale,
        // Flip deck: the outgoing card slides away ABOVE the incoming one;
        // top card = highest rank number still in the deck.
        zIndex: total - index,
        transformOrigin: "50% 40%",
        transformStyle: "preserve-3d",
        backfaceVisibility: "hidden",
      }}
    >
      <motion.div
        className="relative grid h-full overflow-hidden rounded-[clamp(18px,2vw,30px)] shadow-[0_24px_60px_rgba(28,36,56,0.22)] min-[480px]:grid-cols-[1.15fr_0.85fr]"
        style={{
          backgroundColor: background,
          color: foreground,
          y: riseY,
          transformOrigin: "50% 100%",
        }}
      >
        {/* Hairline brass frame, like a printed ledger plate (paper needs no texture) */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-[9px] rounded-[clamp(10px,1.2vw,20px)]"
          style={{ border: `1px solid ${brass}45` }}
        />

        {/* Left pane: rank, identity, the reason it matched, and real actions */}
        <div className="relative flex min-w-0 flex-col p-[clamp(20px,2.6vw,40px)] md:pr-[clamp(18px,2.4vw,40px)]">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-[clamp(8px,1vw,14px)]">
              <span
                className="text-[clamp(24px,2.4vw,36px)] font-medium leading-none tracking-[-0.06em]"
                style={{ fontFamily: serif, color: brass }}
              >
                {String(index + 1).padStart(2, "0")}
              </span>
              <span aria-hidden className="h-[clamp(20px,2vw,30px)] w-px" style={{ background: `${foreground}33` }} />
              <span className="text-[9.5px] font-semibold uppercase tracking-[0.18em] opacity-65" style={{ fontFamily: sans }}>
                Rank {index + 1} of {total}
              </span>
            </div>
            <ScoreRing value={score} accent={brass} plate="rgba(28,36,56,0.05)" />
          </div>

          <div className="mt-auto max-w-[46rem] pt-[clamp(10px,1.4vw,20px)]">
            <div className="mb-[clamp(8px,1vw,14px)] flex items-center gap-3">
              <p className="shrink-0 text-[10px] font-semibold uppercase tracking-[0.16em] opacity-70" style={{ fontFamily: sans }}>
                {s.category || "Indian Standard"}
              </p>
              <span aria-hidden className="h-px flex-1" style={{ background: `${foreground}26` }} />
            </div>
            <button
              onClick={() => onOpenStandard?.(s.is_number)}
              className="text-left text-[clamp(22px,2.4vw,36px)] font-semibold leading-[1.02] tracking-[-0.03em] underline decoration-from-font underline-offset-[6px]"
              style={{ fontFamily: serif, cursor: "pointer", textDecorationColor: `${brass}b3` }}
            >
              {s.is_number}
            </button>
            <h2 className="mt-[clamp(4px,0.6vw,10px)] line-clamp-2 max-w-[26ch] text-[clamp(13px,1.25vw,17px)] leading-[1.3] opacity-90" style={{ fontFamily: serif }}>
              {s.title}
            </h2>
            {rec.reason && (
              <p
                className="mt-[clamp(6px,0.8vw,12px)] line-clamp-2 max-w-[44rem] text-[clamp(11px,1vw,13.5px)] italic leading-[1.45] opacity-70"
                style={{ fontFamily: serif }}
              >
                {rec.reason}
              </p>
            )}

            <div className="mt-[clamp(8px,1vw,14px)] flex flex-wrap items-center gap-1.5">
              <Chip>Edition {s.latest_version}</Chip>
              {s.amendment ? <Chip>{s.amendment}</Chip> : null}
              {/* Provenance-honest chip (audit item 12): only QCO-backed claims
                  say 'Mandatory'; unverified claims say 'per registry'. */}
              {certMandatory
                ? (s.certification?.verification_status === "VERIFIED"
                    ? <Chip tint={seal}>BIS mark · Mandatory (QCO)</Chip>
                    : <Chip tint={seal}>BIS mark · Mandatory*</Chip>)
                : <Chip>BIS mark not mandatory</Chip>}
            </div>

            <div className="mt-[clamp(8px,1vw,14px)] flex flex-wrap items-center gap-2">
              <button
                onClick={() => onOpenStandard?.(s.is_number)}
                className="rounded-full px-3 py-[5px] text-[10px] font-semibold uppercase tracking-[0.14em] transition-opacity hover:opacity-80"
                style={{ fontFamily: sans, border: `1px solid ${foreground}44`, color: foreground }}
              >
                Open details →
              </button>
              {s.archive_link?.url && (
                <a
                  href={s.archive_link.url}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-full px-3 py-[5px] text-[10px] font-semibold uppercase tracking-[0.14em] transition-opacity hover:opacity-80"
                  style={{ fontFamily: sans, border: `1px solid ${brass}66`, color: brass }}
                >
                  Source PDF ↗
                </a>
              )}
            </div>
          </div>
        </div>

        {/* Right pane: score anatomy, evidence trail, tender wording */}
        <div
          className="relative m-[clamp(10px,1.2vw,18px)] flex min-h-0 flex-col overflow-hidden rounded-[clamp(12px,1.4vw,22px)] p-[clamp(12px,1.3vw,18px)] sm:ml-0"
          style={{ background: "rgba(28,36,56,0.05)", border: `1px solid rgba(28,36,56,0.12)` }}
        >
          <div className="mb-[clamp(8px,1vw,12px)] flex items-center justify-between gap-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] opacity-70" style={{ fontFamily: sans }}>
              Why this score
            </p>
            {rec.match?.confidence && (
              <span
                className="shrink-0 rounded-full px-2 py-[3px] text-[9px] font-semibold uppercase tracking-[0.12em]"
                style={{ fontFamily: sans, border: `1px solid ${foreground}3d`, opacity: 0.85 }}
              >
                {rec.match.confidence}
              </span>
            )}
          </div>

          <div className="flex flex-col gap-[clamp(6px,0.8vw,10px)]">
            {factors.map((f) => (
              <div key={f.label}>
                <div className="flex items-center justify-between text-[10.5px] opacity-85" style={{ fontFamily: sans }}>
                  <span className="truncate pr-2">{f.label}</span>
                  <span className="shrink-0 tabular-nums">{f.value}%</span>
                </div>
                <div className="mt-1 h-[5px] rounded-full" style={{ background: "rgba(28,36,56,0.12)" }}>
                  <motion.div
                    className="h-[5px] rounded-full"
                    style={{ background: `linear-gradient(90deg, ${brass}, #e9cf9c)` }}
                    initial={{ width: 0 }}
                    whileInView={{ width: `${f.value}%` }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.8, delay: 0.2 }}
                  />
                </div>
              </div>
            ))}
            {!rec.match && (
              <p className="text-[12px] opacity-70" style={{ fontFamily: sans }}>
                Score breakdown unavailable for this result.
              </p>
            )}
          </div>

          {evidenceClaims.length > 0 && (
            <div className="mt-[clamp(8px,1vw,14px)]">
              <p className="mb-1.5 text-[9.5px] font-semibold uppercase tracking-[0.16em] opacity-60" style={{ fontFamily: sans }}>
                Evidence trail
              </p>
              <div className="flex flex-wrap gap-1.5">
                {evidenceClaims.map((e, i) => {
                  const ev = e.evidence;
                  const locator = ev.clause
                    ? `Cl. ${ev.clause}`
                    : ev.page != null
                      ? `p. ${ev.page}`
                      : kindLabel[e.kind] || "Ref";
                  const body = (
                    <>
                      <span style={{ color: brass }}>{locator}</span>
                      {ev.document ? <span className="opacity-75"> · {ev.document}</span> : null}
                    </>
                  );
                  return ev.url ? (
                    <a
                      key={i}
                      href={ev.url}
                      target="_blank"
                      rel="noreferrer"
                      className="max-w-full truncate rounded-md px-2 py-[3px] text-[9.5px] transition-opacity hover:opacity-85"
                      style={{ fontFamily: sans, background: `${foreground}0f`, border: `1px solid ${foreground}2b` }}
                    >
                      {body}
                    </a>
                  ) : (
                    <span
                      key={i}
                      className="max-w-full truncate rounded-md px-2 py-[3px] text-[9.5px]"
                      style={{ fontFamily: sans, background: `${foreground}0f`, border: `1px solid ${foreground}2b` }}
                    >
                      {body}
                    </span>
                  );
                })}
              </div>
            </div>
          )}

          {(rec.allied?.length || 0) > 0 && (
            <p className="mt-[clamp(6px,0.8vw,10px)] text-[9.5px] uppercase tracking-[0.14em] opacity-55" style={{ fontFamily: sans }}>
              + {rec.allied.length} allied standard{rec.allied.length === 1 ? "" : "s"} referenced
            </p>
          )}

          {rec.tender_block && (
            <p
              className="mt-auto line-clamp-2 border-l-2 pl-2 pt-1 text-[10.5px] italic leading-[1.4] opacity-60"
              style={{ fontFamily: sans, borderColor: `${brass}80` }}
            >
              “{rec.tender_block.slice(0, 150)}…”
            </p>
          )}
        </div>
      </motion.div>
    </motion.article>
  );
}

function Chip({ children, tint }: { children: ReactNode; tint?: string }) {
  return (
    <span
      className="rounded-full px-2 py-[3px] text-[9.5px] font-medium uppercase tracking-[0.12em]"
      style={{
        fontFamily: sans,
        border: `1px solid ${tint ?? "#1c2438"}4d`,
        color: tint ?? "#1c2438",
        opacity: tint ? 0.95 : 0.8,
      }}
    >
      {children}
    </span>
  );
}

/** Hand-rolled score dial — a conic-gradient ring, no chart dependency. */
function ScoreRing({ value, accent, plate, size = 52 }: { value: number; accent: string; plate: string; size?: number }) {
  const v = Math.max(0, Math.min(100, Math.round(value)));
  return (
    <div
      className="relative shrink-0 rounded-full"
      style={{ width: size, height: size, background: `conic-gradient(${accent} ${v}%, rgba(28,36,56,0.14) 0)` }}
      title={`Match score ${v}/100`}
    >
      <div className="absolute inset-[4px] flex flex-col items-center justify-center rounded-full" style={{ background: plate }}>
        <span className="leading-none" style={{ fontFamily: serif, fontSize: size * 0.34, fontWeight: 600 }}>
          {v}
        </span>
        <span className="mt-[1px] uppercase leading-none opacity-60" style={{ fontFamily: sans, fontSize: 6.5, letterSpacing: "0.14em" }}>
          match
        </span>
      </div>
    </div>
  );
}
