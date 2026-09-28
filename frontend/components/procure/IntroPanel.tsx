"use client";

import { useEffect, useState } from "react";
import { motion, useMotionTemplate, useMotionValue, useReducedMotion, useTransform } from "framer-motion";
import { BookOpen, Scale, FileWarning, Search, Compass, BadgeCheck, Columns3, Activity, ArrowUpRight, ScrollText, ChevronDown } from "lucide-react";
import AmbientShell from "./AmbientShell";
import { ink, paper, paperDeep, brass, seal, line, sans, serif } from "./theme";

/**
 * Introduction ("exhibition") page for Standard Setu — cinematic full-bleed
 * hero in the paper/ink/brass manuscript identity, followed by editorial
 * sections: what an Indian Standard is, why to follow it, and what happens
 * if you don't. Everything is CSS/SVG texture — no external assets.
 */

const FACTS = [
  { n: "130", label: "Indian Standards in the curated registry" },
  { n: "12", label: "product categories, steel to safety" },
  { n: "12h", label: "session data lifetime — nothing is stored" },
];

const TABS = [
  { key: "recommend", label: "Recommend", Icon: Search },
  { key: "explore", label: "Explore", Icon: Compass },
  { key: "verify", label: "Verify", Icon: BadgeCheck },
  { key: "compare", label: "Compare", Icon: Columns3 },
  { key: "monitor", label: "Monitor", Icon: Activity },
];

