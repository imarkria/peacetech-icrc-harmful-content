from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from .models import Priority, ReviewDecision, ReviewStatus, UserRole, ViolationCategory


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=255)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: UserRole
    created_at: datetime


class LoginResponse(BaseModel):
    user: UserResponse


class ReportCreate(BaseModel):
    url: HttpUrl
    category: ViolationCategory
    reason: str | None = Field(default=None, max_length=1000)


class ReportResponse(BaseModel):
    id: int
    reference: str
    url: HttpUrl
    category: ViolationCategory
    reason: str | None = None
    created_at: datetime


class DetectionCreate(BaseModel):
    """One sighting sent by harmwatch. Sightings with the same group_key are copies of the same content.
    `external_id` makes repeated sends idempotent."""
    external_id: str = Field(min_length=1, max_length=48, pattern=r"^[A-Za-z0-9_.:-]+$")
    group_key: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")
    url: HttpUrl
    predicted_category: ViolationCategory
    confidence: float = Field(ge=0, le=1)
    priority: Priority = Priority.STANDARD
    source: Literal["SCRAP", "PUBLIC"] = "SCRAP"
    detected_at: datetime | None = None
    context: str = Field(min_length=1, max_length=2000)


class VolunteerReportCreate(BaseModel):
    """Structured report from a trained volunteer: goes to the priority lane, no model screening."""
    url: HttpUrl
    category: ViolationCategory
    harm_types: list[Literal["threat_incitement", "glorification", "mockery", "victim_identification",
                             "stigmatization", "sexually_explicit", "denial_or_disinformation",
                             "unverified_claim"]] = Field(default_factory=list, max_length=8)
    urgency: Literal["urgent", "high", "standard"] = "high"
    context: str = Field(min_length=10, max_length=2000)


class VolunteerReportResponse(BaseModel):
    reference: str
    link_id: str
    duplicate: bool  # the content was already in the queue: the report was added to it


class ScreeningItem(BaseModel):
    id: str
    url: HttpUrl
    platform: str


class ScreeningResult(BaseModel):
    """Model screening of a community report, sent by `python -m harmwatch.screen`."""
    outcome: Literal["flagged", "not_flagged", "restricted", "unavailable"]
    priority: Priority = Priority.STANDARD
    confidence: float = Field(default=0.0, ge=0, le=1)
    summary: str | None = Field(default=None, max_length=1000)
    group_key: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")


class ReviewEvidence(BaseModel):
    sexualElements: list[str] = Field(default_factory=list)
    coerciveCircumstances: list[str] = Field(default_factory=list)
    sexualForms: list[str] = Field(default_factory=list)
    harmfulTypes: list[str] = Field(default_factory=list)
    harmPathways: list[str] = Field(default_factory=list)


class ReviewSummary(BaseModel):
    decision: ReviewDecision
    reviewed_at: datetime
    reviewer_id: int
    evidence: ReviewEvidence | None = None


class OccurrenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    url: HttpUrl
    platform: str
    source: str
    note: str | None = None
    seen_at: datetime


class DetectedLinkResponse(BaseModel):
    id: str
    url: HttpUrl
    platform: str
    predicted_category: ViolationCategory
    confidence: float = Field(ge=0, le=1)
    source: str
    status: ReviewStatus
    detected_at: datetime
    context: str
    priority: Priority
    occurrence_count: int
    occurrences: list[OccurrenceResponse] = Field(default_factory=list)
    review: ReviewSummary | None = None


class ReviewQueueResponse(BaseModel):
    items: list[DetectedLinkResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    pending_count: int
    reviewed_count: int


class AnalysisCount(BaseModel):
    key: str
    count: int


class AnalysisTrendPoint(BaseModel):
    date: str
    count: int


class AnalysisResponse(BaseModel):
    reviewed_total: int
    source_counts: list[AnalysisCount]
    decision_counts: list[AnalysisCount]
    platform_counts: list[AnalysisCount]
    post_trend: list[AnalysisTrendPoint]
    post_trends: dict[str, list[AnalysisTrendPoint]]
    evidence_counts: dict[str, list[AnalysisCount]]


class ReviewSubmit(BaseModel):
    decision: ReviewDecision
    evidence: ReviewEvidence | None = None


class HealthResponse(BaseModel):
    status: str
    database: str
