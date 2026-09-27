export type ViolationCategory =
  | "sexual_violence"
  | "child_related_harm"
  | "hate_related"
  | "other";

export type ReviewDecision =
  | "YES"
  | "NO";

export type ReviewStatus = "PENDING" | "REVIEWED";

export type Source = "SCRAP" | "VOLUNTEER" | "PUBLIC";

export type Priority = "urgent" | "high" | "standard" | "none";

export type Occurrence = {
  url: string;
  platform: string;
  source: Source;
  note?: string | null;
  seenAt: string;
};

export type ReviewEvidence = {
  basicTags?: string[];
  targetedEthnicity?: string;
  targetedEthnicity2?: string;
  sexualElements?: string[];
  coerciveCircumstances?: string[];
  sexualForms?: string[];
  harmfulTypes?: string[];
  harmPathways?: string[];
};

export type DetectedLink = {
  id: string;
  url: string;
  platform: string;
  predictedCategory: ViolationCategory;
  confidence: number;
  source?: Source;
  status: ReviewStatus;
  detectedAt: string;
  context: string;
  priority: Priority;
  occurrenceCount: number;
  occurrences: Occurrence[];
  review?: {
    decision: ReviewDecision;
    reviewedAt: string;
    sexualViolence: boolean;
    harmfulInformation: boolean;
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
  YES: "Yes",
  NO: "No",
};

export const sourceLabels: Record<Source, string> = {
  SCRAP: "Detection",
  VOLUNTEER: "Trained volunteer",
  PUBLIC: "Community report",
};

export const priorityLabels: Record<Priority, string> = {
  urgent: "Urgent",
  high: "High",
  standard: "Standard",
  none: "Low",
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
