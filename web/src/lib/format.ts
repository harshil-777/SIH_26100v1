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
export const factLabel = (key: string) => {
  const [prefix, rest] = key.includes(":") ? key.split(":", 2) : [null, key];
  if (prefix === "placeholder" || prefix === "document") return `${documentTypeLabel(rest)} (document check)`;
  return humanize(key.replace(/_self_declared$/, ""));
};

export const formatScore = (score: number | null) =>
  score === null ? "—" : Number.isInteger(score) ? String(score) : score.toFixed(2);

export const formatDateTime = (iso: string) =>
  new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });

export const formatDate = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { dateStyle: "medium" });

export const formatInr = (value: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(value);

// Indian-system short form for headline figures: 4,50,00,000 -> "₹4.5 Cr".
export const formatInrCompact = (value: number) => {
  const trim = (n: number) => n.toFixed(n >= 100 ? 0 : 1).replace(/\.0$/, "");
  if (value >= 1e7) return `₹${trim(value / 1e7)} Cr`;
  if (value >= 1e5) return `₹${trim(value / 1e5)} L`;
  return formatInr(value);
};

const DAY_MS = 86_400_000;

// Whole calendar days from today to a YYYY-MM-DD deadline; negative once it has passed.
export const daysUntil = (isoDate: string) => {
  const [year, month, day] = isoDate.slice(0, 10).split("-").map(Number);
  const now = new Date();
  return Math.round((Date.UTC(year, month - 1, day) - Date.UTC(now.getFullYear(), now.getMonth(), now.getDate())) / DAY_MS);
};

export const deadlineLabel = (isoDate: string) => {
  const days = daysUntil(isoDate);
  if (days < 0) return `Closed ${-days}d ago`;
  if (days === 0) return "Closes today";
  if (days === 1) return "Closes tomorrow";
  return `${days} days left`;
};

export const deadlineTone = (isoDate: string) => {
  const days = daysUntil(isoDate);
  if (days < 0) return "text-slate-500";
  if (days <= 7) return "text-red-700";
  if (days <= 21) return "text-amber-700";
  return "text-slate-600";
};

export const formatRelative = (iso: string) => {
  const seconds = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return formatDate(iso);
};

export const initials = (name: string) =>
  name
    .replace(/\b(pvt|ltd|llp|private|limited|inc|co)\b\.?/gi, "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]!.toUpperCase())
    .join("");

export const formatValue = (value: unknown): string => {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
};

export const shortHash = (hash: string | null) => (hash ? `${hash.slice(0, 10)}…${hash.slice(-6)}` : "genesis");
