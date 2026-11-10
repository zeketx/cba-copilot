from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True, slots=True)
class Email:
    value: str

    def __post_init__(self) -> None:
        if self.value != self.value.strip().lower() or not _EMAIL.fullmatch(self.value):
            raise ValueError("invalid email")

    @staticmethod
    def parse(raw: str) -> Email:
        return Email(raw.strip().lower())


@dataclass(frozen=True, slots=True)
class AuthUserId:
    value: UUID

    @staticmethod
    def parse(raw: str) -> AuthUserId:
        return AuthUserId(UUID(raw))


@dataclass(frozen=True, slots=True)
class EmailAllowList:
    emails: frozenset[Email]

    @staticmethod
    def parse(raw: str) -> EmailAllowList:
        emails = frozenset(Email.parse(piece) for piece in raw.split(",") if piece.strip())
        return EmailAllowList(emails)


@dataclass(frozen=True, slots=True)
class VerifiedIdentity:
    id: AuthUserId
    email: Email


@dataclass(frozen=True, slots=True)
class AppUser:
    id: AuthUserId
    email: Email


@dataclass(frozen=True, slots=True)
class AccessRequest:
    email: Email
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ThreadGrant:
    viewer_id: AuthUserId
    owner_id: AuthUserId

    def __post_init__(self) -> None:
        if self.viewer_id != self.owner_id:
            raise NotThreadOwner


class AuthError(Exception):
    code: str


class Unauthenticated(AuthError):
    code = "unauthorized"


class NotAllowed(AuthError):
    code = "not_allowed"


class NotThreadOwner(AuthError):
    code = "not_owner"


class MissingThread(AuthError):
    code = "not_found"


class AuthBackendDown(AuthError):
    code = "auth_unavailable"
