from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from app.auth.identity import (
    AccessRequest,
    AppUser,
    AuthBackendDown,
    AuthUserId,
    Email,
    EmailAllowList,
    MissingThread,
    NotAllowed,
    ThreadGrant,
    Unauthenticated,
    VerifiedIdentity,
)


class Verifier(Protocol):
    def verify(self, token: str) -> VerifiedIdentity: ...


class Ledger(Protocol):
    def submit(self, email: Email) -> AccessRequest: ...

    def ensure_user(self, user_id: AuthUserId) -> None: ...


class ThreadDirectory(Protocol):
    def owner_id(self, thread_id: UUID) -> AuthUserId | None: ...


class MemoryThreads:
    def __init__(self, owners: dict[UUID, AuthUserId] | None = None) -> None:
        self._owners = dict(owners or {})

    def owner_id(self, thread_id: UUID) -> AuthUserId | None:
        return self._owners.get(thread_id)


class SqlThreads:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._engine: Engine | None = None

    def owner_id(self, thread_id: UUID) -> AuthUserId | None:
        from app.database.models import ChatThread

        engine = self._engine
        if engine is None:
            engine = create_engine(self._database_url)
            self._engine = engine
        with engine.connect() as connection:
            row = connection.execute(
                select(ChatThread.user_id).where(ChatThread.id == thread_id)
            ).one_or_none()
        if row is None:
            return None
        return AuthUserId(value=row.user_id)


class AccessGate:
    def __init__(
        self,
        *,
        allow: EmailAllowList,
        verifier: Verifier,
        ledger: Ledger,
        threads: ThreadDirectory | None = None,
    ) -> None:
        self._allow = allow
        self._verifier = verifier
        self._ledger = ledger
        self._threads = threads if threads is not None else MemoryThreads()

    def open_thread(self, viewer: AppUser, thread_id: UUID) -> ThreadGrant:
        owner = self._threads.owner_id(thread_id)
        if owner is None:
            raise MissingThread
        return ThreadGrant(viewer_id=viewer.id, owner_id=owner)

    def submit(self, email: Email) -> AccessRequest:
        return self._ledger.submit(email)

    def admit(self, authorization: str | None) -> AppUser:
        token = parse_bearer(authorization)
        identity = self._verifier.verify(token)
        if identity.email not in self._allow.emails:
            raise NotAllowed
        self._ledger.ensure_user(identity.id)
        return AppUser(id=identity.id, email=identity.email)


def parse_bearer(header: str | None) -> str:
    if header is None:
        raise Unauthenticated
    scheme, separator, token = header.partition(" ")
    if separator != " " or scheme != "Bearer" or not token or " " in token:
        raise Unauthenticated
    return token


def identity_from_user_payload(payload: dict[str, object]) -> VerifiedIdentity:
    raw_id = payload.get("id")
    raw_email = payload.get("email")
    if not isinstance(raw_id, str) or not isinstance(raw_email, str):
        raise Unauthenticated
    try:
        return VerifiedIdentity(id=AuthUserId.parse(raw_id), email=Email.parse(raw_email))
    except ValueError:
        raise Unauthenticated from None


class RejectVerifier:
    def verify(self, token: str) -> VerifiedIdentity:
        raise Unauthenticated


class GoTrueVerifier:
    def __init__(
        self,
        *,
        url: str,
        anon_key: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._anon_key = anon_key
        self._client = httpx.Client(
            base_url=url.rstrip("/"),
            timeout=5.0,
            transport=transport,
        )

    def verify(self, token: str) -> VerifiedIdentity:
        try:
            response = self._client.get(
                "/auth/v1/user",
                headers={
                    "apikey": self._anon_key,
                    "Authorization": f"Bearer {token}",
                },
            )
        except httpx.TimeoutException:
            raise AuthBackendDown from None
        except httpx.HTTPError:
            raise AuthBackendDown from None
        if response.status_code in (401, 403):
            raise Unauthenticated
        if response.status_code != 200:
            raise AuthBackendDown
        try:
            payload = response.json()
        except ValueError:
            raise Unauthenticated from None
        if not isinstance(payload, dict):
            raise Unauthenticated
        return identity_from_user_payload(payload)


class MemoryLedger:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._user_ids: set[AuthUserId] = set()
        self._requests: dict[Email, AccessRequest] = {}

    @property
    def user_ids(self) -> set[AuthUserId]:
        with self._lock:
            return set(self._user_ids)

    @property
    def requests(self) -> dict[Email, AccessRequest]:
        with self._lock:
            return dict(self._requests)

    def submit(self, email: Email) -> AccessRequest:
        with self._lock:
            stored = self._requests.get(email)
            if stored is not None:
                return stored
            record = AccessRequest(email=email, created_at=datetime.now(timezone.utc))
            self._requests[email] = record
            return record

    def ensure_user(self, user_id: AuthUserId) -> None:
        with self._lock:
            self._user_ids.add(user_id)


class SqlLedger:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._engine: Engine | None = None

    def _connect(self) -> Engine:
        if self._engine is None:
            self._engine = create_engine(self._database_url)
        return self._engine

    def submit(self, email: Email) -> AccessRequest:
        from app.database.models import AccessRequestRecord

        engine = self._connect()
        with engine.begin() as connection:
            connection.execute(access_request_insert(email))
            row = connection.execute(
                select(AccessRequestRecord.email, AccessRequestRecord.created_at).where(
                    AccessRequestRecord.email == email.value
                )
            ).one()
        return AccessRequest(email=Email.parse(row.email), created_at=row.created_at)

    def ensure_user(self, user_id: AuthUserId) -> None:
        engine = self._connect()
        with engine.begin() as connection:
            connection.execute(user_insert(user_id))


def user_insert(user_id: AuthUserId):
    from app.database.models import User

    return pg_insert(User.__table__).values(id=user_id.value).on_conflict_do_nothing(
        index_elements=["id"]
    )


def access_request_insert(email: Email):
    from app.database.models import AccessRequestRecord

    return (
        pg_insert(AccessRequestRecord.__table__)
        .values(email=email.value)
        .on_conflict_do_nothing(index_elements=["email"])
    )
