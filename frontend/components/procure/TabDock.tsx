"use client";

import { motion, useReducedMotion } from "framer-motion";
import { Home, Search, Compass, BadgeCheck, Columns3, Activity } from "lucide-react";
import { ink, paper, sans } from "./theme";

/**
 * Floating glass icon dock for the workflow tabs (Glacier-style pill with a
 * sliding active highlight). Sticks to the top while long pages scroll.
 */
const ITEMS = [
  { key: "home", label: "Home", Icon: Home },
  { key: "recommend", label: "Recommend", Icon: Search },
  { key: "explore", label: "Explore", Icon: Compass },
  { key: "verify", label: "Verify", Icon: BadgeCheck },
  { key: "compare", label: "Compare", Icon: Columns3 },
  { key: "monitor", label: "Monitor", Icon: Activity },
] as const;

export type TabKey = (typeof ITEMS)[number]["key"];

export default function TabDock({
  active,
  onChange,
  floating = false,
}: {
  active: string;
  onChange: (key: TabKey) => void;
  /** Home mode: fixed translucent glass floating OVER the hero photo. */
  floating?: boolean;
}) {
  // Note: keep `animate` unconditional — framer applies `initial` on mount
  // before the reduced-motion media query resolves, so a conditional animate
  // would leave the dock stuck at opacity 0.
  const reduce = useReducedMotion();

  return (
    <div
      className={floating ? "fixed inset-x-0 top-3 z-40 flex justify-center px-4" : "sticky top-2 z-40 flex justify-center px-4 py-2.5"}
    >
      <motion.nav
        initial={{ opacity: 0, y: reduce ? 0 : -14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: reduce ? 0.01 : 0.6, ease: "easeOut" }}
        className="flex max-w-full items-center gap-1 overflow-x-auto rounded-full px-2.5 py-[5px]"
        style={{
          // Floating (over the photo): Glacier glass — mostly translucent, a
          // whisper of ink so it reads against the sky, fully blurred behind.
          // Docked (other tabs): frosted paper over the plain background.
          background: floating ? "rgba(28,36,56,0.42)" : "rgba(255,255,255,0.55)",
          border: floating ? "1px solid rgba(255,255,255,0.32)" : "1px solid rgba(28,36,56,0.14)",
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)",
          boxShadow: floating
            ? "0 12px 40px rgba(28,36,56,0.28), inset 0 1px 0 rgba(255,255,255,0.28)"
            : "0 12px 40px rgba(28,36,56,0.14), inset 0 1px 0 rgba(255,255,255,0.5)",
          scrollbarWidth: "none",
        }}
      >
        {ITEMS.map(({ key, label, Icon }) => {
          const isActive = active === key;
          return (
            <button
              key={key}
              onClick={() => onChange(key)}
              aria-label={label}
              className="relative flex shrink-0 items-center justify-center gap-1.5 rounded-full px-3.5 py-[7px]"
              style={{
                border: "none",
                background: "transparent",
                cursor: "pointer",
                color: isActive ? paper : floating ? "rgba(241,239,230,0.82)" : "rgba(28,36,56,0.62)",
                transition: "color 0.2s ease",
                fontFamily: sans,
              }}
            >
              {isActive && (
                <motion.span
                  layoutId={reduce ? undefined : "tabdock-active"}
                  className="absolute inset-0 rounded-full"
                  style={{ background: ink, boxShadow: "0 4px 14px rgba(28,36,56,0.28)" }}
                  transition={reduce ? undefined : { type: "spring", stiffness: 420, damping: 36 }}
                />
              )}
              <span className="relative z-[1] flex items-center gap-1.5" style={{ fontSize: 12, fontWeight: 500, letterSpacing: "0.02em", textShadow: floating ? "0 1px 6px rgba(28,36,56,0.4)" : undefined }}>
                <Icon size={floating ? 15 : 13} />
                {/* Floating (Glacier-style over the photo): icons only, like the reference. */}
                {!floating && <span className="hidden sm:inline">{label}</span>}
              </span>
            </button>
          );
        })}
      </motion.nav>
    </div>
  );
}

/** Floating chat button — always available, bottom-right. */
export function ChatFab({ onClick }: { onClick: () => void }) {
  const reduce = useReducedMotion();
  return (
    <motion.button
      onClick={onClick}
      aria-label="Open the chat engine"
      title="Ask the engine"
      initial={{ opacity: 0, scale: reduce ? 1 : 0.6 }}
      animate={{ opacity: 1, scale: 1 }}
      whileHover={reduce ? undefined : { scale: 1.07 }}
      whileTap={reduce ? undefined : { scale: 0.94 }}
      transition={{ type: "spring", stiffness: 320, damping: 22 }}
      className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full"
      style={{
        background: ink,
        color: paper,
        border: `1px solid ${paper}`,
        boxShadow: "0 14px 34px rgba(28,36,56,0.35), inset 0 1px 0 rgba(241,239,230,0.18)",
        cursor: "pointer",
      }}
    >
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path
          d="M12 4.2c-4.6 0-8.3 3.1-8.3 7 0 2.2 1.2 4.2 3.1 5.5-.1.9-.5 2.2-1.5 3.1 1.7 0 3.2-.7 4.2-1.4.8.2 1.6.3 2.5.3 4.6 0 8.3-3.1 8.3-7s-3.7-7.5-8.3-7.5Z"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
        <circle cx="8.6" cy="11.2" r="1" fill="currentColor" />
        <circle cx="12" cy="11.2" r="1" fill="currentColor" />
        <circle cx="15.4" cy="11.2" r="1" fill="currentColor" />
      </svg>
    </motion.button>
  );
}
