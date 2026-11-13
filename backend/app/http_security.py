from __future__ import annotations

import re
from urllib.parse import urlsplit

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_HOST = re.compile(r"\A(?:[A-Za-z0-9.-]+|\[[0-9A-Fa-f:.]+\])(?::[0-9]{1,5})?\Z")
_HSTS = "max-age=31536000; includeSubDomains"
_REFERRER = "strict-origin-when-cross-origin"


def http_origin(value: str) -> str | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    parts = urlsplit(cleaned)
    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"} or parts.hostname is None:
        return None
    host = parts.hostname
    if ":" in host:
        host = f"[{host}]"
    port = parts.port
    default_port = (scheme == "https" and port == 443) or (scheme == "http" and port == 80)
    if port is None or default_port:
        return f"{scheme}://{host}"
    return f"{scheme}://{host}:{port}"


def content_security_policy(
    *,
    supabase_origin: str | None,
    api_origin: str | None,
    pdf_origin: str | None,
) -> str:
    connect = _sources("'self'", supabase_origin, api_origin)
    frames = _sources(pdf_origin)
    return "; ".join(
        (
            "default-src 'none'",
            f"connect-src {connect}",
            f"frame-src {frames}",
            "frame-ancestors 'none'",
            "base-uri 'none'",
            "form-action 'none'",
            "object-src 'none'",
        )
    )


def security_headers(
    *,
    supabase_origin: str | None,
    api_origin: str | None,
    pdf_origin: str | None,
) -> list[tuple[bytes, bytes]]:
    policy = content_security_policy(
        supabase_origin=supabase_origin,
        api_origin=api_origin,
        pdf_origin=pdf_origin,
    )
    pairs = (
        ("content-security-policy", policy),
        ("x-frame-options", "DENY"),
        ("x-content-type-options", "nosniff"),
        ("referrer-policy", _REFERRER),
        ("strict-transport-security", _HSTS),
    )
    return [(name.encode("latin-1"), value.encode("latin-1")) for name, value in pairs]


class SecurityHeadersMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        supabase_origin: str | None,
        pdf_origin: str | None,
    ) -> None:
        self.app = app
        self.supabase_origin = supabase_origin
        self.pdf_origin = pdf_origin

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        extra = security_headers(
            supabase_origin=self.supabase_origin,
            api_origin=_api_origin(scope),
            pdf_origin=self.pdf_origin,
        )

        async def send_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(extra)
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_headers)


def _sources(*items: str | None) -> str:
    seen: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.append(item)
    if not seen:
        return "'none'"
    return " ".join(seen)


def _api_origin(scope: Scope) -> str | None:
    scheme = scope.get("scheme")
    if scheme not in {"http", "https"}:
        return None
    host = _header(scope, b"host")
    if host is None or _HOST.fullmatch(host) is None:
        return None
    return http_origin(f"{scheme}://{host}")


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key == name:
            decoded = value.decode("latin-1").strip()
            return decoded or None
    return None
