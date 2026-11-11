from uuid import UUID

import httpx
import pytest
from app.api import create_app
from app.auth.dependencies import gate_from_settings, http_error
from app.auth.gate import (
    AccessGate,
    GoTrueVerifier,
    MemoryLedger,
    MemoryThreads,
    RejectVerifier,
    access_request_insert,
    user_insert,
)
from app.auth.identity import (
    AppUser,
    AuthUserId,
    Email,
    EmailAllowList,
    NotThreadOwner,
    ThreadGrant,
    Unauthenticated,
    VerifiedIdentity,
)
from app.config import Settings
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql


class StaticVerifier:
    def __init__(self, tokens: dict[str, VerifiedIdentity]) -> None:
        self._tokens = tokens

    def verify(self, token: str) -> VerifiedIdentity:
        try:
            return self._tokens[token]
        except KeyError:
            raise Unauthenticated from None


def test_rejected_bearer_does_not_call_the_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("pipeline ran")

    monkeypatch.setattr("app.api.answer_question", explode)
    ledger = MemoryLedger()
    gate = AccessGate(
        allow=EmailAllowList.parse("fan@example.com"),
        verifier=StaticVerifier({}),
        ledger=ledger,
    )
    settings = Settings(
        allowed_emails=("fan@example.com",),
        supabase_url="",
        supabase_anon_key="",
        database_url="",
        _env_file=None,
    )
    client = TestClient(create_app(settings, gate=gate))
    response = client.post(
        "/api/ask",
        headers={"Authorization": "Bearer nope"},
        json={"question": "What can't a second-apron team do in a trade?"},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "unauthorized"
    assert ledger.user_ids == set()


def test_unlisted_email_does_not_insert_a_user(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("pipeline ran")

    monkeypatch.setattr("app.api.answer_question", explode)
    other = VerifiedIdentity(
        id=AuthUserId.parse("22222222-2222-2222-2222-222222222222"),
        email=Email.parse("other@example.com"),
    )
    ledger = MemoryLedger()
    gate = AccessGate(
        allow=EmailAllowList.parse("fan@example.com"),
        verifier=StaticVerifier({"other": other}),
        ledger=ledger,
    )
    client = TestClient(
        create_app(
            Settings(
                allowed_emails=(),
                supabase_url="",
                supabase_anon_key="",
                database_url="",
                _env_file=None,
            ),
            gate=gate,
        )
    )
    response = client.post(
        "/api/ask",
        headers={"Authorization": "Bearer other"},
        json={"question": "What can't a second-apron team do in a trade?"},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "not_allowed"
    assert ledger.user_ids == set()


def test_opening_another_users_thread_is_forbidden() -> None:
    viewer = VerifiedIdentity(
        id=AuthUserId.parse("11111111-1111-1111-1111-111111111111"),
        email=Email.parse("fan@example.com"),
    )
    other = AuthUserId.parse("22222222-2222-2222-2222-222222222222")
    thread_id = UUID("33333333-3333-3333-3333-333333333333")
    gate = AccessGate(
        allow=EmailAllowList.parse("fan@example.com"),
        verifier=StaticVerifier({"fan": viewer}),
        ledger=MemoryLedger(),
        threads=MemoryThreads({thread_id: other}),
    )
    client = TestClient(
        create_app(
            Settings(
                allowed_emails=(),
                supabase_url="",
                supabase_anon_key="",
                database_url="",
                _env_file=None,
            ),
            gate=gate,
        )
    )
    denied = client.get(
        f"/api/threads/{thread_id}",
        headers={"Authorization": "Bearer fan"},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["error"] == "not_owner"
    missing_token = client.get(f"/api/threads/{thread_id}")
    assert missing_token.status_code == 401
    absent = client.get(
        "/api/threads/44444444-4444-4444-4444-444444444444",
        headers={"Authorization": "Bearer fan"},
    )
    assert absent.status_code == 404
    assert absent.json()["detail"]["error"] == "not_found"


def test_opening_own_thread_returns_the_id() -> None:
    viewer = VerifiedIdentity(
        id=AuthUserId.parse("11111111-1111-1111-1111-111111111111"),
        email=Email.parse("fan@example.com"),
    )
    thread_id = UUID("33333333-3333-3333-3333-333333333333")
    gate = AccessGate(
        allow=EmailAllowList.parse("fan@example.com"),
        verifier=StaticVerifier({"fan": viewer}),
        ledger=MemoryLedger(),
        threads=MemoryThreads({thread_id: viewer.id}),
    )
    client = TestClient(
        create_app(
            Settings(
                allowed_emails=(),
                supabase_url="",
                supabase_anon_key="",
                database_url="",
                _env_file=None,
            ),
            gate=gate,
        )
    )
    response = client.get(
        f"/api/threads/{thread_id}",
        headers={"Authorization": "Bearer fan"},
    )
    assert response.status_code == 200
    assert response.json() == {"id": str(thread_id)}


def test_other_owners_thread_is_forbidden() -> None:
    viewer = AppUser(
        id=AuthUserId.parse("11111111-1111-1111-1111-111111111111"),
        email=Email.parse("fan@example.com"),
    )
    other = AuthUserId.parse("22222222-2222-2222-2222-222222222222")
    with pytest.raises(NotThreadOwner):
        ThreadGrant(viewer_id=viewer.id, owner_id=other)
    own = ThreadGrant(viewer_id=viewer.id, owner_id=viewer.id)
    assert own.viewer_id == viewer.id
    mapped = http_error(NotThreadOwner())
    assert mapped.status_code == 403
    assert mapped.detail == {"error": "not_owner"}


def test_access_request_is_idempotent_and_creates_no_user() -> None:
    ledger = MemoryLedger()
    gate = AccessGate(
        allow=EmailAllowList.parse(""),
        verifier=StaticVerifier({}),
        ledger=ledger,
    )
    client = TestClient(
        create_app(
            Settings(
                allowed_emails=(),
                supabase_url="",
                supabase_anon_key="",
                database_url="",
                _env_file=None,
            ),
            gate=gate,
        )
    )
    first = client.post("/api/access-requests", json={"email": "Fan@Example.com"})
    second = client.post("/api/access-requests", json={"email": " fan@example.com "})
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["email"] == "fan@example.com"
    assert ledger.user_ids == set()
    assert len(ledger.requests) == 1


def test_access_request_rejects_a_bad_email() -> None:
    ledger = MemoryLedger()
    gate = AccessGate(
        allow=EmailAllowList.parse(""),
        verifier=StaticVerifier({}),
        ledger=ledger,
    )
    client = TestClient(
        create_app(
            Settings(
                allowed_emails=(),
                supabase_url="",
                supabase_anon_key="",
                database_url="",
                _env_file=None,
            ),
            gate=gate,
        )
    )
    response = client.post("/api/access-requests", json={"email": "not-an-email"})
    assert response.status_code == 422
    assert ledger.user_ids == set()
    assert ledger.requests == {}


def test_gotrue_verifier_ignores_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/auth/v1/user"
        assert request.headers["apikey"] == "anon-test"
        assert request.headers["Authorization"] == "Bearer token"
        return httpx.Response(
            200,
            json={
                "id": "11111111-1111-1111-1111-111111111111",
                "email": "Fan@Example.com",
                "user_metadata": {"role": "admin"},
            },
        )

    verifier = GoTrueVerifier(
        url="https://example.test",
        anon_key="anon-test",
        transport=httpx.MockTransport(handler),
    )
    identity = verifier.verify("token")
    assert identity == VerifiedIdentity(
        id=AuthUserId.parse("11111111-1111-1111-1111-111111111111"),
        email=Email.parse("fan@example.com"),
    )


def test_reject_verifier_is_installed_without_supabase() -> None:
    with pytest.raises(Unauthenticated):
        RejectVerifier().verify("token")
    gate = gate_from_settings(
        Settings(
            allowed_emails=(),
            supabase_url="",
            supabase_anon_key="",
            database_url="",
            _env_file=None,
        )
    )
    with pytest.raises(Unauthenticated):
        gate.admit("Bearer token")
    gate_url_only = gate_from_settings(
        Settings(
            allowed_emails=(),
            supabase_url="https://example.test",
            supabase_anon_key="",
            database_url="",
            _env_file=None,
        )
    )
    with pytest.raises(Unauthenticated):
        gate_url_only.admit("Bearer token")


def test_user_insert_does_not_mention_auth_users() -> None:
    statement = user_insert(AuthUserId.parse("11111111-1111-1111-1111-111111111111"))
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert statement.table.name == "users"
    assert "auth.users" not in sql
    assert "ON CONFLICT" in sql


def test_access_request_insert_conflicts_on_email() -> None:
    statement = access_request_insert(Email.parse("fan@example.com"))
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert statement.table.name == "access_requests"
    assert "auth.users" not in sql
    assert "ON CONFLICT" in sql


def test_allowed_emails_reject_a_bad_address() -> None:
    with pytest.raises(ValidationError):
        Settings(allowed_emails="not-an-email", _env_file=None)
