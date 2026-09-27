from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()

if settings.database_url.startswith("sqlite:///") and ":memory:" not in settings.database_url:
    sqlite_path = Path(settings.database_url.removeprefix("sqlite:///"))
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def initialize_database() -> None:
    """Create MVP tables and apply the small additive migrations we need for local development."""
    Base.metadata.create_all(bind=engine)
    columns = {column["name"] for column in inspect(engine).get_columns("public_reports")}
    if "reason" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE public_reports ADD COLUMN reason TEXT"))
    if "source" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE public_reports ADD COLUMN source VARCHAR(32) DEFAULT 'PUBLIC'"))
    if "ai_potential" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE public_reports ADD COLUMN ai_potential BOOLEAN DEFAULT 0"))
    with engine.begin() as connection:
        connection.execute(text("UPDATE public_reports SET source = 'PUBLIC' WHERE source IS NULL"))
        connection.execute(text("UPDATE public_reports SET ai_potential = 0 WHERE ai_potential IS NULL"))
    review_columns = {column["name"] for column in inspect(engine).get_columns("reviews")}
    if "sexual_violence" not in review_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE reviews ADD COLUMN sexual_violence VARCHAR(8) DEFAULT 'NO'"))
    if "harmful_information" not in review_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE reviews ADD COLUMN harmful_information VARCHAR(8) DEFAULT 'NO'"))
    if "evidence" not in review_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE reviews ADD COLUMN evidence JSON"))
    with engine.begin() as connection:
        connection.execute(text("UPDATE reviews SET sexual_violence = 'YES', harmful_information = 'YES' WHERE decision IN ('SEXUAL_VIOLENCE', 'CHILD_RELATED_HARM', 'HATE_RELATED', 'OTHER')"))
        connection.execute(text("UPDATE reviews SET decision = 'NO' WHERE decision = 'NOT_A_VIOLATION'"))
        connection.execute(text("UPDATE reviews SET decision = 'YES' WHERE decision IN ('SEXUAL_VIOLENCE', 'CHILD_RELATED_HARM', 'HATE_RELATED', 'OTHER', 'UNCLEAR')"))
    detected_link_columns = {column["name"] for column in inspect(engine).get_columns("detected_links")}
    if "source" not in detected_link_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE detected_links ADD COLUMN source VARCHAR(32) DEFAULT 'SCRAP'"))
    with engine.begin() as connection:
        connection.execute(text("UPDATE detected_links SET source = 'SCRAP' WHERE source IS NULL OR source = 'MODEL'"))
        connection.execute(text("UPDATE detected_links SET source = 'PUBLIC' WHERE source = 'PUBLIC_REPORT'"))
    if "channel" in detected_link_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE detected_links DROP COLUMN channel"))
