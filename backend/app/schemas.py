from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from .models import ReviewDecision, ReviewStatus, UserRole, ViolationCategory


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
