/**
 * API client — typed functions for the Standard Setu (SIH26108) backend.
 */

import { getSessionId } from "./session";

const API_BASE = "/api";

/** fetch wrapper attaching the anonymous session id (privacy scoping). */
async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers || {});
  headers.set("X-Session-Id", getSessionId());
  return fetch(input, { ...init, headers });
}

export interface CertificationInfo {
  mandatory: boolean;
  scheme: string;
  note: string;
  /** Provenance of the mandatory claim (audit): VERIFIED = QCO-backed. */
  verification_status?: "VERIFIED" | "PARTIALLY_VERIFIED" | "UNVERIFIED" | "MANUAL_REVIEW_REQUIRED" | string;
  /** QCO/notification text when VERIFIED. */
  basis?: string;
  source_url?: string;
}

export interface ArchiveLink {
  url: string;
  exact: boolean;
}

export interface RegistryStandard {
  is_number: string;
  title: string;
  category: string;
  scope_description: string;
  latest_version: string;
  amendment: string;
  certification: CertificationInfo;
  archive_link: ArchiveLink;
  score?: number | null;
  /** Version provenance (audit): LOCAL_REGISTRY | GOVERNMENT_VERIFIED | ... */
  version_status?: string;
  verification_status?: string;
  gov_edition?: string;
  qco?: { status?: string; name?: string; notification?: string; source_url?: string };
}

export interface AlliedStandard {
  code: string;
  title: string;
  category: string;
  purpose: string;
  latest_version: string;
  amendment: string;
  certification: CertificationInfo | null;
  known: boolean;
  archive_link: ArchiveLink;
}

export interface ClarifyOption {
  label: string;
  query: string;
}

export interface ClarifyPrompt {
  question: string;
  helper: string;
  options: ClarifyOption[];
}

export interface ScoreFactor {
  label: string;
  value: number;
  detail: string;
}

export interface ScoreBreakdown {
  score: number;
  factors: ScoreFactor[];
  signals: Record<string, number | null>;
  embedding_mode: "semantic" | "keyword_only" | string;
  confidence: "High" | "Medium" | "Low" | string;
}

export interface ProcureRecommendation {
  standard: RegistryStandard;
  relevance_score: number;
  reason: string;
  allied: AlliedStandard[];
  tender_block: string;
  match: ScoreBreakdown | null;
  evidence: ClaimEvidence[];
}

export interface ProcureResponse {
  query: string;
  product_label: string;
  clarify_needed: boolean;
  clarify: ClarifyPrompt | null;
  recommendations: ProcureRecommendation[];
  mode: string;
  history_id: string;
}

export interface OcrStatus {
  attempted: boolean;
  used: boolean;
  pages: number;
  confidence: number | null;
  message: string;
}

export interface BulkIssue {
  kind: "unknown_standard" | "outdated_version" | "missing_certification" | "unparseable" | string;
  detail: string;
  /** IS code this issue concerns; ""/undefined when not attributable to a standard. */
  standard?: string;
  /** True when the issue belongs to the tender/batch, not any single standard. */
  batch_level?: boolean;
}

export interface FileCheckResult {
  file_name: string;
  status: "pass" | "review" | "error";
  product_label: string;
  standards_cited: string[];
  primary_standard: string;
  issues: BulkIssue[];
  note: string;
  ocr: OcrStatus | null;
  text_chars: number;
}

export interface BulkCheckResponse {
  files: FileCheckResult[];
  total: number;
  passing: number;
  min_standards: string[];
  risk: RiskResponse | null;
  /** Demand-vs-availability rating per standard across the batch. */
  demand_rating?: {
    standard: string;
    title: string;
    demanded_by: number;
    share_pct: number;
    demand_level: "HIGH" | "MEDIUM" | "LOW" | string;
    verified_mandatory: boolean;
    certification_status: string;
    availability_note: string;
    availability_confidence: string;
    qco: string;
  }[];
  /** Issues not attributable to any single standard (batch-level findings). */
  batch_issues?: {
    kind: string;
    files: string[];
    count: number;
    detail: string;
  }[];
}

// --- P0-2 evidence -----------------------------------------------------------

export interface EvidenceRef {
  standard: string;
  edition: string;
  document: string;
  page: number | null;
  clause: string | null;
  url: string;
  evidence: string;
  available: boolean;
  unavailable_reason: string;
}

export interface ClaimEvidence {
  claim: string;
  kind: "requirement_match" | "scope" | "certification" | "edition" | "source" | string;
  evidence: EvidenceRef;
}

// --- P0-3 verification --------------------------------------------------------

