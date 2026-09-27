from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "replace-this-in-a-real-environment"
DEMO_REVIEWER_EMAIL = "reviewer@icrc.org"
DEMO_REVIEWER_PASSWORD = "reviewer"


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
    demo_reviewer_password: str = DEMO_REVIEWER_PASSWORD
    ingest_token: str = ""  # shared with the harmwatch publisher; empty disables POST /api/detections

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore")

    @model_validator(mode="after")
    def refuse_unsafe_defaults(self) -> "Settings":
        """Outside development, refuse to start with the development secret, demo password or insecure cookies."""
        if self.environment == "development":
            return self
        problems = []
        if self.jwt_secret == DEFAULT_JWT_SECRET or len(self.jwt_secret) < 32:
            problems.append("JWT_SECRET must be set to a random value of at least 32 characters")
        if self.seed_demo_data and self.demo_reviewer_password == DEMO_REVIEWER_PASSWORD:
            problems.append("SEED_DEMO_DATA=true needs DEMO_REVIEWER_PASSWORD, or set SEED_DEMO_DATA=false")
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
