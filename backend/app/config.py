from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "replace-this-in-a-real-environment"
DEMO_REVIEWER_EMAIL = "reviewer@icrc.org"
DEMO_VOLUNTEER_EMAIL = "volunteer@icrc.org"
DEMO_PASSWORD = "reviewer"


class Settings(BaseSettings):
    app_name: str = "SignalSafe API"
    environment: str = "development"
    database_url: str = "sqlite:///./data/local.db"
    jwt_secret: str = DEFAULT_JWT_SECRET
    access_token_expire_minutes: int = 480
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    cors_origin_regex: str = r"chrome-extension://.*"
    cookie_secure: bool = False
    seed_demo_data: bool = True
    demo_password: str = DEMO_PASSWORD  # for the demo reviewer and the demo volunteer
    ingest_token: str = ""  # shared with harmwatch; empty disables POST /api/detections and model screening
    report_rate_limit: str = "5/600"  # community reports per client IP: <count>/<seconds>; 0/1 disables
    screening_timeout_minutes: int = 30  # unscreened community reports reach the queue after this delay

    @property
    def rate_limit(self) -> tuple[int, int]:
        count, seconds = self.report_rate_limit.split("/")
        return int(count), int(seconds)

    @property
    def screening_enabled(self) -> bool:
        return bool(self.ingest_token)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore")

    @model_validator(mode="after")
    def refuse_unsafe_defaults(self) -> "Settings":
        """Outside development, refuse to start with the development secret, demo password or insecure cookies."""
        if self.environment == "development":
            return self
        problems = []
        if self.jwt_secret == DEFAULT_JWT_SECRET or len(self.jwt_secret) < 32:
            problems.append("JWT_SECRET must be set to a random value of at least 32 characters")
        if self.seed_demo_data and self.demo_password == DEMO_PASSWORD:
            problems.append("SEED_DEMO_DATA=true needs DEMO_PASSWORD, or set SEED_DEMO_DATA=false")
        if not self.cookie_secure:
            problems.append("COOKIE_SECURE must be true (HTTPS)")
        if self.ingest_token and len(self.ingest_token) < 32:
            problems.append("INGEST_TOKEN must be at least 32 characters")
        if problems:
            raise ValueError(f"Unsafe settings for ENVIRONMENT={self.environment}: " + "; ".join(problems))
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
