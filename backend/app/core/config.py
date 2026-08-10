# app/core/config.py

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "Mini ERP System"
    app_version: str = "1.0.0"
    debug: bool = Field(False, validation_alias="APP_DEBUG")

    database_url: str

    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_access_minutes: int = Field(30, ge=1, le=30)
    jwt_refresh_days: int = Field(7, ge=1, le=7)

    bcrypt_rounds: int = Field(12, ge=12)

    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5174,http://127.0.0.1:5174,"
        "http://localhost:5175,http://127.0.0.1:5175"
    )
    login_max_attempts: int = 5
    login_window_minutes: int = 15

    @field_validator("jwt_secret")
    @classmethod
    def reject_placeholder_jwt_secret(cls, value: str) -> str:
        if value == "replace-with-a-long-random-secret-at-least-32-characters":
            raise ValueError("JWT_SECRET must be replaced with a private random value.")
        return value

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def get_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
