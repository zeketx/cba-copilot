from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_RAILWAY = ROOT / "backend" / "railway.toml"
FRONTEND_RAILWAY = ROOT / "frontend" / "railway.toml"
DOCKERIGNORE = ROOT / ".dockerignore"
BACKEND_START = "uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT"
DOCKERIGNORE_PATHS = (
    ".env",
    "backend/.env",
    "frontend/.env",
    "data/downloads/",
)
SECRET_NAMES = (
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "GEMINI_API_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "DATABASE_URL",
)


def test_backend_start_command_binds_port() -> None:
    text = BACKEND_RAILWAY.read_text(encoding="utf-8")
    assert BACKEND_START in text


def test_frontend_start_command_previews_built_app() -> None:
    text = FRONTEND_RAILWAY.read_text(encoding="utf-8")
    assert "$PORT" in text
    assert "vite preview" in text


def test_railway_toml_files_omit_secret_names() -> None:
    for path in (BACKEND_RAILWAY, FRONTEND_RAILWAY):
        text = path.read_text(encoding="utf-8")
        for name in SECRET_NAMES:
            assert name not in text


def test_dockerignore_excludes_env_files_and_downloads() -> None:
    text = DOCKERIGNORE.read_text(encoding="utf-8")
    for entry in DOCKERIGNORE_PATHS:
        assert entry in text
