import pytest
from app.config import Settings, missing_provider_key
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


def test_missing_provider_key_names_the_env_var() -> None:
    message = missing_provider_key("google", openai="", gemini="", openrouter="")
    assert message is not None
    assert "GEMINI_API_KEY" in message
