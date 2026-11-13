import pytest
from app.api import create_app
from app.config import AppMode, Settings, app_mode, missing_provider_key, require_app_mode
from pydantic import ValidationError


def test_openai_answer_id_uses_the_chat_model() -> None:
    settings = Settings(answer_provider="openai", answer_model="", openai_chat_model="gpt-4o")
    assert settings.answer_model_id == "gpt-4o"
    assert settings.openai_embedding_model == "text-embedding-3-small"
    assert settings.openai_embedding_dimensions == 1536


def test_named_answer_model_keeps_the_provider_prefix() -> None:
    settings = Settings(answer_provider="openrouter", answer_model="openai/gpt-4o")
    assert settings.answer_model_id == "openrouter:openai/gpt-4o"


def test_google_without_a_model_name_fails() -> None:
    settings = Settings(answer_provider="google", answer_model="")
    with pytest.raises(ValueError):
        _ = settings.answer_model_id


def test_unknown_provider_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(answer_provider="anthropic")


def test_pooler_url_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(database_url="postgresql://postgres:pw@pooler.supabase.com:6543/postgres")


def test_embedding_settings_default_to_voyage_lite() -> None:
    settings = Settings(_env_file=None)
    assert settings.embedding_provider == "openrouter"
    assert settings.embedding_model == "mongodb/voyage-4-lite"
    assert settings.embedding_dimensions == 1024
    assert settings.resolved_embedding_provider == "openrouter"
    assert settings.resolved_embedding_model == "mongodb/voyage-4-lite"
    assert settings.resolved_embedding_dimensions == 1024
    assert settings.openai_embedding_dimensions == 1536


def test_blank_embedding_fields_resolve_to_voyage() -> None:
    settings = Settings(
        embedding_provider="",
        embedding_model="",
        embedding_dimensions="",
        _env_file=None,
    )
    assert settings.resolved_embedding_provider == "openrouter"
    assert settings.resolved_embedding_model == "mongodb/voyage-4-lite"
    assert settings.resolved_embedding_dimensions == 1024
    assert settings.embedding_dimensions is None


def test_openai_embedding_provider_keeps_the_openai_model() -> None:
    settings = Settings(embedding_provider="openai", embedding_model="", _env_file=None)
    assert settings.resolved_embedding_provider == "openai"
    assert settings.resolved_embedding_model == "text-embedding-3-small"


def test_generic_embedding_settings_override_the_openai_names() -> None:
    settings = Settings(
        embedding_provider="OpenRouter",
        embedding_model="qwen/qwen3-embedding-8b",
        embedding_dimensions=4096,
    )
    assert settings.resolved_embedding_provider == "openrouter"
    assert settings.resolved_embedding_model == "qwen/qwen3-embedding-8b"
    assert settings.resolved_embedding_dimensions == 4096
    assert settings.openai_embedding_model == "text-embedding-3-small"
    assert settings.openai_embedding_dimensions == 1536


def test_unknown_embedding_provider_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(embedding_provider="cohere")


def test_context_caps_default_with_the_rrf_constant() -> None:
    settings = Settings(_env_file=None)
    assert settings.retrieval_rrf_k == 60
    assert settings.retrieval_context_per_hit == 4
    assert settings.retrieval_context_max == 16


def test_missing_provider_key_names_the_env_var() -> None:
    message = missing_provider_key("google", openai="", gemini="", openrouter="")
    assert message is not None
    assert "GEMINI_API_KEY" in message


def test_empty_settings_are_demo() -> None:
    settings = Settings(_env_file=None)
    assert app_mode(settings) is AppMode.demo
    assert AppMode.demo.health_label == "fake"


def test_complete_settings_are_live() -> None:
    settings = Settings(
        database_url="postgresql://postgres:pw@localhost:5432/postgres",
        supabase_url="https://example.supabase.co",
        openai_api_key="sk-test",
        _env_file=None,
    )
    assert app_mode(settings) is AppMode.live
    assert AppMode.live.health_label == "live"


def test_half_settings_startup_names_supabase_url() -> None:
    settings = Settings(
        database_url="postgresql://postgres:pw@localhost:5432/postgres",
        supabase_url="",
        openai_api_key="",
        _env_file=None,
    )
    assert app_mode(settings) is AppMode.invalid
    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        require_app_mode(settings)
    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        create_app(settings)
