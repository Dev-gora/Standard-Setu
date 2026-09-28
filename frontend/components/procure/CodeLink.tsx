"use client";

import { serif, brass } from "./theme";

/** Clickable IS code that opens the standard detail modal. */
export default function CodeLink({
  code,
  onOpen,
}: {
  code: string;
  onOpen: (code: string) => void;
}) {
  return (
    <button
      onClick={() => onOpen(code)}
      style={{
        fontFamily: serif,
        fontSize: "inherit",
        color: brass,
        background: "none",
        border: "none",
        padding: 0,
        cursor: "pointer",
        textDecoration: "underline",
        textDecorationColor: "rgba(169,114,47,0.4)",
      }}
    >
      {code}
    </button>
  );
}
