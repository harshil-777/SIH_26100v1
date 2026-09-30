import type { RiskLevel } from "./api";

export type RiskKey = RiskLevel | "unverified";

// Worst first: the order every risk list, legend and stacked bar uses.
export const RISK_KEYS: RiskKey[] = ["Non-Compliant", "High", "Medium", "Low", "unverified"];

// One colour per level, shared by badges, charts and bars so a level always looks the same.
export const RISK_STYLE: Record<RiskKey, { label: string; hex: string; dot: string }> = {
  "Non-Compliant": { label: "Non-compliant", hex: "#b91c1c", dot: "bg-red-700" },
  High: { label: "High risk", hex: "#ea580c", dot: "bg-orange-600" },
  Medium: { label: "Medium risk", hex: "#f59e0b", dot: "bg-amber-500" },
  Low: { label: "Low risk", hex: "#10b981", dot: "bg-emerald-500" },
  unverified: { label: "Not verified", hex: "#cbd5e1", dot: "bg-slate-300" },
};

const RANK: Record<RiskKey, number> = { "Non-Compliant": 0, High: 1, Medium: 2, Low: 3, unverified: 4 };
export const riskRank = (risk: RiskLevel | null) => RANK[risk ?? "unverified"];

export const scoreColor = (score: number) =>
  score >= 85 ? "bg-emerald-500" : score >= 60 ? "bg-amber-500" : score >= 40 ? "bg-orange-500" : "bg-red-600";
