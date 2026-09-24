import type { BidStatus } from "./api";

const CRITERION_LABELS: Record<string, string> = {
  gst_active: "GSTIN active",
  not_debarred: "Not debarred",
  pan_valid: "PAN valid",
  document_completeness: "Mandatory documents submitted",
  local_content_pct: "Make in India local content",
  epfo_compliance: "EPFO / ESIC compliance",
  declaration_document_consistency: "Declarations match documents & portals",
  msme_eligibility: "MSME eligibility",
};

const SOURCE_LABELS: Record<string, string> = {
  udyam: "Udyam (MSME)",
  gstn: "GSTN",
  pan: "PAN (Income Tax)",
  mca21: "MCA21",
  epfo_esic: "EPFO / ESIC",
  startup_india: "Startup India (DPIIT)",
  nsic: "NSIC",
  debarment: "Debarment registry",
  mii_local_content: "Make in India local content",
};

export const STATUS_LABELS: Record<BidStatus, string> = {
  submitted: "Submitted",
  under_review: "Under review",
  qualified: "Qualified",
  disqualified: "Disqualified",
  clarification_requested: "Clarification requested",
};

const ACRONYMS = /\b(gst|gstin|pan|mii|oem|epfo|esic|bis|psara|ca|emd|msme|dpiit|nsic|cin|mca21)\b/gi;

// Fallback for codes we have no label for: "gst_trade_name" -> "GST trade name".
function humanize(code: string): string {
  const text = code.replace(/^document:/, "").replace(/_/g, " ").toLowerCase().replace(ACRONYMS, (word) => word.toUpperCase());
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export const criterionLabel = (id: string) => CRITERION_LABELS[id] ?? humanize(id);
export const sourceLabel = (source: string) => SOURCE_LABELS[source] ?? humanize(source);
export const documentTypeLabel = (code: string) => humanize(code);
export const factLabel = (key: string) =>
  key.startsWith("document:") ? `${documentTypeLabel(key.slice("document:".length))} (document check)` : humanize(key.replace(/_self_declared$/, ""));

export const formatScore = (score: number | null) =>
  score === null ? "—" : Number.isInteger(score) ? String(score) : score.toFixed(2);

export const formatDateTime = (iso: string) =>
  new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });

export const formatDate = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { dateStyle: "medium" });

export const formatInr = (value: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(value);

export const formatValue = (value: unknown): string => {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
};

export const shortHash = (hash: string | null) => (hash ? `${hash.slice(0, 10)}…${hash.slice(-6)}` : "genesis");
