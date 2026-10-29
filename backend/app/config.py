from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.database.constants import EMBEDDING_DIMENSIONS

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROVIDERS = {"openai", "google", "openrouter"}


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
    openai_embedding_dimensions: int = Field(default=EMBEDDING_DIMENSIONS, gt=0)
    answer_provider: str = "openai"
    answer_model: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""

    retrieval_candidate_k: int = 50
    retrieval_top_k: int = 8
    retrieval_rrf_k: int = 60
    retrieval_fts_config: str = "english"

    allowed_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

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

    @field_validator("answer_provider", "answer_model", "gemini_api_key", "openrouter_api_key")
    @classmethod
    def strip_provider_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("answer_provider")
    @classmethod
    def known_provider(cls, value: str) -> str:
        if value not in _PROVIDERS:
            raise ValueError("ANSWER_PROVIDER must be openai, google, or openrouter")
        return value

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


def require_live_settings(settings: Settings) -> None:
    missing = missing_provider_key(
        settings.answer_provider,
        openai=settings.openai_api_key,
        gemini=settings.gemini_api_key,
        openrouter=settings.openrouter_api_key,
    )
    if missing is not None:
        raise RuntimeError(missing)
    if not settings.database_url or not settings.supabase_url:
        raise RuntimeError("Live mode needs DATABASE_URL and SUPABASE_URL.")
    _ = settings.answer_model_id
