from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from .config import get_settings
from .database import SessionLocal, engine, get_db, initialize_database
from .models import DetectedLink, PublicReport, Review, ReviewStatus, User
from .schemas import (
    DetectedLinkResponse,
    HealthResponse,
    LoginRequest,
    LoginResponse,
    ReportCreate,
    ReportResponse,
    ReviewQueueResponse,
    ReviewSubmit,
    ReviewSummary,
    UserResponse,
)
from .security import create_access_token, require_reviewer, verify_password
from .seed import seed_demo_data

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    if settings.seed_demo_data:
        with SessionLocal() as db:
            seed_demo_data(db)
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def to_link_response(link: DetectedLink) -> DetectedLinkResponse:
    review = None
    if link.review:
        review = ReviewSummary(
            decision=link.review.decision,
            created_at=link.review.created_at,
            reviewer_id=link.review.reviewer_id,
        )
    return DetectedLinkResponse(
        id=link.id,
        url=link.url,
        platform=link.platform,
        channel=link.channel,
        predicted_category=link.predicted_category,
        confidence=link.confidence,
        status=link.status,
        detected_at=link.detected_at,
        context=link.context,
        review=review,
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
    report = PublicReport(url=str(payload.url), category=payload.category.value, reason=payload.reason.strip() or None if payload.reason else None)
    db.add(report)
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


@app.get("/api/reviews/queue", response_model=ReviewQueueResponse, tags=["reviews"])
def review_queue(
    status_filter: ReviewStatus | None = Query(default=None, alias="status"),
    query: str | None = Query(default=None, min_length=1, max_length=200),
    _: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> ReviewQueueResponse:
    base_query = select(DetectedLink).options(joinedload(DetectedLink.review)).order_by(DetectedLink.detected_at.desc())
    if status_filter:
        base_query = base_query.where(DetectedLink.status == status_filter.value)
    if query:
        search = f"%{query.lower()}%"
        base_query = base_query.where(func.lower(DetectedLink.url).like(search) | func.lower(DetectedLink.channel).like(search))

    links = list(db.scalars(base_query).unique().all())
    pending_count = db.scalar(select(func.count()).select_from(DetectedLink).where(DetectedLink.status == ReviewStatus.PENDING.value)) or 0
    reviewed_count = db.scalar(select(func.count()).select_from(DetectedLink).where(DetectedLink.status == ReviewStatus.REVIEWED.value)) or 0
    return ReviewQueueResponse(items=[to_link_response(link) for link in links], total=len(links), pending_count=pending_count, reviewed_count=reviewed_count)


@app.get("/api/reviews/{link_id}", response_model=DetectedLinkResponse, tags=["reviews"])
def get_review(link_id: str, _: User = Depends(require_reviewer), db: Session = Depends(get_db)) -> DetectedLinkResponse:
    link = db.scalar(select(DetectedLink).options(joinedload(DetectedLink.review)).where(DetectedLink.id == link_id))
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detected link not found")
    return to_link_response(link)


@app.post("/api/reviews/{link_id}", response_model=DetectedLinkResponse, tags=["reviews"])
def submit_review(link_id: str, payload: ReviewSubmit, reviewer: User = Depends(require_reviewer), db: Session = Depends(get_db)) -> DetectedLinkResponse:
    link = db.scalar(select(DetectedLink).options(joinedload(DetectedLink.review)).where(DetectedLink.id == link_id))
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detected link not found")
    if link.status == ReviewStatus.REVIEWED.value or link.review:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This link has already been reviewed")

    link.status = ReviewStatus.REVIEWED.value
    link.review = Review(detected_link_id=link.id, reviewer_id=reviewer.id, decision=payload.decision.value, created_at=datetime.now(timezone.utc))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This link has already been reviewed") from exc
    db.refresh(link)
    return to_link_response(link)
