import json
from uuid import uuid4

from app.api import create_app
from app.auth.gate import AccessGate, MemoryLedger
from app.auth.identity import AuthUserId, Email, EmailAllowList, Unauthenticated, VerifiedIdentity
from app.chat.log import MemoryChatLog
from app.chat.service import AnswerFn
from app.config import Settings
from app.demo import load_demo_chunks
from app.domain import AMBIGUOUS_MESSAGE, Claim, Clarification, CopilotResponse, Refusal
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


def _settings() -> Settings:
    return Settings(
        allowed_emails=(),
        supabase_url="",
        supabase_anon_key="",
        database_url="",
        _env_file=None,
    )


def _client(
    log: MemoryChatLog | None = None,
    *,
    answer: AnswerFn | None = None,
) -> tuple[TestClient, MemoryChatLog]:
    chat_log = log if log is not None else MemoryChatLog()
    gate = AccessGate(
        allow=EmailAllowList.parse("fan@example.com,other@example.com"),
        verifier=StaticVerifier({"fan": FAN, "other": OTHER}),
        ledger=MemoryLedger(),
        threads=chat_log,
    )
    return TestClient(create_app(_settings(), gate=gate, log=chat_log, answer=answer)), chat_log


def _events(body: str) -> list[tuple[str, dict[str, object]]]:
    events: list[tuple[str, dict[str, object]]] = []
    for block in body.strip().split("\n\n"):
        if not block.strip():
            continue
        name = "message"
        payload: dict[str, object] | None = None
        for line in block.split("\n"):
            if line.startswith("event:"):
                name = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                payload = json.loads(line.removeprefix("data:").strip())
        if payload is not None:
            events.append((name, payload))
    return events


def test_me_returns_the_verified_email() -> None:
    client, _log = _client()
    response = client.get("/api/me", headers={"Authorization": "Bearer fan"})
    assert response.status_code == 200
    assert response.json() == {"email": "fan@example.com"}


def test_me_without_a_token_is_unauthorized() -> None:
    client, _log = _client()
    response = client.get("/api/me")
    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "unauthorized"


