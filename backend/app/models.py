from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, Enum):
    REVIEWER = "REVIEWER"
    VOLUNTEER = "VOLUNTEER"  # trained volunteer: submits structured reports, cannot see the queue


class ViolationCategory(str, Enum):
    SEXUAL_VIOLENCE = "sexual_violence"
    CHILD_RELATED_HARM = "child_related_harm"
    HATE_RELATED = "hate_related"
    OTHER = "other"


class ReviewStatus(str, Enum):
    PENDING = "PENDING"
    REVIEWED = "REVIEWED"
    SCREENING = "SCREENING"    # community report waiting for the model; not in the queue yet
    RESTRICTED = "RESTRICTED"  # possible minor: never listed, never shown (policy/children.md CH-5)


class Source(str, Enum):
    SCRAP = "SCRAP"            # found by detection (Apify, Telegram collector)
    VOLUNTEER = "VOLUNTEER"    # trained volunteer, priority lane
    PUBLIC = "PUBLIC"          # broader local community: web form, browser extension, Telegram bot


class Priority(str, Enum):
    URGENT = "urgent"
    HIGH = "high"
    STANDARD = "standard"
    NONE = "none"


PRIORITY_RANK = {"urgent": 3, "high": 2, "standard": 1, "none": 0}


class ReviewDecision(str, Enum):
    SEXUAL_VIOLENCE = "SEXUAL_VIOLENCE"
    CHILD_RELATED_HARM = "CHILD_RELATED_HARM"
    HATE_RELATED = "HATE_RELATED"
    OTHER = "OTHER"
    NOT_A_VIOLATION = "NOT_A_VIOLATION"
    UNCLEAR = "UNCLEAR"


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
    priority: Mapped[str] = mapped_column(String(16), default=Priority.STANDARD.value, index=True)
    # Duplicates: every copy of the same content is one occurrence of one link, reviewed once.
    group_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)  # from harmwatch fingerprints
    normalized_url: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    occurrence_count: Mapped[int] = mapped_column(default=1)

    review: Mapped["Review | None"] = relationship(back_populates="detected_link", uselist=False)
    occurrences: Mapped[list["Occurrence"]] = relationship(
        back_populates="detected_link", order_by="Occurrence.seen_at", cascade="all, delete-orphan"
    )


class Occurrence(Base):
    """One sighting or report of a link's content: a repost, a copy on another platform, another report."""
    __tablename__ = "occurrences"

    id: Mapped[int] = mapped_column(primary_key=True)
    detected_link_id: Mapped[str] = mapped_column(ForeignKey("detected_links.id"), index=True)
    external_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)  # harmwatch sighting id
    url: Mapped[str] = mapped_column(Text)
    platform: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(32))
    reporter_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # trained volunteer
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    detected_link: Mapped[DetectedLink] = relationship(back_populates="occurrences")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("detected_link_id", name="uq_reviews_detected_link_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    detected_link_id: Mapped[str] = mapped_column(ForeignKey("detected_links.id"), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    decision: Mapped[str] = mapped_column(String(64))
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    detected_link: Mapped[DetectedLink] = relationship(back_populates="review")
    reviewer: Mapped[User] = relationship(back_populates="reviews")
