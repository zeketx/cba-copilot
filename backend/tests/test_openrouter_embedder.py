import json

import httpx
import pytest
from app.config import Settings
from app.retrieval.embed import (
    OPENROUTER_LIMITS,
    OPENROUTER_TIMEOUT,
    OpenRouterEmbedder,
    QueryEmbeddingCache,
    build_embedder,
    normalize_query_text,
    openrouter_http_client,
    voyage_input_type,
)


def _settings(**kwargs: object) -> Settings:
    base = {
        "embedding_provider": "openrouter",
        "embedding_model": "qwen/qwen3-embedding-8b",
        "openrouter_api_key": "test-key",
        "embedding_dimensions": None,
    }
    base.update(kwargs)
    return Settings(**base)


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_embed_documents_preserve_index_order_and_sum_usage() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        body = json.loads(request.content)
        assert body["model"] == "qwen/qwen3-embedding-8b"
        assert "input_type" not in body
        assert request.headers["authorization"] == "Bearer test-key"
        data = [
            {"index": index, "embedding": [float(index), 1.0]}
            for index in range(len(body["input"]) - 1, -1, -1)
        ]
        return httpx.Response(
            200,
            json={"data": data, "usage": {"prompt_tokens": 3, "total_tokens": 3}},
        )

    embedder = OpenRouterEmbedder(_settings(), client=_client(handler))
    texts = [f"chunk-{index}" for index in range(17)]
    vectors = embedder.embed_documents(texts)
    assert calls["count"] == 2
    assert len(vectors) == 17
    assert vectors[0] == [0.0, 1.0]
    assert vectors[16] == [0.0, 1.0]
    assert embedder.prompt_tokens == 6
    assert embedder.dimensions == 2
    assert embedder.embed_query("one") == [0.0, 1.0]
    assert embedder.prompt_tokens == 9


def test_empty_batch_does_not_call_the_network() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(request.url)

    embedder = OpenRouterEmbedder(_settings(), client=_client(handler))
    assert embedder.embed_documents([]) == []


def test_dimension_mismatch_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [{"index": 0, "embedding": [1.0, 2.0, 3.0]}],
                "usage": {"prompt_tokens": 1},
            },
        )

    embedder = OpenRouterEmbedder(_settings(embedding_dimensions=2), client=_client(handler))
    with pytest.raises(RuntimeError, match="3 dimensions"):
        embedder.embed_query("apron")


def test_http_error_hides_the_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized test-key")

    embedder = OpenRouterEmbedder(_settings(), client=_client(handler))
    with pytest.raises(RuntimeError, match="HTTP 401") as caught:
        embedder.embed_query("apron")
    assert "test-key" not in str(caught.value)
    assert "[redacted]" in str(caught.value)


def test_missing_key_raises_before_a_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(request.url)

    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        OpenRouterEmbedder(_settings(openrouter_api_key=""), client=_client(handler))


def test_provider_must_be_openrouter() -> None:
    with pytest.raises(RuntimeError, match="EMBEDDING_PROVIDER"):
        OpenRouterEmbedder(_settings(embedding_provider="openai"))


def test_voyage_sends_document_and_query_input_types() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body["input_type"])
        return httpx.Response(
            200,
            json={
                "data": [{"index": 0, "embedding": [1.0, 2.0]}],
                "usage": {"prompt_tokens": 1, "total_tokens": 1},
            },
        )

    embedder = OpenRouterEmbedder(
        _settings(embedding_model="mongodb/voyage-4-lite", embedding_dimensions=2),
        client=_client(handler),
    )
    assert embedder.embed_documents(["section"]) == [[1.0, 2.0]]
    assert embedder.embed_query("apron") == [1.0, 2.0]
    assert seen == ["document", "query"]
    embedder.close()


def test_voyage_input_type_matches_the_model_name() -> None:
    assert voyage_input_type("mongodb/voyage-4-lite", "query") == "query"
    assert voyage_input_type("mongodb/voyage-4", "document") == "document"
    assert voyage_input_type("qwen/qwen3-embedding-8b", "query") is None


def test_build_embedder_uses_voyage_lite_without_a_request() -> None:
    embedder = build_embedder(
        Settings(
            openrouter_api_key="test-key",
            _env_file=None,
        )
    )
    assert isinstance(embedder, OpenRouterEmbedder)
    assert embedder.model == "mongodb/voyage-4-lite"
    assert embedder.dimensions == 1024
    embedder.close()


def _vector_handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    return httpx.Response(
        200,
        json={
            "data": [
                {"index": index, "embedding": [float(index + 1), 2.0]}
                for index in range(len(body["input"]))
            ],
            "usage": {"prompt_tokens": 1, "total_tokens": 1},
        },
    )


def test_owned_client_uses_keep_alive_http2_and_timeouts() -> None:
    client = openrouter_http_client()
    try:
        assert client.timeout.connect == OPENROUTER_TIMEOUT.connect == 5.0
        assert client.timeout.read == OPENROUTER_TIMEOUT.read == 30.0
        assert client.timeout.write == 10.0
        pool = client._transport._pool
        assert pool._http2 is True
        assert pool._keepalive_expiry == OPENROUTER_LIMITS.keepalive_expiry == 60.0
        assert pool._max_keepalive_connections == 8
        assert pool._max_connections == 16
    finally:
        client.close()
    embedder = OpenRouterEmbedder(_settings())
    try:
        assert embedder._client.timeout.connect == 5.0
        assert embedder._client._transport._pool._http2 is True
    finally:
        embedder.close()


