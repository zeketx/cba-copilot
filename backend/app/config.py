from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.auth.identity import EmailAllowList
from app.database.constants import EMBEDDING_DIMENSIONS

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROVIDERS = {"openai", "google", "openrouter"}
_EMBEDDING_PROVIDERS = {"hash", "openai", "openrouter"}
_VOYAGE_LITE = "mongodb/voyage-4-lite"


def model_id(provider: str, model: str) -> str:
    cleaned = model.strip()
    if provider == "openai":
        return cleaned
    if provider == "google":
        if cleaned.startswith("google"):
            return cleaned
        return f"google:{cleaned}"
    if provider == "openrouter":
        if cleaned.startswith("openrouter:"):
            return cleaned
        return f"openrouter:{cleaned}"
    raise ValueError("ANSWER_PROVIDER must be openai, google, or openrouter")


def missing_provider_key(
    provider: str,
    *,
    openai: str,
    gemini: str,
    openrouter: str,
) -> str | None:
    if provider not in _PROVIDERS:
        return "ANSWER_PROVIDER must be openai, google, or openrouter"
    key = {"openai": openai, "google": gemini, "openrouter": openrouter}[provider]
    if key.strip():
        return None
    name = {
        "openai": "OPENAI_API_KEY",
        "google": "GEMINI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
    }[provider]
    return f"{name} is required when ANSWER_PROVIDER is {provider}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    database_url: str = ""

    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int = Field(default=1536, gt=0)
    embedding_provider: str = "openrouter"
    embedding_model: str = _VOYAGE_LITE
    embedding_dimensions: int | None = EMBEDDING_DIMENSIONS
    answer_provider: str = "openai"
    answer_model: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""

    retrieval_candidate_k: int = 50
    retrieval_top_k: int = 8
    retrieval_rrf_k: int = 60
    retrieval_context_per_hit: int = 4
    retrieval_context_max: int = 16
    retrieval_fts_config: str = "english"

    answer_rate_limit: int = Field(default=10, gt=0)
    answer_rate_window_seconds: int = Field(default=60, gt=0)
    access_request_rate_limit: int = Field(default=5, gt=0)
    access_request_rate_window_seconds: int = Field(default=600, gt=0)
    access_request_cap: int = Field(default=100, gt=0)

    allowed_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    allowed_emails: Annotated[tuple[str, ...], NoDecode] = ()

    @field_validator("supabase_url")
    @classmethod
    def require_http_url(cls, value: str) -> str:
        if not value:
            return value
        if not value.startswith(("http://", "https://")):
            raise ValueError("SUPABASE_URL must be an http(s) URL")
        return value.rstrip("/")

    @field_validator("database_url")
    @classmethod
    def require_direct_postgres_url(cls, value: str) -> str:
        if not value:
            return value
        if not value.startswith(("postgresql://", "postgresql+psycopg://", "postgres://")):
            raise ValueError("DATABASE_URL must be a postgresql URL")
        if "pooler.supabase.com" in value:
            raise ValueError(
                "DATABASE_URL must use the direct session host, not the transaction pooler"
            )
        return value

    @field_validator(
        "answer_provider",
        "answer_model",
        "gemini_api_key",
        "openrouter_api_key",
        "embedding_provider",
        "embedding_model",
    )
    @classmethod
    def strip_provider_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("embedding_dimensions", mode="before")
    @classmethod
    def blank_embedding_dimensions(cls, value: object) -> object:
        if value is None or value == "":
            return None
        return value

    @field_validator("embedding_dimensions")
    @classmethod
    def positive_embedding_dimensions(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("EMBEDDING_DIMENSIONS must be positive")
        return value

    @field_validator("embedding_provider")
    @classmethod
    def known_embedding_provider(cls, value: str) -> str:
        cleaned = value.lower()
        if cleaned and cleaned not in _EMBEDDING_PROVIDERS:
            raise ValueError("EMBEDDING_PROVIDER must be hash, openai, or openrouter")
        return cleaned

    @field_validator("answer_provider")
    @classmethod
    def known_provider(cls, value: str) -> str:
        if value not in _PROVIDERS:
            raise ValueError("ANSWER_PROVIDER must be openai, google, or openrouter")
        return value

    @field_validator("allowed_emails", mode="before")
    @classmethod
    def parse_allowed_emails(cls, value: str | list[str] | tuple[str, ...]) -> tuple[str, ...]:
        if isinstance(value, str):
            joined = value
        else:
            joined = ",".join(value)
        allow = EmailAllowList.parse(joined)
        return tuple(sorted(email.value for email in allow.emails))

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            origins = [item.strip() for item in value.split(",") if item.strip()]
        else:
            origins = [item.strip() for item in value if item.strip()]
        if not origins:
            raise ValueError("ALLOWED_ORIGINS must include at least one origin")
        return origins

    @property
    def resolved_embedding_provider(self) -> str:
        return self.embedding_provider or "openrouter"

    @property
    def resolved_embedding_model(self) -> str:
        if self.embedding_model:
            return self.embedding_model
        if self.resolved_embedding_provider == "openai":
            return self.openai_embedding_model
        return _VOYAGE_LITE

    @property
    def resolved_embedding_dimensions(self) -> int:
        if self.embedding_dimensions is not None:
            return self.embedding_dimensions
        return EMBEDDING_DIMENSIONS

    @property
    def answer_model_id(self) -> str:
        if self.answer_model:
            return model_id(self.answer_provider, self.answer_model)
        if self.answer_provider == "openai":
            return model_id(self.answer_provider, self.openai_chat_model)
        raise ValueError(f"ANSWER_MODEL is required when ANSWER_PROVIDER is {self.answer_provider}")

    @computed_field
    @property
    def sqlalchemy_database_url(self) -> str:
        url = self.database_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)
        return url


class AppMode(StrEnum):
    demo = "demo"
    live = "live"
    invalid = "invalid"

    @property
    def health_label(self) -> str:
        return "live" if self is AppMode.live else "fake"


def _live_gaps(settings: Settings) -> list[str]:
    gaps: list[str] = []
    if not settings.database_url.strip():
        gaps.append("DATABASE_URL")
    if not settings.supabase_url.strip():
        gaps.append("SUPABASE_URL")
    missing = missing_provider_key(
        settings.answer_provider,
        openai=settings.openai_api_key,
        gemini=settings.gemini_api_key,
        openrouter=settings.openrouter_api_key,
    )
    if missing is not None:
        gaps.append(missing)
    return gaps


def require_live_settings(settings: Settings) -> None:
    gaps = _live_gaps(settings)
    if gaps:
        raise RuntimeError("Live mode needs " + "; ".join(gaps) + ".")
    _ = settings.answer_model_id


def app_mode(settings: Settings) -> AppMode:
    key_missing = (
        missing_provider_key(
            settings.answer_provider,
            openai=settings.openai_api_key,
            gemini=settings.gemini_api_key,
            openrouter=settings.openrouter_api_key,
        )
        is not None
    )
    if not settings.database_url.strip() and not settings.supabase_url.strip() and key_missing:
        return AppMode.demo
    try:
        require_live_settings(settings)
    except (RuntimeError, ValueError):
        return AppMode.invalid
    return AppMode.live


def require_app_mode(settings: Settings) -> AppMode:
    mode = app_mode(settings)
    if mode is AppMode.invalid:
        try:
            require_live_settings(settings)
        except (RuntimeError, ValueError) as exc:
            raise RuntimeError(str(exc)) from None
        raise RuntimeError("Live mode settings are incomplete.")
    return mode
