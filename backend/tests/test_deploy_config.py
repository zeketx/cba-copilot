from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_RAILWAY = ROOT / "backend" / "railway.toml"
FRONTEND_RAILWAY = ROOT / "frontend" / "railway.toml"
DOCKERIGNORE = ROOT / ".dockerignore"
BACKEND_DOCKERFILE = ROOT / "backend" / "Dockerfile"
FRONTEND_DOCKERFILE = ROOT / "frontend" / "Dockerfile"
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


def test_railway_builds_each_service_from_its_dockerfile() -> None:
    assert 'dockerfilePath = "backend/Dockerfile"' in BACKEND_RAILWAY.read_text(encoding="utf-8")
    assert 'dockerfilePath = "frontend/Dockerfile"' in FRONTEND_RAILWAY.read_text(encoding="utf-8")
    assert 'healthcheckPath = "/api/health"' in BACKEND_RAILWAY.read_text(encoding="utf-8")


def test_backend_image_runs_production_uvicorn_on_port_as_non_root() -> None:
    text = BACKEND_DOCKERFILE.read_text(encoding="utf-8")
    assert "ENVIRONMENT=production" in text
    assert "uvicorn app.main:app --host 0.0.0.0 --port ${PORT" in text
    assert "COPY data/corpus.json" in text
    assert "COPY definitions/" in text
    assert "USER app" in text
    assert "data/downloads" not in text


def test_frontend_image_previews_built_app_on_port() -> None:
    text = FRONTEND_DOCKERFILE.read_text(encoding="utf-8")
    assert "pnpm build" in text
    assert "vite preview --host 0.0.0.0 --port ${PORT" in text
    assert "COPY data/corpus.json" in text
    assert "data/downloads" not in text


def test_dockerfiles_take_no_secret_build_args() -> None:
    for path in (BACKEND_DOCKERFILE, FRONTEND_DOCKERFILE):
        text = path.read_text(encoding="utf-8")
        for name in SECRET_NAMES:
            assert name not in text


def test_railway_toml_files_omit_secret_names() -> None:
    for path in (BACKEND_RAILWAY, FRONTEND_RAILWAY):
        text = path.read_text(encoding="utf-8")
        for name in SECRET_NAMES:
            assert name not in text


def test_dockerignore_excludes_env_files_and_downloads() -> None:
    text = DOCKERIGNORE.read_text(encoding="utf-8")
    for entry in DOCKERIGNORE_PATHS:
        assert entry in text
