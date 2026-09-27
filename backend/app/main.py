import secrets
from collections import Counter, defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import case, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from .config import get_settings
from .database import SessionLocal, get_db, initialize_database
from .intake import RateLimiter, add_occurrence, find_group, new_link, normalize_url
from .models import DetectedLink, Occurrence, PublicReport, Review, ReviewDecision, ReviewStatus, Source, User
from .schemas import (
    AnalysisCount,
    AnalysisResponse,
    AnalysisTrendPoint,
    DetectedLinkResponse,
    DetectionCreate,
    HealthResponse,
    LoginRequest,
    LoginResponse,
    OccurrenceResponse,
    ReportCreate,
    ReportResponse,
    ReviewQueueResponse,
    ReviewSubmit,
    ReviewSummary,
    ScreeningItem,
    ScreeningResult,
    UserResponse,
    VolunteerReportCreate,
    VolunteerReportResponse,
)
from .security import create_access_token, get_current_user, require_reviewer, require_volunteer, verify_password
from .seed import seed_demo_data

settings = get_settings()
report_limiter = RateLimiter(*settings.rate_limit)

# Reviewers only ever see these. SCREENING waits for the model; RESTRICTED (possible minor) is never listed or shown.
VISIBLE_STATUSES = (ReviewStatus.PENDING.value, ReviewStatus.REVIEWED.value)
PRIORITY_ORDER = case({"urgent": 0, "high": 1, "standard": 2, "none": 3}, value=DetectedLink.priority, else_=4)
DEFAULT_PUBLIC_CONTEXT = "Submitted by a member of the public for reviewer assessment."


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    if settings.seed_demo_data:
        with SessionLocal() as db:
            seed_demo_data(db)
    with SessionLocal() as db:
        backfill_links(db)
        sync_public_reports_to_queue(db)
    yield


app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)
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
        priority=link.priority,
        occurrence_count=link.occurrence_count,
        occurrences=[OccurrenceResponse.model_validate(o) for o in link.occurrences],
        review=review,
    )


def load_link(db: Session, link_id: str, visible_only: bool = True) -> DetectedLink | None:
    query = (select(DetectedLink)
             .options(joinedload(DetectedLink.review), selectinload(DetectedLink.occurrences))
             .where(DetectedLink.id == link_id))
    if visible_only:
        query = query.where(DetectedLink.status.in_(VISIBLE_STATUSES))
    return db.scalar(query)


def backfill_links(db: Session) -> None:
    """Links created before grouping existed: give them a normalised URL and their first occurrence."""
    links = db.scalars(select(DetectedLink).where(DetectedLink.normalized_url.is_(None))).all()
    for link in links:
        link.normalized_url = normalize_url(link.url)
        if not link.occurrences:
            add_occurrence(link, url=link.url, source=link.source, seen_at=link.detected_at)
    if links:
        db.commit()


def sync_public_reports_to_queue(db: Session) -> None:
    """Public reports stored before they were added to the queue on creation."""
    created = False
    for report in db.scalars(select(PublicReport).order_by(PublicReport.id)).all():
        if db.get(DetectedLink, f"public-{report.id}") or find_group(db, None, normalize_url(report.url)):
            continue
        link = new_link(link_id=f"public-{report.id}", url=report.url, source=Source.PUBLIC.value,
                        category=report.category, confidence=0.0, priority="standard",
                        context=report.reason or DEFAULT_PUBLIC_CONTEXT, detected_at=report.created_at)
        add_occurrence(link, url=report.url, source=Source.PUBLIC.value, note=report.reason, seen_at=report.created_at)
        db.add(link)
        created = True
    if created:
        db.commit()


