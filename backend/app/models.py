from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, Enum):
    REVIEWER = "REVIEWER"
    SPECIALIST = "SPECIALIST"


class ViolationCategory(str, Enum):
    SEXUAL_VIOLENCE = "sexual_violence"
    CHILD_RELATED_HARM = "child_related_harm"
    HATE_RELATED = "hate_related"
    OTHER = "other"


class ReviewStatus(str, Enum):
    PENDING = "PENDING"
    REVIEWED = "REVIEWED"


class ReviewDecision(str, Enum):
    YES = "YES"
    NO = "NO"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default=UserRole.REVIEWER.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    reviews: Mapped[list["Review"]] = relationship(back_populates="reviewer")


class PublicReport(Base):
    __tablename__ = "public_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(64), index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="PUBLIC", index=True)
    ai_potential: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class DetectedLink(Base):
    __tablename__ = "detected_links"
    __table_args__ = (Index("ix_detected_links_status_detected_at", "status", "detected_at"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    url: Mapped[str] = mapped_column(Text)
    platform: Mapped[str] = mapped_column(String(64), default="Telegram")
    predicted_category: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(32), default="SCRAP", index=True)
    status: Mapped[str] = mapped_column(String(32), default=ReviewStatus.PENDING.value, index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    context: Mapped[str] = mapped_column(Text)

    review: Mapped["Review | None"] = relationship(back_populates="detected_link", uselist=False)


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("detected_link_id", name="uq_reviews_detected_link_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    detected_link_id: Mapped[str] = mapped_column(ForeignKey("detected_links.id"), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    decision: Mapped[str] = mapped_column(String(64))
    sexual_violence: Mapped[str] = mapped_column(String(8), default="NO")
    harmful_information: Mapped[str] = mapped_column(String(8), default="NO")
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    detected_link: Mapped[DetectedLink] = relationship(back_populates="review")
    reviewer: Mapped[User] = relationship(back_populates="reviews")