def test_stream_without_a_token_is_unauthorized() -> None:
    client, log = _client()
    thread = log.create_thread(FAN.id)
    response = client.post(
        "/api/chat/stream",
        json={
            "threadId": str(thread.id),
            "messages": [{"id": str(uuid4()), "role": "user", "content": "Hello"}],
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "unauthorized"


def test_stream_for_another_owner_is_forbidden() -> None:
    client, log = _client()
    thread = log.create_thread(FAN.id)
    response = client.post(
        "/api/chat/stream",
        headers={"Authorization": "Bearer other"},
        json={
            "threadId": str(thread.id),
            "messages": [{"id": str(uuid4()), "role": "user", "content": "Hello"}],
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "not_owner"


def test_stream_for_a_missing_thread_is_not_found() -> None:
    client, _log = _client()
    response = client.post(
        "/api/chat/stream",
        headers={"Authorization": "Bearer fan"},
        json={
            "threadId": str(uuid4()),
            "messages": [{"id": str(uuid4()), "role": "user", "content": "Hello"}],
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "not_found"


def test_stream_rejects_a_bad_body() -> None:
    client, log = _client()
    thread = log.create_thread(FAN.id)
    response = client.post(
        "/api/chat/stream",
        headers={"Authorization": "Bearer fan"},
        json={
            "threadId": str(thread.id),
            "messages": [{"id": str(uuid4()), "role": "assistant", "content": "Hi"}],
        },
    )
    assert response.status_code == 422


def test_streamed_refusal_and_reload() -> None:
    client, _log = _client()
    created = client.post("/api/threads", headers={"Authorization": "Bearer fan"})
    assert created.status_code == 200
    thread_id = created.json()["id"]
    turn_id = str(uuid4())
    question = "How many timeouts may an NHL coach call during a playoff overtime?"
    response = client.post(
        "/api/chat/stream",
        headers={"Authorization": "Bearer fan"},
        json={
            "threadId": thread_id,
            "messages": [{"id": turn_id, "role": "user", "content": question}],
        },
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    events = _events(response.text)
    names = [name for name, _payload in events]
    assert names[0] == "delta"
    assert names[-1] == "done"
    assert "citations" not in names
    done = events[-1][1]
    assert done["thread_id"] == thread_id
    assert done["turn_id"] == turn_id
    assert done["response"]["kind"] == "refusal"
    text = "".join(payload["text"] for name, payload in events if name == "delta")
    assert text == done["response"]["message"]
    reloaded = client.get(
        f"/api/threads/{thread_id}/messages",
        headers={"Authorization": "Bearer fan"},
    )
    assert reloaded.status_code == 200
    messages = reloaded.json()
    assert messages[0] == {"id": turn_id, "role": "user", "position": 0, "text": question}
    assert messages[1]["role"] == "assistant"
    assert messages[1]["position"] == 1
    assert messages[1]["response"] == done["response"]
    listed = client.get("/api/threads", headers={"Authorization": "Bearer fan"})
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == thread_id
    opened = client.get(f"/api/threads/{thread_id}", headers={"Authorization": "Bearer fan"})
    assert opened.json() == {"id": thread_id}


def test_streamed_answer_includes_citations() -> None:
    client, _log = _client()
    thread_id = client.post("/api/threads", headers={"Authorization": "Bearer fan"}).json()["id"]
    turn_id = str(uuid4())
    response = client.post(
        "/api/chat/stream",
        headers={"Authorization": "Bearer fan"},
        json={
            "threadId": thread_id,
            "messages": [
                {
                    "id": turn_id,
                    "role": "user",
                    "content": "What can't a second-apron team do in a trade?",
                }
            ],
        },
    )
    assert response.status_code == 200
    events = _events(response.text)
    names = [name for name, _payload in events]
    assert "delta" in names
    assert "citations" in names
    assert names[-1] == "done"
    done = events[-1][1]
    assert done["response"]["kind"] == "answer"
    citations = next(payload for name, payload in events if name == "citations")
    assert citations["claims"] == done["response"]["claims"]
    reloaded = client.get(
        f"/api/threads/{thread_id}/messages",
        headers={"Authorization": "Bearer fan"},
    )
    assert reloaded.json()[1]["response"]["kind"] == "answer"
    other = client.get("/api/threads", headers={"Authorization": "Bearer other"})
    assert other.json() == []


def test_list_does_not_include_another_users_thread() -> None:
    client, log = _client()
    hidden = log.create_thread(OTHER.id)
    visible = log.create_thread(FAN.id)
    listed = client.get("/api/threads", headers={"Authorization": "Bearer fan"})
    ids = {item["id"] for item in listed.json()}
    assert str(visible.id) in ids
    assert str(hidden.id) not in ids
    denied = client.get(
        f"/api/threads/{hidden.id}/messages",
        headers={"Authorization": "Bearer fan"},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["error"] == "not_owner"
    missing = client.get(
        f"/api/threads/{uuid4()}/messages",
        headers={"Authorization": "Bearer fan"},
    )
    assert missing.status_code == 404


def test_stream_answer_emits_deltas_then_citations_then_done() -> None:
    client, _log = _client()
    thread_id = client.post("/api/threads", headers={"Authorization": "Bearer fan"}).json()["id"]
    response = client.post(
        "/api/chat/stream",
        headers={"Authorization": "Bearer fan"},
        json={
            "threadId": thread_id,
            "messages": [
                {
                    "id": str(uuid4()),
                    "role": "user",
                    "content": "What can't a second-apron team do in a trade?",
                }
            ],
        },
    )
    assert response.status_code == 200
    names = [name for name, _payload in _events(response.text)]
    first_delta = names.index("delta")
    citations = names.index("citations")
    done = names.index("done")
    assert first_delta < citations < done
    assert max(index for index, name in enumerate(names) if name == "delta") < citations


def test_failed_answer_is_502_leaves_no_messages_and_retries() -> None:
    log = MemoryChatLog()
    calls = {"n": 0}

    def answer(_question: str) -> CopilotResponse:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("drafter exploded")
        return Refusal(reason="no_evidence", message="Recovered.")

    client, _log = _client(log, answer=answer)
    thread_id = client.post("/api/threads", headers={"Authorization": "Bearer fan"}).json()["id"]
    turn_id = str(uuid4())
    body = {
        "threadId": thread_id,
        "messages": [{"id": turn_id, "role": "user", "content": "What is the cap?"}],
    }
    failed = client.post(
        "/api/chat/stream",
        headers={"Authorization": "Bearer fan"},
        json=body,
    )
    assert failed.status_code == 502
    assert failed.json()["detail"]["error"] == "answer_failed"
    empty = client.get(
        f"/api/threads/{thread_id}/messages",
        headers={"Authorization": "Bearer fan"},
    )
    assert empty.status_code == 200
    assert empty.json() == []
    retried = client.post(
        "/api/chat/stream",
        headers={"Authorization": "Bearer fan"},
        json=body,
    )
    assert retried.status_code == 200
    events = _events(retried.text)
    assert events[-1][0] == "done"
    assert events[-1][1]["response"]["kind"] == "refusal"
    loaded = client.get(
        f"/api/threads/{thread_id}/messages",
        headers={"Authorization": "Bearer fan"},
    )
    assert loaded.json()[0]["id"] == turn_id
    assert loaded.json()[1]["response"]["kind"] == "refusal"


def test_streamed_clarification_then_reload() -> None:
    bird = next(chunk for chunk in load_demo_chunks() if chunk.id == "bird")
    early = next(chunk for chunk in load_demo_chunks() if chunk.id == "early-bird")

    def answer(_question: str) -> CopilotResponse:
        return Clarification(
            reason="ambiguous",
            message=AMBIGUOUS_MESSAGE,
            claims=[
                Claim(text="Bird rights.", passage_ids=[bird.id]),
                Claim(text="Early Bird rights.", passage_ids=[early.id]),
            ],
        )

    client, _log = _client(answer=answer)
    thread_id = client.post("/api/threads", headers={"Authorization": "Bearer fan"}).json()["id"]
    turn_id = str(uuid4())
    response = client.post(
        "/api/chat/stream",
        headers={"Authorization": "Bearer fan"},
        json={
            "threadId": thread_id,
            "messages": [{"id": turn_id, "role": "user", "content": "Which Bird rights?"}],
        },
    )
    assert response.status_code == 200
    events = _events(response.text)
    names = [name for name, _payload in events]
    assert names[0] == "delta"
    assert "citations" in names
    assert names[-1] == "done"
    assert max(index for index, name in enumerate(names) if name == "delta") < names.index(
        "citations"
    )
    assert names.index("citations") < names.index("done")
    done = events[-1][1]
    assert done["response"]["kind"] == "clarification"
    text = "".join(payload["text"] for name, payload in events if name == "delta")
    assert text == done["response"]["message"] == AMBIGUOUS_MESSAGE
    citations = next(payload for name, payload in events if name == "citations")
    assert citations["claims"] == done["response"]["claims"]
    reloaded = client.get(
        f"/api/threads/{thread_id}/messages",
        headers={"Authorization": "Bearer fan"},
    )
    assert reloaded.json()[1]["response"]["kind"] == "clarification"


def test_rename_shows_in_thread_list() -> None:
    client, _log = _client()
    thread_id = client.post("/api/threads", headers={"Authorization": "Bearer fan"}).json()["id"]
    renamed = client.patch(
        f"/api/threads/{thread_id}",
        headers={"Authorization": "Bearer fan"},
        json={"title": "  Apron trades  "},
    )
    assert renamed.status_code == 200
    assert renamed.json()["id"] == thread_id
    assert renamed.json()["title"] == "Apron trades"
    listed = client.get("/api/threads", headers={"Authorization": "Bearer fan"})
    assert listed.json()[0]["id"] == thread_id
    assert listed.json()[0]["title"] == "Apron trades"


def test_blank_title_is_unprocessable() -> None:
    client, _log = _client()
    thread_id = client.post("/api/threads", headers={"Authorization": "Bearer fan"}).json()["id"]
    blank = client.patch(
        f"/api/threads/{thread_id}",
        headers={"Authorization": "Bearer fan"},
        json={"title": "   "},
    )
    assert blank.status_code == 422
    too_long = client.patch(
        f"/api/threads/{thread_id}",
        headers={"Authorization": "Bearer fan"},
        json={"title": "a" * 81},
    )
    assert too_long.status_code == 422
    listed = client.get("/api/threads", headers={"Authorization": "Bearer fan"})
    assert listed.json()[0]["title"] == ""


def test_delete_removes_thread_and_messages() -> None:
    client, _log = _client()
    thread_id = client.post("/api/threads", headers={"Authorization": "Bearer fan"}).json()["id"]
    deleted = client.delete(
        f"/api/threads/{thread_id}",
        headers={"Authorization": "Bearer fan"},
    )
    assert deleted.status_code == 204
    listed = client.get("/api/threads", headers={"Authorization": "Bearer fan"})
    assert listed.json() == []
    missing = client.get(
        f"/api/threads/{thread_id}/messages",
        headers={"Authorization": "Bearer fan"},
    )
    assert missing.status_code == 404
    assert missing.json()["detail"]["error"] == "not_found"


def test_rename_and_delete_are_forbidden_for_another_user() -> None:
    client, log = _client()
    thread = log.create_thread(FAN.id)
    renamed = client.patch(
        f"/api/threads/{thread.id}",
        headers={"Authorization": "Bearer other"},
        json={"title": "stolen"},
    )
    assert renamed.status_code == 403
    assert renamed.json()["detail"]["error"] == "not_owner"
    deleted = client.delete(
        f"/api/threads/{thread.id}",
        headers={"Authorization": "Bearer other"},
    )
    assert deleted.status_code == 403
    assert deleted.json()["detail"]["error"] == "not_owner"
    listed = client.get("/api/threads", headers={"Authorization": "Bearer fan"})
    assert listed.json()[0]["id"] == str(thread.id)
    assert listed.json()[0]["title"] == ""


def test_rename_and_delete_missing_thread_are_not_found() -> None:
    client, _log = _client()
    missing_id = uuid4()
    renamed = client.patch(
        f"/api/threads/{missing_id}",
        headers={"Authorization": "Bearer fan"},
        json={"title": "gone"},
    )
    assert renamed.status_code == 404
    assert renamed.json()["detail"]["error"] == "not_found"
    deleted = client.delete(
        f"/api/threads/{missing_id}",
        headers={"Authorization": "Bearer fan"},
    )
    assert deleted.status_code == 404
    assert deleted.json()["detail"]["error"] == "not_found"