def release_stale_screening(db: Session) -> None:
    """Community reports are never lost: if the model has not screened them in time, they reach the queue unscreened."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.screening_timeout_minutes)
    stale = db.scalars(select(DetectedLink).where(DetectedLink.status == ReviewStatus.SCREENING.value,
                                                  DetectedLink.detected_at < cutoff)).all()
    for link in stale:
        link.status = ReviewStatus.PENDING.value
        link.context = f"{link.context}\nNot screened by the model (timed out)."
    if stale:
        db.commit()


def require_ingest_token(x_ingest_token: str | None = Header(default=None)) -> None:
    if not settings.ingest_token:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Detection ingestion is disabled (INGEST_TOKEN is not set)")
    if not x_ingest_token or not secrets.compare_digest(x_ingest_token, settings.ingest_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid ingest token")


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
def me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(user)


# --- Community lane: anyone, anonymous, rate-limited, screened by the model when harmwatch is connected -------------

@app.post("/api/reports", response_model=ReportResponse, status_code=status.HTTP_201_CREATED, tags=["community reports"])
def create_report(payload: ReportCreate, request: Request, db: Session = Depends(get_db)) -> ReportResponse:
    if not report_limiter.allow(request.client.host if request.client else "unknown"):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many reports. Please try again later.")
    url = str(payload.url)
    reason = payload.reason.strip() or None if payload.reason else None
    report = PublicReport(url=url, category=payload.category.value, reason=reason)
    db.add(report)
    db.flush()

    link = find_group(db, None, normalize_url(url))
    if link is None:
        link = new_link(
            link_id=f"public-{report.id}", url=url, source=Source.PUBLIC.value, category=payload.category.value,
            confidence=0.0, priority="standard", context=reason or DEFAULT_PUBLIC_CONTEXT,
            status=ReviewStatus.SCREENING.value if settings.screening_enabled else ReviewStatus.PENDING.value,
        )
        db.add(link)
    add_occurrence(link, url=url, source=Source.PUBLIC.value, note=reason)
    db.commit()
    db.refresh(report)
    return ReportResponse(
        id=report.id,
        reference=f"SS-{report.id:06d}",
        url=report.url,
        category=report.category,
        reason=report.reason,
        created_at=report.created_at,
    )


# --- Trained volunteer lane: accounts, structured reports, priority, no screening -----------------------------------

@app.post("/api/volunteer/reports", response_model=VolunteerReportResponse, status_code=status.HTTP_201_CREATED, tags=["volunteer reports"])
def create_volunteer_report(payload: VolunteerReportCreate, volunteer: User = Depends(require_volunteer),
                            db: Session = Depends(get_db)) -> VolunteerReportResponse:
    url = str(payload.url)
    labels = ", ".join(payload.harm_types) or "no harm type selected"
    note = f"{labels}. {payload.context.strip()}"
    link = find_group(db, None, normalize_url(url))
    duplicate = link is not None
    if link is None:
        link = new_link(
            link_id=f"vol-{secrets.token_hex(6)}", url=url, source=Source.VOLUNTEER.value,
            category=payload.category.value, confidence=0.0, priority=payload.urgency,
            context=f"Trained volunteer report ({labels}): {payload.context.strip()}",
        )
        db.add(link)
    elif link.status == ReviewStatus.SCREENING.value:
        link.status = ReviewStatus.PENDING.value  # a trained volunteer vouches for it: no need to wait for the model
    occurrence = add_occurrence(link, url=url, source=Source.VOLUNTEER.value, priority=payload.urgency,
                                reporter_id=volunteer.id, note=note)
    db.commit()
    return VolunteerReportResponse(reference=f"VR-{occurrence.id:06d}", link_id=link.id, duplicate=duplicate)


# --- Detection lane: harmwatch (Apify, Telegram collector, Telegram bot) ------------------------------------------

@app.post("/api/detections", response_model=DetectedLinkResponse, status_code=status.HTTP_201_CREATED, tags=["detections"])
def create_detection(
    payload: DetectionCreate,
    response: Response,
    _: None = Depends(require_ingest_token),
    db: Session = Depends(get_db),
) -> DetectedLinkResponse:
    """Add one sighting. A copy of content already in the queue (same group_key or same URL) joins it and returns 200;
    sending the same external_id again is a no-op."""
    known = db.scalar(select(Occurrence).where(Occurrence.external_id == payload.external_id))
    if known:
        response.status_code = status.HTTP_200_OK
        return to_link_response(load_link(db, known.detected_link_id, visible_only=False))

    url = str(payload.url)
    link = find_group(db, payload.group_key, normalize_url(url))
    if link is not None:
        response.status_code = status.HTTP_200_OK
        link.group_key = link.group_key or payload.group_key
        if link.status == ReviewStatus.SCREENING.value:  # the model has now seen this content
            link.status = ReviewStatus.PENDING.value
            link.context = f"{link.context}\nModel: {payload.context}"
    else:
        link = new_link(
            link_id=f"hw-{payload.external_id}", url=url, source=payload.source,
            category=payload.predicted_category.value, confidence=payload.confidence,
            priority=payload.priority.value, context=payload.context, group_key=payload.group_key,
            detected_at=payload.detected_at,
        )
        db.add(link)
    add_occurrence(link, url=url, source=payload.source, priority=payload.priority.value,
                   external_id=payload.external_id, seen_at=payload.detected_at)
    db.commit()
    return to_link_response(load_link(db, link.id, visible_only=False))


@app.get("/api/intake/screening", response_model=list[ScreeningItem], tags=["detections"])
def screening_queue(limit: int = Query(default=50, ge=1, le=200), _: None = Depends(require_ingest_token),
                    db: Session = Depends(get_db)) -> list[ScreeningItem]:
    """Community reports waiting for the model, oldest first."""
    links = db.scalars(select(DetectedLink).where(DetectedLink.status == ReviewStatus.SCREENING.value)
                       .order_by(DetectedLink.detected_at).limit(limit)).all()
    return [ScreeningItem(id=link.id, url=link.url, platform=link.platform) for link in links]


@app.post("/api/intake/screening/{link_id}", tags=["detections"])
def submit_screening(link_id: str, payload: ScreeningResult, _: None = Depends(require_ingest_token),
                     db: Session = Depends(get_db)) -> dict[str, str]:
    link = load_link(db, link_id, visible_only=False)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
    if link.status != ReviewStatus.SCREENING.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This link is not waiting for screening")

    if payload.outcome == "restricted":
        # CH-5: keep nothing that describes the content, not even the reporter's words.
        link.status = ReviewStatus.RESTRICTED.value
        link.context = "Restricted by model screening (possible minor)."
        for occurrence in link.occurrences:
            occurrence.note = None
        db.commit()
        return {"status": link.status, "link_id": link.id}

    if payload.group_key:
        other = db.scalar(select(DetectedLink).where(DetectedLink.group_key == payload.group_key,
                                                     DetectedLink.id != link.id))
        if other is not None:  # same content already in the queue: this report becomes one more copy of it
            for occurrence in list(link.occurrences):
                link.occurrences.remove(occurrence)
                other.occurrences.append(occurrence)
            other.occurrence_count = len(other.occurrences)
            db.delete(link)
            db.commit()
            return {"status": "merged", "link_id": other.id}
        link.group_key = payload.group_key

    link.status = ReviewStatus.PENDING.value
    if payload.outcome == "flagged":
        link.priority, link.confidence = payload.priority.value, payload.confidence
        link.context = f"{link.context}\nModel screening: {payload.summary or 'flagged'}"
    elif payload.outcome == "not_flagged":
        link.priority = "none"  # human reports are never dropped, only ranked lower
        link.context = f"{link.context}\nModel screening: not flagged. {payload.summary or ''}".rstrip()
    else:
        link.context = f"{link.context}\nNot screened: the content could not be fetched."
    db.commit()
    return {"status": link.status, "link_id": link.id}


# --- Reviewers ----------------------------------------------------------------------------------------------------

@app.get("/api/reviews/queue", response_model=ReviewQueueResponse, tags=["reviews"])
def review_queue(
    status_filter: ReviewStatus | None = Query(default=None, alias="status"),
    query: str | None = Query(default=None, min_length=1, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    _: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> ReviewQueueResponse:
    release_stale_screening(db)
    filters = [DetectedLink.status.in_(VISIBLE_STATUSES)]
    if status_filter:
        filters.append(DetectedLink.status == status_filter.value)
    if query:
        search = f"%{query.lower()}%"
        filters.append(func.lower(DetectedLink.url).like(search))

    total = db.scalar(select(func.count()).select_from(DetectedLink).where(*filters)) or 0
    total_pages = max(1, (total + page_size - 1) // page_size)
    if status_filter == ReviewStatus.REVIEWED:
        order = (DetectedLink.detected_at.desc(),)
    else:  # most urgent first, then the most widely spread, then the newest
        order = (PRIORITY_ORDER, DetectedLink.occurrence_count.desc(), DetectedLink.detected_at.desc())
    links = db.scalars(
        select(DetectedLink)
        .options(joinedload(DetectedLink.review), selectinload(DetectedLink.occurrences))
        .where(*filters)
        .order_by(*order)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).unique().all()
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
    link = load_link(db, link_id)
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
    trend_counts_by_decision: dict[str, Counter] = defaultdict(Counter)
    evidence_counts: dict[str, Counter] = defaultdict(Counter)
    for source, platform, decision, evidence, detected_at in reviewed_items:
        source_counts[source] += 1
        decision_counts[decision] += 1
        platform_counts[platform] += 1
        trend_counts[detected_at.date().isoformat()] += 1
        trend_counts_by_decision[decision][detected_at.date().isoformat()] += 1
        for evidence_key in ("sexualElements", "coerciveCircumstances", "sexualForms", "harmfulTypes", "harmPathways"):
            for value in (evidence or {}).get(evidence_key, []):
                evidence_counts[evidence_key][value] += 1

    return AnalysisResponse(
        reviewed_total=len(reviewed_items),
        source_counts=[AnalysisCount(key=key, count=count) for key, count in source_counts.most_common()],
        decision_counts=[AnalysisCount(key=key, count=count) for key, count in decision_counts.most_common()],
        platform_counts=[AnalysisCount(key=key, count=count) for key, count in platform_counts.most_common()],
        post_trend=[AnalysisTrendPoint(date=date, count=trend_counts[date]) for date in sorted(trend_counts)],
        post_trends={decision: [AnalysisTrendPoint(date=date, count=count) for date, count in sorted(dates.items())] for decision, dates in trend_counts_by_decision.items()},
        evidence_counts={key: [AnalysisCount(key=item, count=count) for item, count in values.most_common()] for key, values in evidence_counts.items()},
    )


@app.post("/api/reviews/{link_id}", response_model=DetectedLinkResponse, tags=["reviews"])
def submit_review(link_id: str, payload: ReviewSubmit, reviewer: User = Depends(require_reviewer), db: Session = Depends(get_db)) -> DetectedLinkResponse:
    link = load_link(db, link_id)
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detected link not found")
    if link.status == ReviewStatus.REVIEWED.value or link.review:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This link has already been reviewed")

    link.status = ReviewStatus.REVIEWED.value
    link.review = Review(
        detected_link_id=link.id,
        reviewer_id=reviewer.id,
        decision=payload.decision.value,
        evidence=payload.evidence.model_dump() if payload.evidence else None,
        created_at=datetime.now(timezone.utc),
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This link has already been reviewed") from exc
    return to_link_response(load_link(db, link.id))
