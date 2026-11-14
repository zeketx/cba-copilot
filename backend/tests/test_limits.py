from uuid import uuid4

from app.api import create_app
from app.auth.gate import AccessGate, MemoryLedger
from app.auth.identity import AuthUserId, Email, EmailAllowList, Unauthenticated, VerifiedIdentity
from app.chat.log import MemoryChatLog
from app.config import Settings
from app.domain import CopilotResponse, Refusal
from app.limits import SlidingWindow, client_address
from fastapi.testclient import TestClient


class StaticVerifier:
    def __init__(self, tokens: dict[str, VerifiedIdentity]) -> None:
        self._tokens = tokens

    def verify(self, token: str) -> VerifiedIdentity:
        try:
            return self._tokens[token]
        except KeyError:
            raise Unauthenticated from None


FAN = VerifiedIdentity(
    id=AuthUserId.parse("11111111-1111-1111-1111-111111111111"),
    email=Email.parse("fan@example.com"),
)
OTHER = VerifiedIdentity(
    id=AuthUserId.parse("22222222-2222-2222-2222-222222222222"),
    email=Email.parse("other@example.com"),
)


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "allowed_emails": (),
        "supabase_url": "",
        "supabase_anon_key": "",
        "database_url": "",
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _emails(ledger: MemoryLedger) -> set[str]:
    return {email.value for email in ledger.requests}


def _access_client(**overrides: object) -> tuple[TestClient, MemoryLedger]:
    ledger = MemoryLedger()
    gate = AccessGate(
        allow=EmailAllowList.parse(""),
        verifier=StaticVerifier({}),
        ledger=ledger,
    )
    app = create_app(_settings(**overrides), gate=gate)
    return TestClient(app), ledger


def test_window_forgets_hits_after_the_interval() -> None:
    now = 0.0

    def clock() -> float:
        return now

    window = SlidingWindow(limit=1, window_seconds=10, clock=clock)
    assert window.allow("fan")
    assert not window.allow("fan")
    assert window.allow("other")
    now = 10.0
    assert window.allow("fan")


def test_answer_limit_is_per_user_and_skips_the_drafter() -> None:
    calls = {"n": 0}

    def answer(_question: str) -> CopilotResponse:
        calls["n"] += 1
        return Refusal(reason="no_evidence", message="No.")

    log = MemoryChatLog()
    thread = log.create_thread(FAN.id)
    gate = AccessGate(
        allow=EmailAllowList.parse("fan@example.com,other@example.com"),
        verifier=StaticVerifier({"fan": FAN, "other": OTHER}),
        ledger=MemoryLedger(),
        threads=log,
    )
    client = TestClient(
        create_app(
            _settings(answer_rate_limit=1),
            gate=gate,
            log=log,
            answer=answer,
        )
    )
    fan = {"Authorization": "Bearer fan"}
    asked = client.post("/api/ask", headers=fan, json={"question": "What is the cap?"})
    assert asked.status_code == 200
    blocked = client.post("/api/ask", headers=fan, json={"question": "What is the cap?"})
    assert blocked.status_code == 429
    assert blocked.json()["detail"]["error"] == "rate_limited"
    streamed = client.post(
        "/api/chat/stream",
        headers=fan,
        json={
            "threadId": str(thread.id),
            "messages": [{"id": str(uuid4()), "role": "user", "content": "What is the cap?"}],
        },
    )
    assert streamed.status_code == 429
    assert streamed.json()["detail"]["error"] == "rate_limited"
    assert calls["n"] == 1
    assert log.list_turns(thread.id) == []
    other = client.post(
        "/api/ask",
        headers={"Authorization": "Bearer other"},
        json={"question": "What is the cap?"},
    )
    assert other.status_code == 200
    assert calls["n"] == 2


def test_access_request_address_limit_is_per_socket() -> None:
    ledger = MemoryLedger()
    gate = AccessGate(
        allow=EmailAllowList.parse(""),
        verifier=StaticVerifier({}),
        ledger=ledger,
    )
    app = create_app(_settings(access_request_rate_limit=1), gate=gate)
    first = TestClient(app, client=("203.0.113.1", 50000))
    second = TestClient(app, client=("203.0.113.2", 50000))
    stored = first.post("/api/access-requests", json={"email": "a@example.com"})
    assert stored.status_code == 200
    blocked = first.post("/api/access-requests", json={"email": "b@example.com"})
    assert blocked.status_code == 429
    assert blocked.json()["detail"]["error"] == "rate_limited"
    assert _emails(ledger) == {"a@example.com"}
    other = second.post("/api/access-requests", json={"email": "c@example.com"})
    assert other.status_code == 200
    assert _emails(ledger) == {"a@example.com", "c@example.com"}


