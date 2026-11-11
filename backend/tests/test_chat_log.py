from uuid import UUID, uuid4

import pytest
from app.auth.gate import AccessGate, MemoryLedger
from app.auth.identity import (
    AppUser,
    AuthUserId,
    Email,
    EmailAllowList,
    MissingThread,
    NotThreadOwner,
    Unauthenticated,
    VerifiedIdentity,
)
from app.chat.log import MemoryChatLog
from app.chat.model import uuid_chunk_ids
from app.chat.service import ThreadChat
from app.domain import CITATIONS_DROPPED_MESSAGE, CitedAnswer, Claim, Refusal


class StaticVerifier:
    def __init__(self, tokens: dict[str, VerifiedIdentity]) -> None:
        self._tokens = tokens

    def verify(self, token: str) -> VerifiedIdentity:
        try:
            return self._tokens[token]
        except KeyError:
            raise Unauthenticated from None


def _user(suffix: str) -> AppUser:
    return AppUser(
        id=AuthUserId.parse(f"{suffix * 8}-{'1' * 4}-{'1' * 4}-{'1' * 4}-{'1' * 12}"),
        email=Email.parse(f"{suffix}@example.com"),
    )


def _gate(log: MemoryChatLog, *users: AppUser) -> AccessGate:
    tokens = {
        user.email.value: VerifiedIdentity(id=user.id, email=user.email) for user in users
    }
    allow = ",".join(user.email.value for user in users)
    return AccessGate(
        allow=EmailAllowList.parse(allow),
        verifier=StaticVerifier(tokens),
        ledger=MemoryLedger(),
        threads=log,
    )


def test_create_and_list_only_the_owners_threads() -> None:
    log = MemoryChatLog()
    owner = _user("a")
    other = _user("b")
    first = log.create_thread(owner.id)
    second = log.create_thread(owner.id)
    outsider = log.create_thread(other.id)
    listed = log.list_threads(owner.id)
    assert [item.id for item in listed] == [second.id, first.id]
    assert outsider.id not in {item.id for item in listed}
    assert [item.id for item in log.list_threads(other.id)] == [outsider.id]


def test_commit_stores_a_refusal_and_an_answer() -> None:
    log = MemoryChatLog()
    owner = _user("a")
    thread = log.create_thread(owner.id)
    refusal = log.commit_turn(
        owner.id,
        thread.id,
        uuid4(),
        "How many timeouts may an NHL coach call?",
        Refusal(reason="no_evidence", message="No CBA passage covers that."),
    )
    answer = log.commit_turn(
        owner.id,
        thread.id,
        uuid4(),
        "What can't a second-apron team do in a trade?",
        CitedAnswer(claims=[Claim(text="They cannot aggregate.", passage_ids=["apron-trades"])]),
    )
    assert refusal.outcome.kind == "refusal"
    assert answer.outcome.kind == "answer"
    assert [turn.turn_id for turn in log.list_turns(thread.id)] == [
        refusal.turn_id,
        answer.turn_id,
    ]


def test_ask_is_idempotent_on_turn_id() -> None:
    log = MemoryChatLog()
    owner = _user("a")
    thread = log.create_thread(owner.id)
    calls = {"n": 0}

    def answer(question: str) -> Refusal:
        calls["n"] += 1
        return Refusal(reason="no_evidence", message=question)

    chat = ThreadChat(_gate(log, owner), log, answer)
    turn_id = uuid4()
    first = chat.ask(owner, thread.id, turn_id, "same question")
    second = chat.ask(owner, thread.id, turn_id, "same question")
    assert first == second
    assert calls["n"] == 1
    assert first.user_position == 0
    assert first.assistant_position == 1


def test_positions_are_even_then_odd_pairs() -> None:
    log = MemoryChatLog()
    owner = _user("a")
    thread = log.create_thread(owner.id)
    first = log.commit_turn(
        owner.id,
        thread.id,
        uuid4(),
        "first",
        Refusal(reason="no_evidence", message="first"),
    )
    second = log.commit_turn(
        owner.id,
        thread.id,
        uuid4(),
        "second",
        Refusal(reason="citations_dropped", message=CITATIONS_DROPPED_MESSAGE),
    )
    assert (first.user_position, first.assistant_position) == (0, 1)
    assert (second.user_position, second.assistant_position) == (2, 3)


def test_same_turn_id_on_another_thread_is_rejected() -> None:
    log = MemoryChatLog()
    owner = _user("a")
    first = log.create_thread(owner.id)
    second = log.create_thread(owner.id)
    turn_id = uuid4()
    stored = log.commit_turn(
        owner.id,
        first.id,
        turn_id,
        "first thread",
        Refusal(reason="no_evidence", message="first"),
    )
    with pytest.raises(KeyError):
        log.commit_turn(
            owner.id,
            second.id,
            turn_id,
            "second thread",
            Refusal(reason="no_evidence", message="second"),
        )
    assert log.get_turn(first.id, turn_id) == stored
    assert log.get_turn(second.id, turn_id) is None


def test_another_user_cannot_ask_before_commit() -> None:
    log = MemoryChatLog()
    owner = _user("a")
    stranger = _user("b")
    thread = log.create_thread(owner.id)
    calls = {"n": 0}

    def answer(_question: str) -> Refusal:
        calls["n"] += 1
        return Refusal(reason="no_evidence", message="should not run")

    chat = ThreadChat(_gate(log, owner, stranger), log, answer)
    with pytest.raises(NotThreadOwner):
        chat.ask(stranger, thread.id, uuid4(), "secret")
    assert calls["n"] == 0
    assert log.list_turns(thread.id) == []


def test_missing_thread_raises_before_commit() -> None:
    log = MemoryChatLog()
    owner = _user("a")
    calls = {"n": 0}

    def answer(_question: str) -> Refusal:
        calls["n"] += 1
        return Refusal(reason="no_evidence", message="should not run")

    chat = ThreadChat(_gate(log, owner), log, answer)
    with pytest.raises(MissingThread):
        chat.ask(owner, uuid4(), uuid4(), "missing")
    assert calls["n"] == 0


def test_uuid_chunk_ids_drop_slugs_and_keep_uuids() -> None:
    assert uuid_chunk_ids(["apron-trades"]) == []
    passage = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert uuid_chunk_ids([str(passage)]) == [passage]
    assert uuid_chunk_ids([str(passage), "apron-trades"]) == []
