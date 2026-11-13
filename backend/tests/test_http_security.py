import asyncio
import re

from app.api import create_app
from app.config import Settings
from app.corpus import pdf_url
from app.domain import Refusal
from app.http_security import SecurityHeadersMiddleware, http_origin
from fastapi.testclient import TestClient
from starlette.responses import StreamingResponse

_PDF_ORIGIN = "https://imgix.cosmicjs.com"
_SUPABASE_ORIGIN = "https://example.supabase.co"
_API_ORIGIN = "http://testserver"
_HEADER_NAMES = (
    "content-security-policy",
    "x-frame-options",
    "x-content-type-options",
    "referrer-policy",
    "strict-transport-security",
)


def _production(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "production",
        "allowed_emails": (),
        "supabase_url": "",
        "supabase_anon_key": "",
        "database_url": "",
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def _origins(policy: str) -> set[str]:
    return set(re.findall(r"https?://[^\s;]+", policy))


def _assert_headers(response: object, origins: set[str]) -> None:
    headers = response.headers
    assert headers["x-frame-options"] == "DENY"
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"
    policy = headers["content-security-policy"]
    assert "frame-ancestors 'none'" in policy
    assert "*" not in policy
    assert _origins(policy) == origins


def test_http_origin_keeps_the_origin_only() -> None:
    assert http_origin("https://proj.supabase.co/auth/v1") == "https://proj.supabase.co"
    assert http_origin(pdf_url()) == _PDF_ORIGIN
    assert http_origin("http://127.0.0.1:8000/api") == "http://127.0.0.1:8000"
    assert http_origin("") is None
    assert http_origin("javascript:alert(1)") is None


def test_environment_names_production() -> None:
    assert Settings(_env_file=None).production is False
    assert Settings(environment="production", _env_file=None).production is True
    assert Settings(environment=" Production ", _env_file=None).production is True
    assert Settings(environment="development", _env_file=None).production is False


def test_demo_keeps_openapi_routes() -> None:
    client = TestClient(create_app(Settings(_env_file=None)))
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json() == {"ok": "true", "mode": "fake"}
    for name in _HEADER_NAMES:
        assert name not in health.headers
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 200


def test_production_hides_openapi_and_sends_headers() -> None:
    client = TestClient(create_app(_production()))
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json() == {"ok": "true", "mode": "fake"}
    _assert_headers(health, {_API_ORIGIN, _PDF_ORIGIN})
    for path in ("/docs", "/redoc", "/openapi.json"):
        hidden = client.get(path)
        assert hidden.status_code == 404
        _assert_headers(hidden, {_API_ORIGIN, _PDF_ORIGIN})


def test_production_csp_allows_the_configured_origins_only() -> None:
    settings = _production(
        database_url="postgresql://postgres:pw@localhost:5432/postgres",
        supabase_url=f"{_SUPABASE_ORIGIN}/auth/v1",
        openai_api_key="sk-test",
    )

    def answer(_question: str) -> Refusal:
        raise AssertionError("answer called")

    def session_factory() -> None:
        raise AssertionError("database session opened")

    client = TestClient(create_app(settings, answer=answer, session_factory=session_factory))
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json() == {"ok": "true", "mode": "live"}
    _assert_headers(health, {_SUPABASE_ORIGIN, _API_ORIGIN, _PDF_ORIGIN})
    policy = health.headers["content-security-policy"]
    assert "default-src 'none'" in policy
    assert _SUPABASE_ORIGIN in policy
    assert "nbpa.com" not in policy
    assert "vercel" not in policy


def test_middleware_keeps_the_body_and_drops_a_bad_host() -> None:
    async def app(scope: dict[str, object], receive: object, send: object) -> None:
        del scope, receive
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"data: ok\n\n", "more_body": False})

    middleware = SecurityHeadersMiddleware(
        app,
        supabase_origin=_SUPABASE_ORIGIN,
        pdf_origin=_PDF_ORIGIN,
    )
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    asyncio.run(
        middleware(
            {
                "type": "http",
                "scheme": "https",
                "method": "GET",
                "path": "/",
                "headers": [(b"host", b"ok.com; connect-src https://evil.test")],
            },
            receive,
            send,
        )
    )
    assert sent[1]["body"] == b"data: ok\n\n"
    raw = dict(sent[0]["headers"])
    policy = raw[b"content-security-policy"].decode()
    assert _origins(policy) == {_SUPABASE_ORIGIN, _PDF_ORIGIN}
    assert "evil.test" not in policy
    assert "*" not in policy


def test_production_stream_keeps_its_body_and_headers() -> None:
    app = create_app(_production())

    @app.get("/api/stream-probe")
    def stream_probe() -> StreamingResponse:
        return StreamingResponse(iter(["data: ok\n\n"]), media_type="text/event-stream")

    client = TestClient(app)
    response = client.get("/api/stream-probe")
    assert response.status_code == 200
    assert response.text == "data: ok\n\n"
    _assert_headers(response, {_API_ORIGIN, _PDF_ORIGIN})
