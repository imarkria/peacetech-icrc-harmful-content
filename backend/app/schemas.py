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


class ReviewSummary(BaseModel):
    decision: ReviewDecision
    reviewed_at: datetime = Field(alias="created_at")
    reviewer_id: int

    model_config = ConfigDict(populate_by_name=True)


class DetectedLinkResponse(BaseModel):
    id: str
    url: HttpUrl
    platform: str
    channel: str
    predicted_category: ViolationCategory
    confidence: float = Field(ge=0, le=1)
    status: ReviewStatus
    detected_at: datetime
    context: str
    review: ReviewSummary | None = None


class ReviewQueueResponse(BaseModel):
    items: list[DetectedLinkResponse]
    total: int
    pending_count: int
    reviewed_count: int


class ReviewSubmit(BaseModel):
    decision: ReviewDecision


class HealthResponse(BaseModel):
    status: str
    database: str
