export type ViolationCategory =
  | "sexual_violence"
  | "child_related_harm"
  | "hate_related"
  | "other";

export type ReviewDecision =
  | "YES"
  | "NO";

export type ReviewStatus = "PENDING" | "REVIEWED";

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
  platform: "Telegram" | "Web";
  predictedCategory: ViolationCategory;
  confidence: number;
  source?: "SCRAP" | "PUBLIC" | "SPECIALIST";
  status: ReviewStatus;
  detectedAt: string;
  context: string;
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

export const initialDetectedLinks: DetectedLink[] = [
  {
    id: "link-1001",
    url: "https://t.me/example_channel/1842",
    platform: "Telegram",
    predictedCategory: "sexual_violence",
    confidence: 0.93,
    status: "PENDING",
    detectedAt: "2025-02-14T09:32:00Z",
    context: "Model flagged language that may describe or encourage sexual violence. No media is displayed in this review interface.",
  },
  {
    id: "link-1002",
    url: "https://t.me/public_updates/771",
    platform: "Telegram",
    predictedCategory: "hate_related",
    confidence: 0.88,
    status: "PENDING",
    detectedAt: "2025-02-14T08:15:00Z",
    context: "Model detected potentially dehumanising language targeting a protected group.",
  },
  {
    id: "link-1003",
    url: "https://t.me/community_watch/338",
    platform: "Telegram",
    predictedCategory: "child_related_harm",
    confidence: 0.81,
    status: "PENDING",
    detectedAt: "2025-02-13T17:48:00Z",
    context: "Model flagged a possible child-safety concern for human verification.",
  },
  {
    id: "link-1004",
    url: "https://t.me/news_digest/904",
    platform: "Telegram",
    predictedCategory: "sexual_violence",
    confidence: 0.76,
    status: "PENDING",
    detectedAt: "2025-02-13T13:05:00Z",
    context: "Model found a possible reference to sexual violence. Review the source safely and record the most accurate label.",
  },
  {
    id: "link-1005",
    url: "https://t.me/example_channel/1760",
    platform: "Telegram",
    predictedCategory: "other",
    confidence: 0.69,
    status: "REVIEWED",
    detectedAt: "2025-02-12T16:21:00Z",
    context: "Model flagged content for general harmful-content review.",
    review: {
      decision: "NO",
      sexualViolence: false,
      harmfulInformation: false,
      reviewedAt: "2025-02-13T10:04:00Z",
    },
  },
  {
    id: "link-1006",
    url: "https://t.me/field_reports/121",
    platform: "Telegram",
    predictedCategory: "hate_related",
    confidence: 0.91,
    status: "REVIEWED",
    detectedAt: "2025-02-11T11:40:00Z",
    context: "Model flagged potentially hateful content targeting a protected group.",
    review: {
      decision: "YES",
      sexualViolence: true,
      harmfulInformation: true,
      reviewedAt: "2025-02-12T09:17:00Z",
    },
  },
];

const STORAGE_KEY = "icrc-detected-links";

export function getStoredLinks(): DetectedLink[] {
  if (typeof window === "undefined") return initialDetectedLinks;

  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (!stored) {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(initialDetectedLinks));
    return initialDetectedLinks;
  }

  try {
    return JSON.parse(stored) as DetectedLink[];
  } catch {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(initialDetectedLinks));
    return initialDetectedLinks;
  }
}

export function saveStoredLinks(links: DetectedLink[]) {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(links));
  }
}

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
