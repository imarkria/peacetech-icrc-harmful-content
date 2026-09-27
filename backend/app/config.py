from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SignalSafe API"
    environment: str = "development"
    database_url: str = "sqlite:///./data/local.db"
    jwt_secret: str = "replace-this-in-a-real-environment"
    access_token_expire_minutes: int = 480
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    cors_origin_regex: str = r"chrome-extension://.*"
    cookie_secure: bool = False
    seed_demo_data: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
