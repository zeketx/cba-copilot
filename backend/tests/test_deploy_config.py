from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_TOML = ROOT / "backend" / "railway.toml"
FRONTEND_TOML = ROOT / "frontend" / "railway.toml"
DOCKERIGNORE = ROOT / ".dockerignore"
SECRET_MARKERS = (
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "GEMINI_API_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "DATABASE_URL",
)


def test_backend_start_command_listens_on_port() -> None:
    text = BACKEND_TOML.read_text(encoding="utf-8")
    assert "uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT" in text
    for marker in SECRET_MARKERS:
        assert marker not in text


def test_frontend_start_command_previews_on_port() -> None:
    text = FRONTEND_TOML.read_text(encoding="utf-8")
    assert "$PORT" in text
    assert "vite preview" in text
    for marker in SECRET_MARKERS:
        assert marker not in text


def test_dockerignore_excludes_env_and_downloads() -> None:
    text = DOCKERIGNORE.read_text(encoding="utf-8")
    for path in (".env", "backend/.env", "frontend/.env", "data/downloads/"):
        assert path in text
