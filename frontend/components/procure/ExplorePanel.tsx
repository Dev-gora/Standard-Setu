"use client";

import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { BookOpen, ExternalLink, Search, ShieldAlert, ShieldCheck } from "lucide-react";
import { browseStandards, type BrowseResponse, type BrowseStandard } from "@/lib/api";
import { ink, paper, line, brass, seal, good, sans, serif } from "./theme";

/**
 * Explore tab — for people who don't know what they need:
 *  1. "What is IS 1786?" — search any number/keyword for a plain overview
 *     with links to the actual documents (Internet Archive mirror).
 *  2. Category grid — 12 procurement categories as generated logo-mark tiles;
 *     click to see every standard in that category.
 *
 * Category art: deterministic generated SVG logo-marks (seeded per category,
 * theme palette) — crisp at any size, no external AI-image API calls, which
 * also keeps the T&C privacy promise ("no data leaves this application").
 */

const CATEGORY_ART: Record<string, { bg: string; fg: string; icon: "beam" | "cube" | "layers" | "drops" | "wave" | "bolt" | "helmet" | "grain" | "pipe" | "brush" | "chair" | "plank" }> = {
  "Cement & Concrete": { bg: "#1c2438", fg: "#f1efe6", icon: "cube" },
  "Steel & Metal Products": { bg: "#a9722f", fg: "#f1efe6", icon: "beam" },
  "Bricks & Clay": { bg: "#8a3324", fg: "#f1efe6", icon: "layers" },
  "Timber & Wood": { bg: "#3f6b4e", fg: "#f1efe6", icon: "plank" },
  "Water Supply & Pipes": { bg: "#2c5a70", fg: "#f1efe6", icon: "pipe" },
  "Paints & Coatings": { bg: "#7a4a8c", fg: "#f1efe6", icon: "brush" },
  "Plastic Products": { bg: "#35635c", fg: "#f1efe6", icon: "drops" },
  "Electrical & Wiring": { bg: "#b07d2b", fg: "#1c2438", icon: "bolt" },
  "Safety Equipment": { bg: "#8a3324", fg: "#f6ecda", icon: "helmet" },
  "Aggregates & Sand": { bg: "#5c5843", fg: "#f1efe6", icon: "grain" },
  Furniture: { bg: "#4a4636", fg: "#f1efe6", icon: "chair" },
  Adhesives: { bg: "#31435c", fg: "#f1efe6", icon: "wave" },
};

const FALLBACK_ART = { bg: "#4a4636", fg: "#f1efe6", icon: "cube" as const };

/** Deterministic seeded SVG mark per category — a 'logo' generated from its name. */
function CategoryMark({ name, size = 56 }: { name: string; size?: number }) {
  const art = CATEGORY_ART[name] || FALLBACK_ART;
  let seed = 0;
  for (let i = 0; i < name.length; i++) seed = (seed * 31 + name.charCodeAt(i)) % 9973;
  const bars = Array.from({ length: 5 }, (_, i) => {
    const h = 8 + ((seed >> i) % 20);
    return { h, x: i * (size / 5 + 1.5) };
  });

  return (
    <div
      className="flex items-center justify-center rounded-xl"
      style={{ width: size + 20, height: size + 20, background: art.bg, flexShrink: 0 }}
    >
      <svg width={size} height={size} viewBox="0 0 56 56" fill="none" aria-hidden="true">
        {art.icon === "cube" && (
          <g stroke={art.fg} strokeWidth="2.4" fill="none">
            <path d="M28 8 L46 18 V38 L28 48 L10 38 V18 Z" />
            <path d="M28 8 V28 M28 28 L46 18 M28 28 L10 18" opacity="0.65" />
          </g>
        )}
        {art.icon === "beam" && (
          <g stroke={art.fg} strokeWidth="2.4" fill="none">
            <path d="M8 40 H48 M14 40 V16 H42 V40 M20 16 V40 M28 16 V40 M36 16 V40" />
          </g>
        )}
        {art.icon === "layers" && (
          <g stroke={art.fg} strokeWidth="2.4" fill="none">
            <path d="M28 8 L48 20 L28 32 L8 20 Z" />
            <path d="M8 30 L28 42 L48 30" opacity="0.7" />
            <path d="M8 38 L28 50 L48 38" opacity="0.4" />
          </g>
        )}
        {art.icon === "plank" && (
          <g stroke={art.fg} strokeWidth="2.4" fill="none">
            <rect x="8" y="20" width="40" height="16" rx="2" />
            <path d="M14 20 V36 M22 20 V36 M34 20 V36 M42 20 V36" opacity="0.6" />
          </g>
        )}
        {art.icon === "pipe" && (
          <g stroke={art.fg} strokeWidth="2.4" fill="none">
            <path d="M10 22 H34 A12 12 0 0 1 34 46 H10" />
            <path d="M10 30 H34 A4 4 0 0 1 34 38 H10" opacity="0.6" />
          </g>
        )}
        {art.icon === "brush" && (
          <g stroke={art.fg} strokeWidth="2.4" fill="none">
            <path d="M36 8 L48 20 L24 44 L8 48 L12 32 Z" />
            <path d="M32 12 L44 24" opacity="0.6" />
          </g>
        )}
        {art.icon === "drops" && (
          <g stroke={art.fg} strokeWidth="2.4" fill="none">
            <path d="M20 8 C20 8 10 22 10 30 A10 10 0 0 0 30 30 C30 22 20 8 20 8 Z" />
            <path d="M40 24 C40 24 34 32 34 37 A6 6 0 0 0 46 37 C46 32 40 24 40 24 Z" opacity="0.7" />
          </g>
        )}
        {art.icon === "bolt" && (
          <g stroke={art.fg} strokeWidth="2.4" fill="none">
            <path d="M30 6 L14 32 H26 L22 50 L42 22 H30 L34 6 Z" strokeLinejoin="round" />
          </g>
        )}
        {art.icon === "helmet" && (
          <g stroke={art.fg} strokeWidth="2.4" fill="none">
            <path d="M10 34 A18 18 0 0 1 46 34" />
            <path d="M6 34 H50 M18 34 V22 M28 34 V16 M38 34 V22" />
          </g>
        )}
        {art.icon === "grain" && (
          <g fill={art.fg}>
            {bars.map((b, i) => (
              <rect key={i} x={10 + i * 8} y={38 - b.h} width="5" height={b.h} rx="2.5" opacity={0.55 + i * 0.09} />
            ))}
            <circle cx="42" cy="14" r="5" opacity="0.8" />
          </g>
        )}
        {art.icon === "chair" && (
          <g stroke={art.fg} strokeWidth="2.4" fill="none">
            <path d="M16 8 V34 H44 M16 34 V48 M44 34 V48 M24 8 H44 V22 H24 Z" />
          </g>
        )}
        {art.icon === "wave" && (
          <g stroke={art.fg} strokeWidth="2.4" fill="none">
            <path d="M8 20 Q18 10 28 20 T48 20" />
            <path d="M8 32 Q18 22 28 32 T48 32" opacity="0.7" />
            <path d="M8 44 Q18 34 28 44 T48 44" opacity="0.4" />
          </g>
        )}
      </svg>
    </div>
  );
}

