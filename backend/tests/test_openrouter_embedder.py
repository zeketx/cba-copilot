import json

import httpx
import pytest
from app.config import Settings
from app.retrieval.embed import OpenRouterEmbedder


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
