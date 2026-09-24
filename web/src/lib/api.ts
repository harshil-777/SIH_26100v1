const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export type RiskLevel = "Low" | "Medium" | "High" | "Non-Compliant";
export type BidStatus = "submitted" | "under_review" | "qualified" | "disqualified" | "clarification_requested";
export type Decision = "qualify" | "disqualify" | "request_clarification";

// The API serialises Postgres NUMERIC as a string ("76.19"); callers parse with toNumber().
type Numeric = string | number;

export type DashboardBid = {
  bid_id: string;
  tender_id: string;
  tender_title: string;
  bidder_id: string;
  bidder_name: string;
  enterprise_category: string | null;
  status: BidStatus;
  submitted_at: string;
  overall_score: Numeric | null;
  risk_level: RiskLevel | null;
};

export type BidDetail = {
  bid_id: string;
  status: BidStatus;
  submitted_at: string;
  bidder: {
    bidder_id: string;
    name: string;
    pan: string;
    gstin: string | null;
    udyam_number: string | null;
    cin: string | null;
    dpiit_recognition_number: string | null;
    nsic_registration_number: string | null;
    epfo_establishment_code: string | null;
    employee_count: number | null;
    enterprise_category: string | null;
    state: string | null;
  };
  tender: {
    tender_id: string;
    title: string;
    department: string;
    category: string;
    estimated_value_inr: Numeric;
    msme_reserved: boolean;
    mii_local_content_threshold_pct: Numeric | null;
    requires_oem_authorization: boolean;
    submission_deadline: string;
  };
  declarations: {
    declaration_id: string;
    criterion_code: string;
    declared_value: string;
    declared_at: string;
    note: string | null;
  }[];
  verification_results: {
    source: string;
    status: string;
    confidence_score: Numeric | null;
    raw_response_json: Record<string, unknown> | null;
    verified_at: string;
  }[];
};

export type Criterion = {
  id: string;
  type: "mandatory" | "graded";
  score: number | null;
  passed: boolean | null;
  reason: string | null;
  weight: number | null;
  evidence: Record<string, unknown>;
};

// One fact compared across declaration / document / portal. Seed placeholders (keyed
// "placeholder:<doc>", or carrying `document_match` in pre-Phase-2 scores) have only a verdict
// and a note; real comparisons carry the values and which pairs disagreed.
export type Comparison = {
  match?: boolean;
  document_match?: boolean;
  declared?: unknown;
  document?: unknown;
  portal?: unknown;
  document_type?: string;
  mismatched_pairs?: string[];
  note?: string;
};

export type ComplianceScore = {
  bid_id: string;
  overall_score: Numeric;
  risk_level: RiskLevel;
  criterion_breakdown_json: {
    criteria: Criterion[];
    graded_weighted_score: number | null;
    mandatory_failure_reasons: string[];
  };
  generated_at: string;
  recommendation: string;
};

export type OcrResult = {
  status?: "extracted" | "no_text" | "failed" | "ocr_unavailable";
  method?: string | null;
  fields?: Record<string, unknown>;
  error?: string;
  text_excerpt?: string;
  pages_processed?: number;
  extracted_at?: string;
};

export type BidDocument = {
  document_type: string;
  submitted: boolean;
  file_ref: string | null;
  note: string | null;
  doc_id: string | null;
  file_hash: string | null;
  uploaded_at: string | null;
  is_placeholder: boolean;
  ocr: OcrResult | null;
};

export type AuditEntry = {
  log_id: number;
  bid_id: string | null;
  actor: string;
  action: string;
  payload_json: Record<string, unknown> | null;
  timestamp: string;
  prev_hash: string | null;
  curr_hash: string;
};

export type AuditLog = {
  bid_id: string;
  chain_valid: boolean;
  broken_at: string[];
  entries: AuditEntry[];
};

export type AuditVerification = {
  valid: boolean;
  chains_checked: number;
  entries_checked: number;
  breaks: { bid_id: string | null; log_id: number; problem: string }[];
  checked_at: string;
};

export type JobStatus = {
  bid_id: string;
  job_status: "not_started" | "queued" | "running" | "success" | "failed";
  celery_state: string;
  error: string | null;
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    throw new ApiError(0, `Cannot reach the API at ${API_BASE_URL}. Is it running?`);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(response.status, describeError(body) ?? `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

// FastAPI returns `detail` as a string for HTTPException and as a list for validation errors.
function describeError(body: unknown): string | null {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item: { msg?: string }) => (item.msg ?? "").replace(/^Value error, /, ""))
      .filter(Boolean)
      .join("; ");
  }
  return null;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  listBids: () => request<DashboardBid[]>("/dashboard/bids"),
  getBid: (bidId: string) => request<BidDetail>(`/bids/${encodeURIComponent(bidId)}`),
  getDocuments: (bidId: string) => request<BidDocument[]>(`/bids/${encodeURIComponent(bidId)}/documents`),
  getAuditLog: (bidId: string) => request<AuditLog>(`/bids/${encodeURIComponent(bidId)}/audit-log`),
  verifyAuditLog: () => request<AuditVerification>("/audit/verify"),
  getJobStatus: (bidId: string) => request<JobStatus>(`/bids/${encodeURIComponent(bidId)}/status`),

  // 404 here just means the bid has never been verified -- not an error for the UI.
  getScore: async (bidId: string): Promise<ComplianceScore | null> => {
    try {
      return await request<ComplianceScore>(`/bids/${encodeURIComponent(bidId)}/compliance-score`);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) return null;
      throw error;
    }
  },

  verify: (bidId: string) => request<{ job_id: string }>(`/bids/${encodeURIComponent(bidId)}/verify`, { method: "POST" }),

  decide: (bidId: string, body: { decision: Decision; actor: string; reason: string | null }) =>
    request<{ bid_id: string; status: BidStatus; audit_log_id: number }>(
      `/bids/${encodeURIComponent(bidId)}/decision`,
      json(body),
    ),
};

export const toNumber = (value: Numeric | null | undefined): number | null =>
  value === null || value === undefined ? null : Number(value);