export default function ExplorePanel({ onOpenStandard }: { onOpenStandard: (code: string) => void }) {
  const [data, setData] = useState<BrowseResponse | null>(null);
  const [query, setQuery] = useState("");
  const [activeCat, setActiveCat] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    browseStandards()
      .then(setData)
      .catch(() => setError("Could not load the registry — is the backend running?"));
  }, []);

  const results = useMemo(() => {
    if (!data) return [];
    const q = query.trim().toLowerCase();
    let list = data.standards;
    if (activeCat) list = list.filter((s) => s.category === activeCat);
    if (q) {
      list = list.filter(
        (s) =>
          s.code.toLowerCase().includes(q.replace(/^is\s*/, "")) ||
          s.title.toLowerCase().includes(q)
      );
    }
    return list;
  }, [data, query, activeCat]);

  const exactHit = useMemo(() => {
    if (!data || !query.trim()) return null;
    const q = query.trim().toLowerCase().replace(/^is\s*/, "").replace(/:.*$/, "");
    return data.standards.find((s) => s.code.toLowerCase().replace(/^is\s*/, "") === q) || null;
  }, [data, query]);

  if (error) return <p style={{ fontSize: 13.5, color: seal, fontFamily: sans }}>{error}</p>;
  if (!data) return <p style={{ fontSize: 14, color: "#6b6650", fontFamily: sans }}>Loading the registry…</p>;

  return (
    <div>
      <h2 style={{ fontSize: 19, color: ink, marginBottom: 4, fontWeight: 400 }}>Explore Indian Standards</h2>
      <p style={{ fontSize: 13, color: "#6b6650", marginBottom: 16, fontFamily: sans }}>
        Know the number? Search it. Don&apos;t? Browse by category. Every standard links to the
        actual public document.
      </p>

      {/* Search any number / keyword */}
      <div className="flex items-center gap-2 mb-6" style={{ position: "relative" }}>
        <Search size={15} style={{ color: "#8b8570", position: "absolute", left: 12 }} />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search a number (1786) or keyword (steel bars)…"
          style={{
            width: "100%",
            border: `1px solid ${line}`,
            borderRadius: 4,
            background: "rgba(255,255,255,0.6)",
            padding: "10px 12px 10px 34px",
            fontSize: 14,
            color: ink,
            fontFamily: sans,
          }}
        />
      </div>

      {/* Exact hit — the 'what is 1786?' overview card */}
      {exactHit && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          style={{ border: `1px solid ${brass}`, borderRadius: 6, background: "rgba(255,255,255,0.65)" }}
          className="p-5 mb-6"
        >
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <div style={{ fontSize: 24, fontFamily: serif, color: brass }}>{exactHit.code}</div>
              <div style={{ fontSize: 15, color: ink, marginTop: 2 }}>{exactHit.title}</div>
              <div style={{ fontSize: 12.5, color: "#6b6650", fontFamily: sans, marginTop: 6 }}>
                {exactHit.category} · Edition {exactHit.latest_version}
                {exactHit.amendment ? ` — ${exactHit.amendment}` : ""}
              </div>
              <div
                className="flex items-center gap-1.5 mt-2"
                style={{ fontSize: 12.5, fontFamily: sans, color: exactHit.certification.mandatory ? seal : good }}
              >
                {exactHit.certification.mandatory ? <ShieldAlert size={13} /> : <ShieldCheck size={13} />}
                BIS certification {exactHit.certification.mandatory
                  ? (exactHit.certification.verification_status === "VERIFIED" ? "is mandatory (QCO-backed)" : "is listed as mandatory (unverified)")
                  : "is not mandatory"}
                {exactHit.certification.scheme ? ` (${exactHit.certification.scheme})` : ""}
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <a
                href={exactHit.archive_link.url}
                target="_blank"
                rel="noreferrer"
                style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 13, color: brass, fontFamily: sans, textDecoration: "none", border: `1px solid ${brass}`, borderRadius: 4, padding: "7px 12px" }}
              >
                Read the actual document <ExternalLink size={12} />
              </a>
              <button
                onClick={() => onOpenStandard(exactHit.code)}
                style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 13, color: ink, fontFamily: sans, border: `1px solid ${line}`, borderRadius: 4, padding: "7px 12px", background: "rgba(255,255,255,0.5)", cursor: "pointer" }}
              >
                <BookOpen size={12} /> Full details
              </button>
            </div>
          </div>
        </motion.div>
      )}

      {/* Category grid — logo-mark tiles */}
      {!activeCat && !query && (
        <div className="grid gap-3 mb-6" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))" }}>
          {Object.entries(data.categories).map(([cat, count], i) => (
            <motion.button
              key={cat}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04 }}
              onClick={() => setActiveCat(cat)}
              className="flex items-center gap-3 p-3 text-left"
              style={{ border: `1px solid ${line}`, borderRadius: 10, background: "rgba(255,255,255,0.5)", cursor: "pointer" }}
            >
              <CategoryMark name={cat} size={34} />
              <div>
                <div style={{ fontSize: 13, color: ink, fontFamily: sans, lineHeight: 1.25 }}>{cat}</div>
                <div style={{ fontSize: 11, color: "#8b8570", fontFamily: sans }}>{count} standards</div>
              </div>
            </motion.button>
          ))}
        </div>
      )}

      {/* Category open view */}
      {activeCat && (
        <div className="mb-5">
          <button
            onClick={() => setActiveCat(null)}
            style={{ fontSize: 12.5, color: "#8b8570", background: "none", border: "none", cursor: "pointer", marginBottom: 12, fontFamily: sans }}
          >
            ← All categories
          </button>
          <div className="flex items-center gap-3 mb-4">
            <CategoryMark name={activeCat} size={40} />
            <div>
              <div style={{ fontSize: 17, color: ink, fontFamily: serif }}>{activeCat}</div>
              <div style={{ fontSize: 12, color: "#8b8570", fontFamily: sans }}>
                {results.length} standard{results.length === 1 ? "" : "s"}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Result list */}
      {results.length > 0 && (
        <div style={{ borderTop: `1px solid ${ink}` }}>
          {results.slice(0, 60).map((s) => (
            <div key={s.code} className="flex items-center justify-between gap-3 py-2.5" style={{ borderBottom: `1px solid ${line}` }}>
              <button
                onClick={() => onOpenStandard(s.code)}
                className="min-w-0 text-left"
                style={{ background: "none", border: "none", cursor: "pointer", padding: 0 }}
              >
                <span style={{ fontSize: 14, fontFamily: serif, color: brass, textDecoration: "underline", textDecorationColor: "rgba(169,114,47,0.4)" }}>{s.code}</span>
                <span style={{ fontSize: 13.5, color: ink }}> — {s.title}</span>
                <div style={{ fontSize: 11.5, color: "#8b8570", fontFamily: sans }}>
                  {s.latest_version}{s.amendment ? ` — ${s.amendment}` : ""}
                  {s.certification.mandatory ? " · certification mandatory" : ""}
                </div>
              </button>
              <a
                href={s.archive_link.url}
                target="_blank"
                rel="noreferrer"
                style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11.5, color: brass, fontFamily: sans, textDecoration: "none", flexShrink: 0 }}
              >
                source <ExternalLink size={10} />
              </a>
            </div>
          ))}
          {results.length > 60 && (
            <p style={{ fontSize: 12, color: "#8b8570", fontFamily: sans, marginTop: 8 }}>
              Showing 60 of {results.length} — refine the search to narrow it down.
            </p>
          )}
        </div>
      )}

      {query && results.length === 0 && !exactHit && (
        <p style={{ fontSize: 14, color: "#6b6650", fontFamily: sans }}>
          Nothing in the registry matches &quot;{query}&quot;. Try a number (&quot;1786&quot;) or a material word (&quot;cement&quot;, &quot;steel&quot;).
        </p>
      )}
    </div>
  );
}