def test_query_cache_skips_a_second_identical_query() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        assert request.method == "POST"
        return _vector_handler(request)

    embedder = OpenRouterEmbedder(
        _settings(embedding_dimensions=2),
        client=_client(handler),
    )
    first = embedder.embed_query("  Bird   rights ")
    assert embedder.last_query_cached is False
    assert calls["count"] == 1
    assert embedder.prompt_tokens == 1
    second = embedder.embed_query("Bird rights")
    assert embedder.last_query_cached is True
    assert second == first
    assert calls["count"] == 1
    assert embedder.prompt_tokens == 1
    first[0] = 99.0
    assert embedder.embed_query("Bird rights")[0] == pytest.approx(1.0)


def test_query_cache_key_includes_model_and_dimensions() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return _vector_handler(request)

    shared = QueryEmbeddingCache(max_entries=8, ttl_seconds=60)
    transport = _client(handler)
    first = OpenRouterEmbedder(
        _settings(embedding_model="qwen/qwen3-embedding-8b", embedding_dimensions=2),
        client=transport,
        cache=shared,
    )
    second = OpenRouterEmbedder(
        _settings(embedding_model="mongodb/voyage-4-lite", embedding_dimensions=2),
        client=transport,
        cache=shared,
    )
    third = OpenRouterEmbedder(
        _settings(embedding_model="qwen/qwen3-embedding-8b", embedding_dimensions=4),
        client=_client(
            lambda request: httpx.Response(
                200,
                json={
                    "data": [{"index": 0, "embedding": [1.0, 2.0, 3.0, 4.0]}],
                    "usage": {"prompt_tokens": 1, "total_tokens": 1},
                },
            )
        ),
        cache=shared,
    )
    first.embed_query("apron")
    second.embed_query("apron")
    third.embed_query("apron")
    assert calls["count"] == 2
    assert third.prompt_tokens == 1
    assert normalize_query_text("  apron\n") == "apron"


def test_document_embed_is_not_served_from_the_query_cache() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return _vector_handler(request)

    embedder = OpenRouterEmbedder(
        _settings(embedding_dimensions=2),
        client=_client(handler),
    )
    embedder.embed_documents(["apron"])
    embedder.embed_query("apron")
    assert calls["count"] == 2
    assert embedder.last_query_cached is False


def test_query_cache_evicts_oldest_and_expired_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = {"now": 100.0}
    monkeypatch.setattr("app.retrieval.embed.time.monotonic", lambda: clock["now"])
    cache = QueryEmbeddingCache(max_entries=2, ttl_seconds=10)
    cache.put(("a", "m", 2), [1.0])
    cache.put(("b", "m", 2), [2.0])
    cache.put(("c", "m", 2), [3.0])
    assert cache.get(("a", "m", 2)) is None
    assert cache.get(("b", "m", 2)) == [2.0]
    clock["now"] = 111.0
    assert cache.get(("b", "m", 2)) is None
    assert cache.get(("c", "m", 2)) is None


def test_warmup_gets_the_embeddings_url_and_does_not_post() -> None:
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        assert str(request.url) == "https://openrouter.ai/api/v1/embeddings"
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(405, text="method not allowed")

    embedder = OpenRouterEmbedder(_settings(), client=_client(handler))
    embedder.warmup()
    assert methods == ["GET"]


def test_warmup_network_error_is_swallowed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    embedder = OpenRouterEmbedder(_settings(), client=_client(handler))
    embedder.warmup()


def test_live_app_warms_and_closes_the_embedder(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api import create_app
    from app.auth.gate import AccessGate, MemoryLedger
    from app.auth.identity import (
        AuthUserId,
        Email,
        EmailAllowList,
        Unauthenticated,
        VerifiedIdentity,
    )
    from app.chat.log import MemoryChatLog
    from fastapi.testclient import TestClient

    events: list[str] = []

    class FakeEmbedder:
        def warmup(self) -> None:
            events.append("warmup")

        def close(self) -> None:
            events.append("close")

    monkeypatch.setattr("app.api.build_embedder", lambda _settings: FakeEmbedder())
    monkeypatch.setattr("app.api.build_live_drafter", lambda _settings: object())
    identity = VerifiedIdentity(
        id=AuthUserId.parse("11111111-1111-1111-1111-111111111111"),
        email=Email.parse("fan@example.com"),
    )

    class Verifier:
        def verify(self, token: str) -> VerifiedIdentity:
            del token
            raise Unauthenticated

    log = MemoryChatLog()
    gate = AccessGate(
        allow=EmailAllowList.parse(identity.email.value),
        verifier=Verifier(),
        ledger=MemoryLedger(),
        threads=log,
    )
    settings = Settings(
        database_url="postgresql://postgres:pw@localhost:5432/postgres",
        supabase_url="https://example.supabase.co",
        openai_api_key="sk-test",
        openrouter_api_key="test-key",
        _env_file=None,
    )

    def session_factory() -> None:
        raise AssertionError("database")

    with TestClient(
        create_app(settings, gate=gate, log=log, session_factory=session_factory)
    ) as client:
        assert events == ["warmup"]
        assert client.get("/api/health").json() == {"ok": "true", "mode": "live"}
    assert events == ["warmup", "close"]