function Reveal({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) {
  const reduce = useReducedMotion() ?? false;
  // `initial` values must be identical on server and client (framer reads the
  // reduced-motion query synchronously on the client but not on the server,
  // so reduce-dependent initial values cause hydration mismatches). The
  // reduced-motion preference is honoured at animation time via `transition`.
  return (
    <motion.div
      initial={{ opacity: 0, y: 26 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "0px 0px -30px 0px" }}
      transition={{ duration: reduce ? 0.01 : 0.7, delay: reduce ? 0 : delay, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </motion.div>
  );
}

function SectionHeading({ eyebrow, title }: { eyebrow: string; title: string }) {
  return (
    <div className="mb-8">
      <p className="mb-2 text-[10.5px] font-semibold uppercase tracking-[0.22em]" style={{ color: brass, fontFamily: sans }}>
        {eyebrow}
      </p>
      <h2 className="max-w-[24ch] text-[clamp(26px,3.4vw,44px)] font-semibold leading-[1.05] tracking-[-0.02em]" style={{ color: ink, fontFamily: serif }}>
        {title}
      </h2>
    </div>
  );
}

export default function IntroPanel({ onEnter, onJump }: { onEnter: () => void; onJump: (tab: string) => void }) {
  const reduce = useReducedMotion();

  // Scroll-linked hero photo: crisp on arrival, blurring away as the reader
  // scrolls into the manuscript — like a plate slipping out of focus.
  const photoScrub = useMotionValue(0);
  useEffect(() => {
    const onScroll = () => {
      photoScrub.set(Math.min(1, Math.max(0, window.scrollY / (window.innerHeight * 0.85))));
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [photoScrub]);
  const blurPx = useTransform(photoScrub, [0, 1], [0, 18]);
  const photoFilter = useMotionTemplate`blur(${blurPx}px) saturate(1.12)`;
  const photoScale = useTransform(photoScrub, [0, 1], [1.04, 1.14]);
  // The plate blurs but does not vanish — the waves show through it slightly.
  const photoOpacity = useTransform(photoScrub, [0, 1], [1, 0.55]);

  // "What is an IS" — tabbed detail panes
  const [detail, setDetail] = useState<"spec" | "cert" | "wording">("spec");
  const detailContent: Record<string, { title: string; body: string }> = {
    spec: {
      title: "The specification",
      body: "Each IS fixes the product's dimensions, material grades, strength grades and test methods. 'IS 1786' is not a brand — it is the exact definition of high-strength deformed steel bars: what chemistry they may have, how they are tested, and what the test certificate must state.",
    },
    cert: {
      title: "The certification",
      body: "For products on the mandatory list, the manufacturer must hold a BIS licence and mark the product with the ISI mark. The standard number tells you whether certification is mandatory for your item — and therefore what you are legally required to check before accepting a delivery.",
    },
    wording: {
      title: "The tender wording",
      body: "Tender documents cite standards verbatim: 'Supply shall conform to IS 1786:2008 (as amended) — High Strength Deformed Steel Bars and Wires for Concrete Reinforcement'. One wrong edition or a missing part number, and the clause is open to challenge.",
    },
  };

  return (
    <div style={{ color: ink }}>
      {/* ---------------- HERO ---------------- */}
      <section
        // Full-bleed from the very top — the header steps aside on Home and
        // only the translucent dock floats above the photo.
        className="relative z-10 flex min-h-[100vh] flex-col items-center justify-center overflow-hidden px-6 text-center"
      >
        {/* The photo as the first screen's SHEET: a framed plate floating over
            the wavy canvas (visible around its edges). Crisp on arrival,
            blurring away as the reader scrolls — the waves stay behind it. */}
        <div
          aria-hidden
          className="absolute inset-[14px] overflow-hidden rounded-[22px]"
          style={{ border: `1px solid ${brass}45`, boxShadow: "0 30px 80px rgba(10,14,24,0.35), inset 0 1px 0 rgba(255,255,255,0.5)" }}
        >
          <motion.div
            className="absolute -inset-3"
            style={{
              backgroundImage: "url(/bis-hero.png)",
              backgroundSize: "cover",
              backgroundPosition: "center",
              filter: photoFilter,
              scale: photoScale,
              opacity: photoOpacity,
            }}
          />
          {/* Faint paper veil inside the plate for text contrast */}
          <div
            className="absolute inset-0"
            style={{
              background: "linear-gradient(to bottom, rgba(241,239,230,0.24) 0%, rgba(241,239,230,0.05) 36%, rgba(241,239,230,0.14) 70%, rgba(241,239,230,0.34) 100%)",
            }}
          />
        </div>

        {/* Brand lockup */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: reduce ? 0.01 : 0.7, delay: reduce ? 0 : 0.1, ease: "easeOut" }}
          className="relative z-10 mb-7 flex flex-col items-center gap-2.5"
        >
          <div className="flex items-center gap-2.5">
            <img src="/logo.png" alt="" width={22} height={22} style={{ flexShrink: 0 }} />
            <span className="text-[15px] font-medium uppercase tracking-[0.28em] pl-[0.28em]" style={{ color: ink, fontFamily: sans }}>
              Standard Setu
            </span>
          </div>
          <span className="text-[10px] font-medium uppercase tracking-[0.34em] pl-[0.34em]" style={{ color: "rgba(28,36,56,0.62)", fontFamily: sans }}>
            SIH26108 · A standards engine for procurement
          </span>
        </motion.div>

        {/* Two-line headline */}
        <motion.h1
          initial={{ opacity: 0, y: 26 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: reduce ? 0.01 : 0.85, delay: reduce ? 0 : 0.24, ease: "easeOut" }}
          className="relative z-10 m-0 uppercase"
          style={{ fontFamily: serif, color: ink, textShadow: "0 1px 14px rgba(241,239,230,0.85), 0 2px 34px rgba(28,36,56,0.12)" }}
        >
          <span className="block font-normal leading-[1] tracking-[0.02em]" style={{ fontSize: "clamp(2.6rem, 6.5vw, 5rem)" }}>
            Every tender
          </span>
          <span className="block font-bold leading-[0.98] tracking-[0.01em]" style={{ fontSize: "clamp(2.4rem, 6.2vw, 4.8rem)" }}>
            rests on a standard
          </span>
        </motion.h1>

        {/* Italic subtext */}
        <motion.p
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: reduce ? 0.01 : 0.8, delay: reduce ? 0 : 0.42, ease: "easeOut" }}
          className="relative z-10 mx-auto mt-6 max-w-[520px] italic"
          style={{ fontFamily: serif, fontSize: 17.5, lineHeight: 1.55, color: "rgba(28,36,56,0.82)" }}
        >
          Learn what an Indian Standard is, why tenders lean on it, and what it costs to ignore one — then let the engine find yours.
        </motion.p>

        {/* Elliptical CTA — true ellipse, Glacier-style */}
        <motion.button
          onClick={onEnter}
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: reduce ? 0.01 : 0.8, delay: reduce ? 0 : 0.58, ease: "easeOut" }}
          whileHover={reduce ? undefined : { scale: 1.05, boxShadow: "0 0 0 2px rgba(169,114,47,0.65), 0 18px 46px rgba(28,36,56,0.38)" }}
          whileTap={reduce ? undefined : { scale: 0.96 }}
          className="relative z-10 mt-10 uppercase"
          style={{
            padding: "22px 58px",
            borderRadius: "50%",
            border: `1px solid ${ink}`,
            color: paper,
            background: ink,
            fontSize: 12,
            fontWeight: 600,
            letterSpacing: "0.22em",
            fontFamily: sans,
            cursor: "pointer",
            boxShadow: "0 0 0 1px rgba(169,114,47,0.55), 0 14px 34px rgba(28,36,56,0.3)",
          }}
        >
          Enter the engine
        </motion.button>

        {/* Hero footer strip */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: reduce ? 0.01 : 0.8, delay: reduce ? 0 : 0.8 }}
          className="absolute inset-x-0 bottom-0 z-10 flex items-center justify-between px-8 pb-6 md:px-12"
        >
          <div className="hidden items-center gap-2 md:flex" style={{ fontFamily: sans }}>
            {FACTS.map((f) => (
              <span key={f.label} className="text-[10px] uppercase tracking-[0.14em]" style={{ color: "rgba(28,36,56,0.55)" }}>
                <b style={{ color: brass, fontSize: 12.5 }}>{f.n}</b>&nbsp; {f.label}
              </span>
            ))}
          </div>
        </motion.div>

        {/* Scroll cue — a real button: glides down to the manuscript */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: reduce ? 0.01 : 0.8, delay: reduce ? 0 : 1.1 }}
          className="absolute inset-x-0 bottom-20 z-10 flex justify-center px-4"
        >
          {/* CSS animation keeps server/client markup identical; the media
              query disables it under reduced motion. */}
          <style>{`@media (prefers-reduced-motion: no-preference) { @keyframes setu-bob { 0%, 100% { transform: translateY(-1px); } 50% { transform: translateY(3px); } } .setu-bob { animation: setu-bob 1.4s ease-in-out infinite; } }`}</style>
          <motion.button
            type="button"
            aria-label="Go to the manuscript — What is an Indian Standard?"
            onClick={() =>
              document.getElementById("manuscript")?.scrollIntoView({
                behavior: reduce ? "auto" : "smooth",
                block: "start",
              })
            }
            whileHover={reduce ? undefined : { scale: 1.06 }}
            whileTap={reduce ? undefined : { scale: 0.94 }}
            className="flex items-center gap-2 rounded-full px-4 py-2"
            style={{
              background: "rgba(28,36,56,0.62)",
              border: "1px solid rgba(241,239,230,0.45)",
              backdropFilter: "blur(14px)",
              WebkitBackdropFilter: "blur(14px)",
              boxShadow: "0 8px 24px rgba(28,36,56,0.3)",
              cursor: "pointer",
            }}
          >
            <span
              style={{
                fontSize: 10.5,
                fontWeight: 600,
                letterSpacing: "0.22em",
                textTransform: "uppercase",
                color: paper,
                fontFamily: sans,
                whiteSpace: "nowrap",
              }}
            >
              Scroll to know more
            </span>
            <ChevronDown className="setu-bob" size={13} style={{ color: "#c99a55", flexShrink: 0 }} />
          </motion.button>
        </motion.div>
      </section>

      {/* Below the fold = the other tabs' interface: the wavy-lines ink
          canvas as background, with the manuscript sheet floating over it.
          The BIS photo stays up in the hero — crisp on arrival, blurring as
          the reader scrolls away from it. */}
      <AmbientShell mode="raw">
      <div id="manuscript" className="relative z-10 mx-auto w-full max-w-[1040px] px-4 pb-16" style={{ scrollMarginTop: 18 }}>
        <div
          className="rounded-[26px] p-[clamp(16px,2.6vw,34px)]"
          style={{
            background: "rgba(247,245,238,0.96)",
            border: "1px solid rgba(201,195,171,0.9)",
            boxShadow: "0 30px 80px rgba(10,14,24,0.4), inset 0 1px 0 rgba(255,255,255,0.6)",
            backdropFilter: "blur(10px)",
            WebkitBackdropFilter: "blur(10px)",
          }}
        >

      {/* ---------------- WHAT IS AN INDIAN STANDARD ---------------- */}
      <section className="px-2 py-10 md:py-14">
        <Reveal>
          <SectionHeading eyebrow="The manuscript" title="What is an Indian Standard?" />
        </Reveal>
        <div className="grid gap-10 md:grid-cols-[1.1fr_0.9fr]">
          <Reveal delay={0.08}>
            <div className="space-y-4 text-[15px] leading-[1.7]" style={{ color: "rgba(28,36,56,0.85)", fontFamily: sans }}>
              <p>
                An <b>Indian Standard (IS)</b> is a published technical specification maintained by the{" "}
                <b>Bureau of Indian Standards</b> — the national standards body under the BIS Act, 2016. Each standard
                carries a number (<i>IS 1786</i>), an edition year, and sometimes amendments or parts.
              </p>
              <p>
                It is the single authoritative answer to &ldquo;what exactly counts as good steel / cement / cable /
                pump in India&rdquo;. Contracts, tender documents, and quality inspectors all refer to the same
                document — so everyone is arguing from the same manuscript, not from opinion.
              </p>
            </div>
          </Reveal>
          <Reveal delay={0.16}>
            <div className="rounded-2xl p-6" style={{ background: paperDeep, border: `1px solid ${line}` }}>
              {/* anatomy of an IS number */}
              <p className="mb-4 text-[10px] font-semibold uppercase tracking-[0.18em]" style={{ color: "rgba(28,36,56,0.6)", fontFamily: sans }}>
                Anatomy of a citation
              </p>
              <div style={{ fontFamily: serif }} className="flex flex-wrap items-baseline gap-x-1.5 text-[clamp(18px,2vw,26px)]">
                <span style={{ color: brass }}>IS</span>
                <span style={{ color: ink }}>1786</span>
                <span style={{ color: "rgba(28,36,56,0.6)" }}>:</span>
                <span style={{ color: ink }}>2008</span>
                <span className="text-[13px] italic" style={{ color: "rgba(28,36,56,0.6)" }}>(as amended — A.2, 2018)</span>
              </div>
              <div className="mt-4 space-y-2 text-[11.5px]" style={{ fontFamily: sans, color: "rgba(28,36,56,0.7)" }}>
                <p><b style={{ color: brass }}>IS</b> — prefix, Indian Standard</p>
                <p><b style={{ color: ink }}>1786</b> — the subject number: high-strength deformed steel bars</p>
                <p><b style={{ color: ink }}>2008</b> — the edition; the current one at the time of citation</p>
                <p><b style={{ color: "rgba(28,36,56,0.6)" }}>(as amended)</b> — amendments issued after the edition</p>
              </div>
            </div>
          </Reveal>
        </div>

        {/* tabbed detail */}
        <Reveal delay={0.1}>
          <div className="mt-10 rounded-2xl" style={{ border: `1px solid ${line}`, background: "rgba(255,255,255,0.5)" }}>
            <div className="flex flex-wrap gap-1 border-b p-2" style={{ borderColor: line }}>
              {(["spec", "cert", "wording"] as const).map((k) => (
                <button
                  key={k}
                  onClick={() => setDetail(k)}
                  className="rounded-full px-4 py-2 text-[12px] font-medium transition-colors"
                  style={{
                    fontFamily: sans,
                    border: `1px solid ${detail === k ? ink : line}`,
                    background: detail === k ? ink : "transparent",
                    color: detail === k ? paper : ink,
                    cursor: "pointer",
                  }}
                >
                  {detailContent[k].title}
                </button>
              ))}
            </div>
            <p className="p-6 text-[14px] leading-[1.7]" style={{ fontFamily: sans, color: "rgba(28,36,56,0.85)" }}>
              {detailContent[detail].body}
            </p>
          </div>
        </Reveal>
      </section>

      {/* ---------------- WHY FOLLOW IT (ink plate inside the sheet) ---------------- */}
      <section className="relative my-6 overflow-hidden rounded-[20px] px-6 py-12 md:py-14" style={{ background: ink }}>
        <div aria-hidden className="pointer-events-none absolute inset-0" style={{ background: "repeating-linear-gradient(0deg, rgba(241,239,230,0.05) 0px, rgba(241,239,230,0.05) 1px, transparent 1px, transparent 9px)" }} />
        <div className="relative mx-auto max-w-5xl">
          <Reveal>
            <p className="mb-2 text-[10.5px] font-semibold uppercase tracking-[0.22em]" style={{ color: "#c99a55", fontFamily: sans }}>
              The reason
            </p>
            <h2 className="max-w-[26ch] text-[clamp(26px,3.4vw,44px)] font-semibold leading-[1.05]" style={{ color: paper, fontFamily: serif }}>
              Why tenders are built on standards
            </h2>
          </Reveal>
          <div className="mt-12 grid gap-5 md:grid-cols-3">
            {[
              {
                Icon: Scale,
                t: "Equal footing for every bidder",
                b: "When the spec says IS 1786:2008, a small fabricator and a large mill compete on the same measurable terms — grades, tolerances, test methods. Procurement stays defensible.",
              },
              {
                Icon: BookOpen,
                t: "A common technical language",
                b: "The engineer in the field, the buyer in the office, and the auditor years later all point to the same clause. No translation loss between what was asked and what was delivered.",
              },
              {
                Icon: ScrollText,
                t: "Quality you can enforce",
                b: "Standards define how conformance is tested and certified. That is what turns a promise of quality into a checkable clause — and gives you grounds for rejection when it fails.",
              },
            ].map(({ Icon, t, b }, i) => (
              <Reveal key={t} delay={0.08 * i}>
                <div className="h-full rounded-2xl p-6" style={{ background: "rgba(241,239,230,0.07)", border: "1px solid rgba(241,239,230,0.14)" }}>
                  <Icon size={22} style={{ color: "#c99a55" }} />
                  <h3 className="mt-4 text-[17px] font-semibold" style={{ color: paper, fontFamily: serif }}>{t}</h3>
                  <p className="mt-2.5 text-[13px] leading-[1.65]" style={{ color: "rgba(241,239,230,0.75)", fontFamily: sans }}>{b}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------- WHAT IF YOU DON'T ---------------- */}
      <section className="px-2 py-10 md:py-12">
        <Reveal>
          <SectionHeading eyebrow="The risk" title="What if you don't follow it?" />
        </Reveal>
        <div className="grid gap-5 md:grid-cols-2">
          {[
            {
              Icon: FileWarning,
              t: "Tender challenges and re-tenders",
              b: "A vague or wrong citation — wrong edition, missing part, unnamed amendment — is the classic ground for challenge. The procuring agency can be forced to cancel and re-tender, costing months.",
            },
            {
              Icon: FileWarning,
              t: "Non-conforming material accepted",
              b: "Without a standard to test against, substandard steel, cable or cement can pass on trust. Failures surface later as structural defects, short circuits, or collapsed schedules — with the contract silent on recourse.",
            },
            {
              Icon: FileWarning,
              t: "Legal exposure under the BIS Act",
              b: "For notified products, using or selling non-ISI-marked goods is an offence. The buyer who ignored the mandatory certification shares the liability for what entered the project.",
            },
            {
              Icon: FileWarning,
              t: "Wasted public money",
              b: "The end cost of skipping the standard is always higher: rework, replacement, litigation, and the audit findings that follow. The standard is cheaper than any of its alternatives.",
            },
          ].map(({ Icon, t, b }, i) => (
            <Reveal key={t} delay={0.06 * i}>
              <div className="flex h-full items-start gap-4 rounded-2xl p-6" style={{ background: "rgba(255,255,255,0.55)", border: `1px solid ${line}` }}>
                <div className="h-fit shrink-0 rounded-full p-2.5" style={{ background: "rgba(138,51,36,0.08)", border: `1px solid ${seal}33` }}>
                  <Icon size={18} style={{ color: seal }} />
                </div>
                <div>
                  <h3 className="text-[16px] font-semibold" style={{ color: ink, fontFamily: serif }}>{t}</h3>
                  <p className="mt-2 text-[13px] leading-[1.65]" style={{ color: "rgba(28,36,56,0.75)", fontFamily: sans }}>{b}</p>
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ---------------- CLOSING CTA ---------------- */}
      <section className="relative overflow-hidden px-2 py-10 text-center md:py-12">
        <Reveal>
          <div className="mx-auto flex max-w-2xl flex-col items-center">
            <p className="text-[10.5px] font-semibold uppercase tracking-[0.22em]" style={{ color: brass, fontFamily: sans }}>
              Now that you know why
            </p>
            <h2 className="mt-3 text-[clamp(24px,3vw,40px)] font-semibold leading-[1.08]" style={{ color: ink, fontFamily: serif }}>
              Let the engine find your standard
            </h2>
            <p className="mt-4 max-w-[46ch] text-[14px] leading-[1.65]" style={{ color: "rgba(28,36,56,0.72)", fontFamily: sans }}>
              Describe the product in plain language — get the IS number, the edition to cite, the certification to check, and tender-ready wording.
            </p>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              {TABS.filter((t) => t.key !== "recommend").map(({ key, label, Icon }) => (
                <button
                  key={key}
                  onClick={() => onJump(key)}
                  className="flex items-center gap-2 rounded-full px-4 py-2 text-[12px] font-medium transition-opacity hover:opacity-80"
                  style={{ fontFamily: sans, border: `1px solid ${line}`, color: ink, background: "rgba(255,255,255,0.5)", cursor: "pointer" }}
                >
                  <Icon size={13} /> {label} <ArrowUpRight size={12} />
                </button>
              ))}
              <button
                onClick={onEnter}
                className="flex items-center gap-2 rounded-full px-5 py-2.5 text-[12px] font-semibold uppercase tracking-[0.14em] transition-opacity hover:opacity-85"
                style={{ fontFamily: sans, background: ink, color: paper, border: "none", cursor: "pointer" }}
              >
                <Search size={13} /> Ask the engine
              </button>
            </div>
          </div>
        </Reveal>
      </section>

        </div>{/* /sheet */}
      </div>{/* /sheet-column */}
      </AmbientShell>
    </div>
  );
}
