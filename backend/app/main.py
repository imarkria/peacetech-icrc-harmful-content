from contextlib import asynccontextmanager
from collections import Counter, defaultdict
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from .config import get_settings
from .database import SessionLocal, engine, get_db, initialize_database
from .models import DetectedLink, PublicReport, Review, ReviewDecision, ReviewStatus, User
from .schemas import (
    DetectedLinkResponse,
    HealthResponse,
    LoginRequest,
    LoginResponse,
    ReportCreate,
    ReportResponse,
    ReviewQueueResponse,
    AnalysisResponse,
    AnalysisCount,
    AnalysisTrendPoint,
    ReviewSubmit,
    ReviewSummary,
    UserResponse,
)
from .security import create_access_token, require_reviewer, require_specialist, verify_password
from .seed import seed_demo_data

settings = get_settings()
BASIC_TAG_IDS = (
    "BT-MEN",
    "BT-WOMEN",
    "BT-CHILDREN",
    "BT-SEXUAL-VIOLENCE",
    "BT-FORCED-SEXUAL-ACTION",
)
MOCK_AI_KEYWORDS = (
    "sexual violence",
    "sexual assault",
    "forced sexual",
    "rape",
    "gender-based violence",
    "hate speech",
    "ethnic hatred",
    "incitement",
    "threat",
    "kill",
    "violence",
    "harmful",
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    if settings.seed_demo_data:
        with SessionLocal() as db:
            seed_demo_data(db)
    with SessionLocal() as db:
        sync_public_reports_to_queue(db)
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def to_link_response(link: DetectedLink) -> DetectedLinkResponse:
    review = None
    if link.review:
        review = ReviewSummary(
            decision=link.review.decision,
            reviewed_at=link.review.created_at,
            reviewer_id=link.review.reviewer_id,
            sexual_violence=link.review.sexual_violence == "YES",
            harmful_information=link.review.harmful_information == "YES",
            evidence=link.review.evidence,
        )
    return DetectedLinkResponse(
        id=link.id,
        url=link.url,
        platform=link.platform,
        predicted_category=link.predicted_category,
        confidence=link.confidence,
        source=link.source,
        status=link.status,
        detected_at=link.detected_at,
        context=link.context,
        review=review,
    )


def public_report_platform(url: str) -> str:
    hostname = (urlparse(url).hostname or "").lower()
    return "Telegram" if hostname in {"t.me", "telegram.me", "www.t.me", "www.telegram.me"} else "Web"


def sync_public_reports_to_queue(db: Session) -> None:
    reports = db.scalars(select(PublicReport).order_by(PublicReport.id)).all()
    created = False
    for report in reports:
        if report.source != "SPECIALIST" and not report.ai_potential:
            continue
        link_id = f"public-{report.id}"
        if db.get(DetectedLink, link_id):
            continue
        db.add(DetectedLink(
            id=link_id,
            url=report.url,
            platform=public_report_platform(report.url),
            predicted_category=report.category,
            confidence=0.82 if report.ai_potential else 0.0,
            source=report.source,
            status=ReviewStatus.PENDING.value,
            detected_at=report.created_at,
            context=report.reason or ("Mock AI flagged this public report as potentially harmful." if report.ai_potential else "Submitted by an ICRC specialist for reviewer assessment."),
        ))
        created = True
    if created:
        db.commit()


def mock_ai_potential(url: str, reason: str | None, category: str) -> bool:
    """Small deterministic stand-in for the future harmful-content model."""
    haystack = f"{url} {reason or ''} {category}".lower()
    return any(keyword in haystack for keyword in MOCK_AI_KEYWORDS)


def save_link_submission(payload: ReportCreate, db: Session, source: str, direct_to_queue: bool) -> ReportResponse:
    report_url = str(payload.url)
    report_reason = payload.reason.strip() or None if payload.reason else None
    ai_potential = mock_ai_potential(report_url, report_reason, payload.category.value) if not direct_to_queue else False
    report = PublicReport(
        url=report_url,
        category=payload.category.value,
        reason=report_reason,
        source=source,
        ai_potential=ai_potential,
    )
    db.add(report)
    db.flush()

    queued = direct_to_queue or ai_potential
    if queued:
        db.add(DetectedLink(
            id=f"public-{report.id}",
            url=report_url,
            platform=public_report_platform(report_url),
            predicted_category=payload.category.value,
            confidence=0.0 if direct_to_queue else 0.82,
            source=source,
            status=ReviewStatus.PENDING.value,
            detected_at=datetime.now(timezone.utc),
            context=report_reason or (
                "Submitted by an ICRC specialist for reviewer assessment."
                if direct_to_queue else "Mock AI flagged this public report as potentially harmful."
            ),
        ))

    db.commit()
    db.refresh(report)
    return ReportResponse(
        id=report.id,
        reference=f"SS-{report.id:06d}",
        url=report.url,
        category=report.category,
        reason=report.reason,
        created_at=report.created_at,
        queued=queued,
        ai_potential=ai_potential,
    )


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {"name": settings.app_name, "docs": "/docs"}


@app.get("/api/health", response_model=HealthResponse, tags=["system"])
def health(db: Session = Depends(get_db)) -> HealthResponse:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return HealthResponse(status="ok", database="connected")


@app.post("/api/auth/login", response_model=LoginResponse, tags=["auth"])
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.scalar(select(User).where(func.lower(User.email) == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email or password is incorrect")

    response.set_cookie(
        key="access_token",
        value=create_access_token(user),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    return LoginResponse(user=UserResponse.model_validate(user))


@app.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT, tags=["auth"])
def logout(response: Response) -> None:
    response.delete_cookie(key="access_token", path="/")


@app.get("/api/me", response_model=UserResponse, tags=["auth"])
def me(user: User = Depends(require_reviewer)) -> UserResponse:
    return UserResponse.model_validate(user)


@app.post("/api/reports", response_model=ReportResponse, status_code=status.HTTP_201_CREATED, tags=["public reports"])
def create_report(payload: ReportCreate, db: Session = Depends(get_db)) -> ReportResponse:
    return save_link_submission(payload, db, source="PUBLIC", direct_to_queue=False)


@app.post("/api/specialist/reports", response_model=ReportResponse, status_code=status.HTTP_201_CREATED, tags=["specialist reports"])
def create_specialist_report(payload: ReportCreate, _: User = Depends(require_specialist), db: Session = Depends(get_db)) -> ReportResponse:
    return save_link_submission(payload, db, source="SPECIALIST", direct_to_queue=True)


@app.get("/api/reviews/queue", response_model=ReviewQueueResponse, tags=["reviews"])
def review_queue(
    status_filter: ReviewStatus | None = Query(default=None, alias="status"),
    query: str | None = Query(default=None, min_length=1, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    _: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> ReviewQueueResponse:
    filters = []
    if status_filter:
        filters.append(DetectedLink.status == status_filter.value)
    if query:
        search = f"%{query.lower()}%"
        filters.append(func.lower(DetectedLink.url).like(search))

    total = db.scalar(select(func.count()).select_from(DetectedLink).where(*filters)) or 0
    total_pages = max(1, (total + page_size - 1) // page_size)
    base_query = (
        select(DetectedLink)
        .options(joinedload(DetectedLink.review))
        .where(*filters)
        .order_by(DetectedLink.detected_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    links = list(db.scalars(base_query).unique().all())
    pending_count = db.scalar(select(func.count()).select_from(DetectedLink).where(DetectedLink.status == ReviewStatus.PENDING.value)) or 0
    reviewed_count = db.scalar(select(func.count()).select_from(DetectedLink).where(DetectedLink.status == ReviewStatus.REVIEWED.value)) or 0
    return ReviewQueueResponse(
        items=[to_link_response(link) for link in links],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        pending_count=pending_count,
        reviewed_count=reviewed_count,
    )


@app.get("/api/reviews/{link_id}", response_model=DetectedLinkResponse, tags=["reviews"])
def get_review(link_id: str, _: User = Depends(require_reviewer), db: Session = Depends(get_db)) -> DetectedLinkResponse:
    link = db.scalar(select(DetectedLink).options(joinedload(DetectedLink.review)).where(DetectedLink.id == link_id))
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detected link not found")
    return to_link_response(link)


@app.get("/api/analysis/summary", response_model=AnalysisResponse, tags=["analysis"])
def analysis_summary(
    category: ReviewDecision | None = Query(default=None),
    _: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> AnalysisResponse:
    filters = [DetectedLink.status == ReviewStatus.REVIEWED.value]
    if category:
        filters.append(Review.decision == category.value)
    reviewed_items = db.execute(
        select(DetectedLink.source, DetectedLink.platform, Review.decision, Review.evidence, DetectedLink.detected_at)
        .join(Review, Review.detected_link_id == DetectedLink.id)
        .where(*filters)
        .order_by(DetectedLink.detected_at.asc())
    ).all()

    source_counts = Counter()
    decision_counts = Counter()
    platform_counts = Counter()
    trend_counts = Counter()
    trend_counts_by_basic_tag: dict[str, Counter] = defaultdict(Counter)
    evidence_counts: dict[str, Counter] = defaultdict(Counter)
    for source, platform, decision, evidence, detected_at in reviewed_items:
        source_counts[source] += 1
        decision_counts[decision] += 1
        platform_counts[platform] += 1
        trend_counts[detected_at.date().isoformat()] += 1
        for basic_tag in (evidence or {}).get("basicTags", []):
            trend_counts_by_basic_tag[basic_tag][detected_at.date().isoformat()] += 1
        for evidence_key in ("basicTags", "sexualElements", "coerciveCircumstances", "sexualForms", "harmfulTypes", "harmPathways"):
            for value in (evidence or {}).get(evidence_key, []):
                evidence_counts[evidence_key][value] += 1

    return AnalysisResponse(
        reviewed_total=len(reviewed_items),
        source_counts=[AnalysisCount(key=key, count=count) for key, count in source_counts.most_common()],
        decision_counts=[AnalysisCount(key=key, count=count) for key, count in decision_counts.most_common()],
        platform_counts=[AnalysisCount(key=key, count=count) for key, count in platform_counts.most_common()],
        post_trend=[AnalysisTrendPoint(date=date, count=trend_counts[date]) for date in sorted(trend_counts)],
        post_trends={tag: [AnalysisTrendPoint(date=date, count=count) for date, count in sorted(trend_counts_by_basic_tag[tag].items())] for tag in BASIC_TAG_IDS},
        evidence_counts={key: [AnalysisCount(key=item, count=count) for item, count in values.most_common()] for key, values in evidence_counts.items()},
    )


@app.post("/api/reviews/{link_id}", response_model=DetectedLinkResponse, tags=["reviews"])
def submit_review(link_id: str, payload: ReviewSubmit, reviewer: User = Depends(require_reviewer), db: Session = Depends(get_db)) -> DetectedLinkResponse:
    link = db.scalar(select(DetectedLink).options(joinedload(DetectedLink.review)).where(DetectedLink.id == link_id))
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detected link not found")
    if link.status == ReviewStatus.REVIEWED.value or link.review:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This link has already been reviewed")

    link.status = ReviewStatus.REVIEWED.value
    decision = ReviewDecision.YES.value if payload.sexual_violence and payload.harmful_information else ReviewDecision.NO.value
    link.review = Review(
        detected_link_id=link.id,
        reviewer_id=reviewer.id,
        decision=decision,
        sexual_violence="YES" if payload.sexual_violence else "NO",
        harmful_information="YES" if payload.harmful_information else "NO",
        evidence=payload.evidence.model_dump() if payload.evidence else None,
        created_at=datetime.now(timezone.utc),
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This link has already been reviewed") from exc
    db.refresh(link)
    return to_link_response(link)