def test_forged_forwarded_for_cannot_dodge_untrusted_proxy() -> None:
    ledger = MemoryLedger()
    gate = AccessGate(
        allow=EmailAllowList.parse(""),
        verifier=StaticVerifier({}),
        ledger=ledger,
    )
    app = create_app(
        _settings(access_request_rate_limit=1, trusted_proxy_count=0),
        gate=gate,
    )
    client = TestClient(app, client=("203.0.113.1", 50000))
    stored = client.post("/api/access-requests", json={"email": "a@example.com"})
    assert stored.status_code == 200
    blocked = client.post("/api/access-requests", json={"email": "b@example.com"})
    assert blocked.status_code == 429
    forged = client.post(
        "/api/access-requests",
        headers={"X-Forwarded-For": "198.51.100.8"},
        json={"email": "b@example.com"},
    )
    assert forged.status_code == 429
    chained = client.post(
        "/api/access-requests",
        headers={"X-Forwarded-For": "198.51.100.8, 10.0.0.1"},
        json={"email": "b@example.com"},
    )
    assert chained.status_code == 429
    assert _emails(ledger) == {"a@example.com"}


def test_access_request_limit_shares_rightmost_forwarded_hop() -> None:
    client, ledger = _access_client(access_request_rate_limit=1)
    stored = client.post(
        "/api/access-requests",
        headers={"X-Forwarded-For": "198.51.100.8, 10.0.0.1"},
        json={"email": "a@example.com"},
    )
    assert stored.status_code == 200
    blocked = client.post(
        "/api/access-requests",
        headers={"X-Forwarded-For": "203.0.113.9, 10.0.0.1"},
        json={"email": "b@example.com"},
    )
    assert blocked.status_code == 429
    other = client.post(
        "/api/access-requests",
        headers={"X-Forwarded-For": "198.51.100.8, 10.0.0.2"},
        json={"email": "c@example.com"},
    )
    assert other.status_code == 200
    assert _emails(ledger) == {"a@example.com", "c@example.com"}


def test_access_request_limit_prefers_real_ip() -> None:
    client, ledger = _access_client(access_request_rate_limit=1)
    stored = client.post(
        "/api/access-requests",
        headers={
            "X-Real-IP": "203.0.113.50",
            "X-Forwarded-For": "198.51.100.8",
        },
        json={"email": "a@example.com"},
    )
    assert stored.status_code == 200
    blocked = client.post(
        "/api/access-requests",
        headers={
            "X-Real-IP": "203.0.113.50",
            "X-Forwarded-For": "198.51.100.9",
        },
        json={"email": "b@example.com"},
    )
    assert blocked.status_code == 429
    other = client.post(
        "/api/access-requests",
        headers={
            "X-Real-IP": "203.0.113.51",
            "X-Forwarded-For": "203.0.113.50",
        },
        json={"email": "c@example.com"},
    )
    assert other.status_code == 200
    assert _emails(ledger) == {"a@example.com", "c@example.com"}


def test_client_address_parses_headers() -> None:
    assert (
        client_address(
            peer="203.0.113.1",
            forwarded_for="198.51.100.8",
            real_ip="203.0.113.9",
            trusted_proxy_count=0,
        )
        == "203.0.113.1"
    )
    assert (
        client_address(peer=None, forwarded_for="198.51.100.8", trusted_proxy_count=0) == "unknown"
    )
    assert (
        client_address(
            peer="10.0.0.1",
            forwarded_for="198.51.100.8, 10.0.0.1",
            real_ip=" 203.0.113.9 ",
            trusted_proxy_count=1,
        )
        == "203.0.113.9"
    )
    assert (
        client_address(
            peer="10.0.0.1",
            forwarded_for="198.51.100.8, 10.0.0.1",
            trusted_proxy_count=1,
        )
        == "10.0.0.1"
    )
    assert (
        client_address(
            peer="10.0.0.1",
            forwarded_for="198.51.100.8, 10.0.0.1",
            trusted_proxy_count=2,
        )
        == "198.51.100.8"
    )
    assert (
        client_address(
            peer="10.0.0.1",
            forwarded_for="198.51.100.8",
            trusted_proxy_count=2,
        )
        == "198.51.100.8"
    )
    assert client_address(peer="10.0.0.1", forwarded_for="", trusted_proxy_count=1) == "10.0.0.1"
    assert (
        client_address(peer=None, forwarded_for="", real_ip="", trusted_proxy_count=1) == "unknown"
    )


def test_access_request_cap_does_not_store_another_row() -> None:
    ledger = MemoryLedger()
    gate = AccessGate(
        allow=EmailAllowList.parse(""),
        verifier=StaticVerifier({}),
        ledger=ledger,
    )
    client = TestClient(
        create_app(
            _settings(access_request_rate_limit=10, access_request_cap=1),
            gate=gate,
        )
    )
    first = client.post("/api/access-requests", json={"email": "A@Example.com"})
    assert first.status_code == 200
    blocked = client.post("/api/access-requests", json={"email": "b@example.com"})
    assert blocked.status_code == 429
    assert blocked.json()["detail"]["error"] == "access_requests_full"
    assert _emails(ledger) == {"a@example.com"}
    repeat = client.post("/api/access-requests", json={"email": " a@example.com "})
    assert repeat.status_code == 200
    assert repeat.json() == first.json()
    assert _emails(ledger) == {"a@example.com"}
