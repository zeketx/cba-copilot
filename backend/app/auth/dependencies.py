from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException, Request

from app.auth.gate import (
    AccessGate,
    GoTrueVerifier,
    Ledger,
    MemoryLedger,
    RejectVerifier,
    SqlLedger,
    Verifier,
)
from app.auth.identity import AppUser, AuthError, EmailAllowList
from app.config import Settings

_STATUS: dict[str, int] = {
    "unauthorized": 401,
    "not_allowed": 403,
    "not_owner": 403,
    "auth_unavailable": 503,
}


def http_error(exc: AuthError) -> HTTPException:
    return HTTPException(status_code=_STATUS[exc.code], detail={"error": exc.code})


def get_current_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> AppUser:
    try:
        return request.app.state.gate.admit(authorization)
    except AuthError as exc:
        raise http_error(exc) from None


def gate_from_settings(settings: Settings) -> AccessGate:
    allow = EmailAllowList.parse(",".join(settings.allowed_emails))
    verifier: Verifier
    if settings.supabase_url and settings.supabase_anon_key:
        verifier = GoTrueVerifier(url=settings.supabase_url, anon_key=settings.supabase_anon_key)
    else:
        verifier = RejectVerifier()
    ledger: Ledger
    if settings.database_url:
        ledger = SqlLedger(settings.sqlalchemy_database_url)
    else:
        ledger = MemoryLedger()
    return AccessGate(allow=allow, verifier=verifier, ledger=ledger)