export interface VerifyRequest {
  licence_number: string;
  supplier_name?: string;
  is_number?: string;
}

export interface VerifyResponse {
  licence_number: string;
  supplier_name: string;
  is_number: string;
  status: "valid" | "invalid" | "expired" | "not_found" | "unable_to_verify" | "source_unavailable" | string;
  /** Exact audit state (backend `state`): SOURCE_LOCATED, VERIFIED_ACTIVE, ... */
  state?: string;
  detail: string;
  product: string;
  validity: string;
  source: string;
  last_verified: string;
  cached: boolean;
  source_url: string;
  message: string;
}

// --- P0-4 history -------------------------------------------------------------

export interface HistoryEntry {
  id: string;
  ts: string;
  kind: "recommendation" | "clarify" | "tender_check" | "verification" | string;
  query: string;
  session_id: string;
  title: string;
  status: string;
  payload: Record<string, unknown>;
}

export interface HistoryListResponse {
  entries: HistoryEntry[];
  total: number;
}

// --- P0-5 watchlist -----------------------------------------------------------

export interface WatchlistItem {
  is_number: string;
  title: string;
  latest_version: string;
  amendment: string;
  added_at: string;
  last_checked: string;
  note: string;
  changed: boolean;
  baseline: Record<string, string>;
}

export interface StandardChangeNotification {
  id: string;
  ts: string;
  is_number: string;
  title: string;
  change: string;
  previous: { latest_version: string; amendment: string };
  current: { latest_version: string; amendment: string; title: string };
  read: boolean;
}

export interface WatchlistResponse {
  items: WatchlistItem[];
  notifications: StandardChangeNotification[];
  checked_at: string;
  total: number;
}

export interface NotificationsResponse {
  notifications: StandardChangeNotification[];
  unread: number;
}

// --- P1-1 comparison -----------------------------------------------------------

export interface CompareColumn {
  code: string;
  title: string;
  found: boolean;
  latest_version: string;
  amendment: string;
  category: string;
  scope_description: string;
  certification: CertificationInfo | null;
  normative_refs: string[];
  match_score: number | null;
  attributes: Record<string, string>;
}

export interface CompareResponse {
  columns: CompareColumn[];
  attributes: string[];
  query: string;
}

// --- P1-7 risk ------------------------------------------------------------------

export interface RiskDimension {
  dimension: string;
  level: "low" | "medium" | "high" | string;
  score: number;
  findings: string[];
  action: string;
}

export interface TenderRisk {
  file_name: string;
  overall: "low" | "medium" | "high" | string;
  dimensions: RiskDimension[];
}

export interface RiskResponse {
  files: TenderRisk[];
  overall: "low" | "medium" | "high" | string;
  summary: string;
}

// --- P1-9 versions ---------------------------------------------------------------

export interface VersionSectionDiff {
  section: string;
  previous: string;
  current: string;
  change: "added" | "removed" | "modified" | "unchanged" | "unable_to_determine" | string;
}

export interface VersionCompareResponse {
  code: string;
  from_version: string;
  to_version: string;
  sections: VersionSectionDiff[];
  changed_count: number;
  available: boolean;
  message: string;
}

// --- P1-10 report -----------------------------------------------------------------

export interface ReportResponse {
  generated_at: string;
  query: string;
  standard: RegistryStandard | null;
  match: ScoreBreakdown | null;
  evidence: ClaimEvidence[];
  allied: AlliedStandard[];
  tender_block: string;
  risk_notes: string[];
  sources: EvidenceRef[];
}

/**
 * Recommend Indian Standards for a procurement description.
 * May return a clarifying question instead of recommendations.
 */
export async function procureRecommend(
  query: string,
  topK: number = 4
): Promise<ProcureResponse> {
  const res = await apiFetch(`${API_BASE}/procure/recommend`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, top_k: topK }),
  });
  if (!res.ok) throw new Error(`Procure API error: ${res.status}`);
  return res.json();
}

/**
 * Bulk-check tender PDFs against the standards registry.
 */
export async function procureBulkCheck(
  files: File[]
): Promise<BulkCheckResponse> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  const res = await apiFetch(`${API_BASE}/procure/bulk-check`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(`Bulk check API error: ${res.status}`);
  return res.json();
}

/**
 * Registry detail for one standard (used by the detail modal).
 */
export async function getRegistryStandard(
  isNumber: string
): Promise<RegistryStandard> {
  const res = await apiFetch(
    `${API_BASE}/procure/standard/${encodeURIComponent(isNumber)}`
  );
  if (!res.ok) throw new Error(`Standard detail API error: ${res.status}`);
  return res.json()
}

