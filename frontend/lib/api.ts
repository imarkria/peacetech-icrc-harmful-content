import { DetectedLink, ReviewDecision, ReviewEvidence, ReviewStatus, ViolationCategory } from "./review-data";

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

type ApiErrorShape = { detail?: string };

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
  const raw = await response.text();
  let data: unknown = null;
  try {
    data = raw ? JSON.parse(raw) : null;
  } catch {
    data = null;
  }

  if (!response.ok) {
    const detail = (data as ApiErrorShape | null)?.detail;
    throw new ApiError(response.status, detail || `Request failed with status ${response.status}`);
  }
  return data as T;
}

type ApiReview = {
  id: string;
  url: string;
  platform: "Telegram" | "Web";
  predicted_category: ViolationCategory;
  confidence: number;
  source: "SCRAP" | "PUBLIC";
  status: ReviewStatus;
  detected_at: string;
  context: string;
  review?: {
    decision: ReviewDecision;
    reviewed_at?: string;
    created_at?: string;
    reviewer_id: number;
    evidence?: ReviewEvidence;
  } | null;
};

type ApiQueue = {
  items: ApiReview[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  pending_count: number;
  reviewed_count: number;
};

function mapReview(item: ApiReview): DetectedLink {
  return {
    id: item.id,
    url: item.url,
    platform: item.platform,
    predictedCategory: item.predicted_category,
    confidence: item.confidence,
    source: item.source,
    status: item.status,
    detectedAt: item.detected_at,
    context: item.context,
    review: item.review ? {
      decision: item.review.decision,
      reviewedAt: item.review.reviewed_at || item.review.created_at || "",
      evidence: item.review.evidence,
    } : undefined,
  };
}

export async function loginRequest(email: string, password: string) {
  return request<{ user: { id: number; email: string; role: string } }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function getMeRequest() {
  return request<{ id: number; email: string; role: string }>("/api/me");
}

export async function logoutRequest() {
  await request<void>("/api/auth/logout", { method: "POST" });
}

export async function createReportRequest(payload: { url: string; category: ViolationCategory; reason?: string }) {
  return request<{ reference: string; reason: string | null }>("/api/reports", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getReviewQueue(status?: ReviewStatus, query = "", page = 1, pageSize = 10) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (status) params.set("status", status);
  if (query.trim()) params.set("query", query.trim());
  const result = await request<ApiQueue>(`/api/reviews/queue?${params.toString()}`);
  return {
    ...result,
    items: result.items.map(mapReview),
  };
}

export type AnalysisCount = { key: string; count: number };
export type AnalysisTrendPoint = { date: string; count: number };
export type AnalysisSummary = {
  reviewed_total: number;
  source_counts: AnalysisCount[];
  decision_counts: AnalysisCount[];
  platform_counts: AnalysisCount[];
  post_trend: AnalysisTrendPoint[];
  post_trends: Record<string, AnalysisTrendPoint[]>;
  evidence_counts: Record<string, AnalysisCount[]>;
};

export async function getAnalysisSummary(category?: string) {
  const query = category ? `?category=${encodeURIComponent(category)}` : "";
  return request<AnalysisSummary>(`/api/analysis/summary${query}`);
}

export async function getReviewRequest(id: string) {
  const result = await request<ApiReview>(`/api/reviews/${encodeURIComponent(id)}`);
  return mapReview(result);
}

export async function submitReviewRequest(id: string, decision: ReviewDecision, evidence: ReviewEvidence) {
  const result = await request<ApiReview>(`/api/reviews/${encodeURIComponent(id)}`, {
    method: "POST",
    body: JSON.stringify({ decision, evidence }),
  });
  return mapReview(result);
}
