from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import DEMO_REVIEWER_EMAIL, DEMO_VOLUNTEER_EMAIL, get_settings
from .intake import normalize_url
from .models import DetectedLink, Occurrence, Review, ReviewDecision, ReviewStatus, User, UserRole, ViolationCategory
from .security import hash_password


SEED_LINKS = [
    {
        "id": "link-1001",
        "url": "https://t.me/example_channel/1842",
        "platform": "Telegram",
        "predicted_category": ViolationCategory.SEXUAL_VIOLENCE.value,
        "confidence": 0.93,
        "status": ReviewStatus.PENDING.value,
        "detected_at": datetime(2025, 2, 14, 9, 32, tzinfo=timezone.utc),
        "context": "Model flagged language that may describe or encourage sexual violence. No media is displayed in this review interface.",
    },
    {
        "id": "link-1002",
        "url": "https://t.me/public_updates/771",
        "platform": "Telegram",
        "predicted_category": ViolationCategory.HATE_RELATED.value,
        "confidence": 0.88,
        "status": ReviewStatus.PENDING.value,
        "detected_at": datetime(2025, 2, 14, 8, 15, tzinfo=timezone.utc),
        "context": "Model detected potentially dehumanising language targeting a protected group.",
    },
    {
        "id": "link-1003",
        "url": "https://t.me/community_watch/338",
        "platform": "Telegram",
        "predicted_category": ViolationCategory.CHILD_RELATED_HARM.value,
        "confidence": 0.81,
        "status": ReviewStatus.PENDING.value,
        "detected_at": datetime(2025, 2, 13, 17, 48, tzinfo=timezone.utc),
        "context": "Model flagged a possible child-safety concern for human verification.",
    },
    {
        "id": "link-1004",
        "url": "https://t.me/news_digest/904",
        "platform": "Telegram",
        "predicted_category": ViolationCategory.SEXUAL_VIOLENCE.value,
        "confidence": 0.76,
        "status": ReviewStatus.PENDING.value,
        "detected_at": datetime(2025, 2, 13, 13, 5, tzinfo=timezone.utc),
        "context": "Model found a possible reference to sexual violence. Review the source safely and record the most accurate label.",
    },
    {
        "id": "link-1005",
        "url": "https://t.me/example_channel/1760",
        "platform": "Telegram",
        "predicted_category": ViolationCategory.OTHER.value,
        "confidence": 0.69,
        "status": ReviewStatus.REVIEWED.value,
        "detected_at": datetime(2025, 2, 12, 16, 21, tzinfo=timezone.utc),
        "context": "Model flagged content for general harmful-content review.",
        "review_decision": ReviewDecision.NO.value,
        "reviewed_at": datetime(2025, 2, 13, 10, 4, tzinfo=timezone.utc),
    },
    {
        "id": "link-1006",
        "url": "https://t.me/field_reports/121",
        "platform": "Telegram",
        "predicted_category": ViolationCategory.HATE_RELATED.value,
        "confidence": 0.91,
        "status": ReviewStatus.REVIEWED.value,
        "detected_at": datetime(2025, 2, 11, 11, 40, tzinfo=timezone.utc),
        "context": "Model flagged potentially hateful content targeting a protected group.",
        "review_decision": ReviewDecision.YES.value,
        "reviewed_at": datetime(2025, 2, 12, 9, 17, tzinfo=timezone.utc),
    },
]


def seed_demo_data(db: Session) -> None:
    password = get_settings().demo_password
    reviewer = db.scalar(select(User).where(User.email == DEMO_REVIEWER_EMAIL))
    if reviewer is None:
        reviewer = User(email=DEMO_REVIEWER_EMAIL, password_hash=hash_password(password), role=UserRole.REVIEWER.value)
        db.add(reviewer)
        db.flush()
    if db.scalar(select(User).where(User.email == DEMO_VOLUNTEER_EMAIL)) is None:
        db.add(User(email=DEMO_VOLUNTEER_EMAIL, password_hash=hash_password(password), role=UserRole.VOLUNTEER.value))
        db.flush()

    if db.scalar(select(DetectedLink.id).limit(1)) is not None:
        db.commit()
        return

    for original_data in SEED_LINKS:
        link_data = dict(original_data)
        review_decision = link_data.pop("review_decision", None)
        reviewed_at = link_data.pop("reviewed_at", None)
        link = DetectedLink(**link_data, normalized_url=normalize_url(link_data["url"]), occurrence_count=1)
        link.occurrences.append(Occurrence(url=link.url, platform=link.platform, source="SCRAP", seen_at=link.detected_at))
        db.add(link)
        if review_decision:
            db.flush()
            is_yes = review_decision == ReviewDecision.YES.value
            db.add(Review(
                detected_link_id=link.id,
                reviewer_id=reviewer.id,
                decision=review_decision,
                sexual_violence="YES" if is_yes else "NO",
                harmful_information="YES" if is_yes else "NO",
                created_at=reviewed_at,
            ))
    db.commit()