// --- P0-2 evidence -------------------------------------------------------------

export async function getEvidence(
  isNumber: string,
  query = ""
): Promise<ClaimEvidence[]> {
  const qs = query ? `?query=${encodeURIComponent(query)}` : "";
  const res = await apiFetch(
    `${API_BASE}/procure/evidence/${encodeURIComponent(isNumber)}${qs}`
  );
  if (!res.ok) throw new Error(`Evidence API error: ${res.status}`);
  return res.json();
}

// --- P0-3 verification -----------------------------------------------------------

export async function verifyLicence(req: VerifyRequest): Promise<VerifyResponse> {
  const res = await apiFetch(`${API_BASE}/procure/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`Verify API error: ${res.status}`);
  return res.json();
}

// --- P0-4 history -----------------------------------------------------------------

export async function getHistory(limit = 50): Promise<HistoryListResponse> {
  const res = await apiFetch(`${API_BASE}/procure/history?limit=${limit}`);
  if (!res.ok) throw new Error(`History API error: ${res.status}`);
  return res.json();
}

export async function getHistoryEntry(id: string): Promise<HistoryEntry> {
  const res = await apiFetch(`${API_BASE}/procure/history/${id}`);
  if (!res.ok) throw new Error(`History detail API error: ${res.status}`);
  return res.json();
}

// --- P0-5 watchlist ----------------------------------------------------------------

export async function getWatchlist(check = true): Promise<WatchlistResponse> {
  const res = await apiFetch(`${API_BASE}/procure/watchlist?check=${check}`);
  if (!res.ok) throw new Error(`Watchlist API error: ${res.status}`);
  return res.json()
}

export async function addWatch(isNumber: string, note = ""): Promise<WatchlistItem> {
  const res = await apiFetch(`${API_BASE}/procure/watchlist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_number: isNumber, note }),
  });
 if (!res.ok) throw new Error(`Watch add API error: ${res.status}`);
  return res.json();
}

export async function removeWatch(isNumber: string): Promise<void> {
  const res = await apiFetch(
    `${API_BASE}/procure/watchlist/${encodeURIComponent(isNumber)}`,
    { method: "DELETE" }
  );
  if (!res.ok) throw new Error(`Watch remove API error: ${res.status}`);
}

export async function getNotifications(): Promise<NotificationsResponse> {
  const res = await apiFetch(`${API_BASE}/procure/notifications`);
  if (!res.ok) throw new Error(`Notifications API error: ${res.status}`);
  return res.json();
}

export async function markNotificationRead(id: string): Promise<void> {
  const res = await apiFetch(`${API_BASE}/procure/notifications/read`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id }),
  });
  if (!res.ok) throw new Error(`Notification read API error: ${res.status}`);
}

// --- P1-1 comparison ------------------------------------------------------------------

export async function compareStandards(
  codes: string[],
  query = ""
): Promise<CompareResponse> {  const res = await apiFetch(`${API_BASE}/procure/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ codes, query }),
  });
  if (!res.ok) throw new Error(`Compare API error: ${res.status}`);
  return res.json();
}

// --- P1-9 versions ----------------------------------------------------------------------

export async function compareVersions(
  isNumber: string
): Promise<VersionCompareResponse> {
  const res = await apiFetch(
    `${API_BASE}/procure/versions/${encodeURIComponent(isNumber)}`
  );
  if (!res.ok) throw new Error(`Versions API error: ${res.status}`);
  return res.json();
}

// --- P1-10 report -------------------------------------------------------------------------

export async function buildReport(
  query: string,
  code = ""
): Promise<ReportResponse> {
  const res = await apiFetch(`${API_BASE}/procure/report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, code }),
  });
  if (!res.ok) throw new Error(`Report API error: ${res.status}`);
  return res.json();
}

// --- Explore --------------------------------------------------------------------------------

export interface BrowseStandard {
  code: string;
  title: string;
  category: string;
  latest_version: string;
  amendment: string;
  certification: { mandatory: boolean; scheme: string; verification_status?: string; basis?: string };
  archive_link: { url: string; exact: boolean };
}

export interface BrowseResponse {
  standards: BrowseStandard[];
  categories: Record<string, number>;
  total: number;
}

/** Full registry summary for the Explore tab (category grid + number search). */
export async function browseStandards(): Promise<BrowseResponse> {
  const res = await apiFetch(`${API_BASE}/procure/browse`);
  if (!res.ok) throw new Error(`Browse API error: ${res.status}`);
  return res.json();
}
