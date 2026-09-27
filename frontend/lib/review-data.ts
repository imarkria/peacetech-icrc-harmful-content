export type ViolationCategory =
  | "sexual_violence"
  | "child_related_harm"
  | "hate_related"
  | "other";

export type ReviewDecision =
  | "SEXUAL_VIOLENCE"
  | "CHILD_RELATED_HARM"
  | "HATE_RELATED"
  | "OTHER"
  | "NOT_A_VIOLATION"
  | "UNCLEAR";

export type ReviewStatus = "PENDING" | "REVIEWED";

export type ReviewEvidence = {
  sexualElements?: string[];
  coerciveCircumstances?: string[];
  sexualForms?: string[];
  harmfulTypes?: string[];
  harmPathways?: string[];
};

export type DetectedLink = {
  id: string;
  url: string;
  platform: "Telegram" | "Web";
  predictedCategory: ViolationCategory;
  confidence: number;
  source?: "SCRAP" | "PUBLIC";
  status: ReviewStatus;
  detectedAt: string;
  context: string;
  review?: {
    decision: ReviewDecision;
    reviewedAt: string;
    evidence?: ReviewEvidence;
  };
};

export const categoryLabels: Record<ViolationCategory, string> = {
  sexual_violence: "Sexual violence",
  child_related_harm: "Child-related harmful content",
  hate_related: "Hate-related content",
  other: "Other harmful content",
};

export const decisionLabels: Record<ReviewDecision, string> = {
  SEXUAL_VIOLENCE: "Sexual violence",
  CHILD_RELATED_HARM: "Child-related harm",
  HATE_RELATED: "Hate-related content",
  OTHER: "Other harmful content",
  NOT_A_VIOLATION: "Not a violation",
  UNCLEAR: "Unclear / needs escalation",
};

export function formatDate(date: string) {
  const parsed = new Date(date);
  if (Number.isNaN(parsed.getTime())) return "Date unavailable";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(parsed);
}

export function formatRelativeDate(date: string) {
  const parsed = new Date(date);
  if (Number.isNaN(parsed.getTime())) return "Date unavailable";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(parsed);
}
