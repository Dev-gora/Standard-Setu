/**
 * Anonymous session handling + Terms & Conditions consent.
 *
 * Privacy model (matches what the T&C popup promises):
 * - The session id is a random UUID in sessionStorage — no PII, no cookies,
 *   cleared by the browser when the tab closes.
 * - Activity recorded against it (history, notifications) is deleted when the
 *   user closes/refreshes the site: a keepalive DELETE /session-data fires on
 *   `pagehide`, and the backend also expires stale sessions after 12h as a
 *   safety net.
 * - Consent itself is remembered in localStorage so the popup shows once.
 */

const SESSION_KEY = "setu_session_id";
const CONSENT_KEY = "setu_tc_accepted_v1";
const UNSAVED_KEY = "setu_unsaved_session_data";

export function getSessionId(): string {
  if (typeof window === "undefined") return "local";
  try {
    let id = sessionStorage.getItem(SESSION_KEY);
    if (!id) {
      id =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `s-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
      sessionStorage.setItem(SESSION_KEY, id);
    }
    return id;
  } catch {
    return "local";
  }
}

export function hasAcceptedTerms(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(CONSENT_KEY) === "yes";
  } catch {
    return false;
  }
}

export function acceptTerms(): void {
  try {
    window.localStorage.setItem(CONSENT_KEY, "yes");
  } catch {
    /* storage unavailable — popup will re-show next visit; still usable */
  }
}

/** Fire-and-forget deletion of this session's server-side activity. */
export function purgeSessionOnExit(): void {
  try {
    const sid = getSessionId();
    if (!sid || sid === "local") return;
    void fetch("/api/procure/session-data", {
      method: "DELETE",
      headers: { "X-Session-Id": sid },
      keepalive: true, // survives tab close during unload
    }).catch(() => {});
  } catch {
    /* unload race — backend stale-session purge covers it */
  }
}

/** Install the unload purge exactly once. */
export function installSessionPurge(): void {
  if (typeof window === "undefined") return;
  const w = window as typeof window & { __setuPurgeInstalled?: boolean };
  if (w.__setuPurgeInstalled) return;
  w.__setuPurgeInstalled = true;
  window.addEventListener("pagehide", purgeSessionOnExit);
  window.addEventListener("beforeunload", purgeSessionOnExit);
}

// --- Session-data-loss warning ---------------------------------------------
// Uploaded tender files / bulk results exist only in the current tab's
// memory. We track their presence with a flag in the SAME sessionStorage the
// session id lives in (no second session system), and use the browser's
// native beforeunload mechanism to warn before refresh/close/navigate-away.
// Modern browsers may replace the custom text with their own wording —
// expected. Internal SPA navigation never fires beforeunload, so switching
// tabs/views that keep the session never triggers the warning.

/** Mark whether temporary uploaded/session-only data currently exists. */
export function setUnsavedSessionData(active: boolean): void {
  try {
    if (active) sessionStorage.setItem(UNSAVED_KEY, "1");
    else sessionStorage.removeItem(UNSAVED_KEY);
  } catch {
    /* storage unavailable — fail safe to no warning */
  }
}

export function hasUnsavedSessionData(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return sessionStorage.getItem(UNSAVED_KEY) === "1";
  } catch {
    return false;
  }
}

const LEAVE_WARNING =
  "Your uploaded session data will be lost if you leave this page. Are you sure you want to continue?";

/** Install the beforeunload warning exactly once. */
export function installUnsavedDataWarning(): void {
  if (typeof window === "undefined") return;
  const w = window as typeof window & { __setuUnsavedGuardInstalled?: boolean };
  if (w.__setuUnsavedGuardInstalled) return;
  w.__setuUnsavedGuardInstalled = true;
  window.addEventListener("beforeunload", (e: BeforeUnloadEvent) => {
    if (!hasUnsavedSessionData()) return; // nothing temporary to lose
    e.preventDefault();
    // Chrome requires returnValue; Firefox/Edge honour it too. The browser
    // may show its own native confirmation text instead of ours.
    e.returnValue = LEAVE_WARNING;
    return e.returnValue;
  });
}
