from __future__ import annotations

import hashlib
import math
import threading
import time
from collections import OrderedDict
from typing import Literal, Protocol

import httpx

from app.config import Settings
from app.database.constants import EMBEDDING_DIMENSIONS
from app.retrieval.text import tokens

OPENROUTER_EMBEDDINGS_URL = "https://openrouter.ai/api/v1/embeddings"
_EMBED_BATCH = 16
QUERY_CACHE_MAX = 256
QUERY_CACHE_TTL_SECONDS = 1_800.0
OPENROUTER_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
OPENROUTER_LIMITS = httpx.Limits(
    max_keepalive_connections=8,
    max_connections=16,
    keepalive_expiry=60.0,
)


class Embedder(Protocol):
    def embed_query(self, text: str) -> list[float]: ...


class DocumentEmbedder(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbedder:
    def __init__(self, dimensions: int = EMBEDDING_DIMENSIONS) -> None:
        if dimensions < 8:
            raise ValueError("dimensions must be at least 8")
        self.dimensions = dimensions

    def embed_query(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in tokens(text):
            digest = hashlib.sha256(token.encode()).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]


class OpenAIEmbedder:

    def __init__(self, settings: Settings) -> None:
        self._model = settings.openai_embedding_model
        self._dimensions = settings.openai_embedding_dimensions
        self._api_key = settings.openai_api_key

    def embed_query(self, text: str) -> list[float]:
        raise RuntimeError(
            f"OpenAI embeddings ({self._model}, {self._dimensions} dimensions) "
            "are disabled in this skeleton."
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY is required to embed documents")
        response = httpx.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._model,
                "input": texts,
                "dimensions": self._dimensions,
            },
            timeout=60.0,
        )
        response.raise_for_status()
        by_index = {item["index"]: item["embedding"] for item in response.json()["data"]}
        vectors = [by_index[index] for index in range(len(texts))]
        for vector in vectors:
            if len(vector) != self._dimensions:
                raise RuntimeError(
                    f"embedding length {len(vector)} does not match {self._dimensions}"
                )
        return vectors


class QueryEmbeddingCache:
    def __init__(
        self,
        *,
        max_entries: int = QUERY_CACHE_MAX,
        ttl_seconds: float = QUERY_CACHE_TTL_SECONDS,
    ) -> None:
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self._entries: OrderedDict[tuple[str, str, int | str], tuple[tuple[float, ...], float]] = (
            OrderedDict()
        )
        self._lock = threading.Lock()

    def get(self, key: tuple[str, str, int | str]) -> list[float] | None:
        if self._max_entries <= 0:
            return None
        now = time.monotonic()
        with self._lock:
            item = self._entries.get(key)
            if item is None:
                return None
            vector, expires_at = item
            if expires_at <= now:
                del self._entries[key]
                return None
            self._entries.move_to_end(key)
            return list(vector)

    def put(self, key: tuple[str, str, int | str], vector: list[float]) -> None:
        if self._max_entries <= 0:
            return
        expires_at = time.monotonic() + self._ttl_seconds
        stored = tuple(vector)
        with self._lock:
            self._entries[key] = (stored, expires_at)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)


def normalize_query_text(text: str) -> str:
    return " ".join(text.split())


def openrouter_http_client(*, http2: bool = True) -> httpx.Client:
    if http2:
        try:
            return httpx.Client(
                timeout=OPENROUTER_TIMEOUT,
                limits=OPENROUTER_LIMITS,
                http2=True,
            )
        except ImportError:
            pass
    return httpx.Client(
        timeout=OPENROUTER_TIMEOUT,
        limits=OPENROUTER_LIMITS,
        http2=False,
    )


class OpenRouterEmbedder:
    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
        cache: QueryEmbeddingCache | None = None,
        cache_max_entries: int = QUERY_CACHE_MAX,
        cache_ttl_seconds: float = QUERY_CACHE_TTL_SECONDS,
    ) -> None:
        if settings.resolved_embedding_provider != "openrouter":
            raise RuntimeError("OpenRouterEmbedder requires EMBEDDING_PROVIDER=openrouter.")
        if not settings.embedding_model.strip():
            raise RuntimeError("EMBEDDING_MODEL is required when EMBEDDING_PROVIDER is openrouter.")
        key = settings.openrouter_api_key.strip()
        if not key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is required to embed with OpenRouter. "
                "Set it in the environment or backend/.env. No request was sent."
            )
        self.model = settings.embedding_model.strip()
        self._api_key = key
        self._expected_dimensions = settings.embedding_dimensions
        self.dimensions = settings.embedding_dimensions
        self._cache_dims: int | str = (
            settings.embedding_dimensions
            if settings.embedding_dimensions is not None
            else "unset"
        )
        self.prompt_tokens = 0
        self.total_tokens = 0
        self.last_query_cached = False
        self._client = client or openrouter_http_client()
        self._owns_client = client is None
        self._cache = cache if cache is not None else QueryEmbeddingCache(
            max_entries=cache_max_entries,
            ttl_seconds=cache_ttl_seconds,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def warmup(self) -> None:
        try:
            self._client.get(OPENROUTER_EMBEDDINGS_URL, headers=self._headers())
        except httpx.HTTPError:
            return

    def embed_query(self, text: str) -> list[float]:
        key = (normalize_query_text(text), self.model, self._cache_dims)
        cached = self._cache.get(key)
        if cached is not None:
            self.last_query_cached = True
            return cached
        self.last_query_cached = False
        vector = self._embed([text], role="query")[0]
        self._cache.put(key, vector)
        return vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, role="document")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _embed(self, texts: list[str], *, role: Literal["query", "document"]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for start in range(0, len(texts), _EMBED_BATCH):
            vectors.extend(self._embed_batch(texts[start : start + _EMBED_BATCH], role=role))
        return vectors

    def _embed_batch(
        self,
        texts: list[str],
        *,
        role: Literal["query", "document"],
    ) -> list[list[float]]:
        body: dict[str, object] = {
            "model": self.model,
            "input": texts,
            "encoding_format": "float",
        }
        input_type = voyage_input_type(self.model, role)
        if input_type is not None:
            body["input_type"] = input_type
        try:
            response = self._client.post(
                OPENROUTER_EMBEDDINGS_URL,
                headers=self._headers(),
                json=body,
            )
        except httpx.HTTPError as exc:
            raise RuntimeError(f"OpenRouter embeddings request failed for {self.model}.") from exc
        if response.status_code != 200:
            detail = response.text[:300].replace(self._api_key, "[redacted]").replace("\n", " ")
            raise RuntimeError(
                f"OpenRouter embeddings failed for {self.model} "
                f"with HTTP {response.status_code}. {detail}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"OpenRouter embeddings response for {self.model} was not JSON."
            ) from exc
        vectors, prompt_tokens, total_tokens = parse_embedding_payload(
            payload,
            expected_count=len(texts),
            expected_dimensions=self._expected_dimensions,
        )
        self.prompt_tokens += prompt_tokens
        self.total_tokens += total_tokens
        if self._expected_dimensions is None and vectors:
            self._expected_dimensions = len(vectors[0])
            self.dimensions = self._expected_dimensions
        return vectors


def voyage_input_type(model: str, role: Literal["query", "document"]) -> str | None:
    name = model.rsplit("/", 1)[-1]
    if name.startswith("voyage-"):
        return role
    return None


def build_embedder(settings: Settings) -> HashEmbedder | OpenAIEmbedder | OpenRouterEmbedder:
    provider = settings.resolved_embedding_provider
    if provider == "hash":
        return HashEmbedder(settings.resolved_embedding_dimensions)
    if provider == "openrouter":
        return OpenRouterEmbedder(settings)
    if provider == "openai":
        return OpenAIEmbedder(settings)
    raise RuntimeError("EMBEDDING_PROVIDER must be hash, openai, or openrouter")


def parse_embedding_payload(
    payload: object,
    *,
    expected_count: int,
    expected_dimensions: int | None,
) -> tuple[list[list[float]], int, int]:
    if not isinstance(payload, dict):
        raise RuntimeError("OpenRouter embeddings response did not include vectors.")
    data = payload.get("data")
    if not isinstance(data, list) or len(data) != expected_count:
        raise RuntimeError("OpenRouter embeddings response did not include vectors.")
    if data and all(isinstance(item, dict) and "index" in item for item in data):
        data = sorted(data, key=lambda item: int(item["index"]))
    vectors: list[list[float]] = []
    locked = expected_dimensions
    for item in data:
        if not isinstance(item, dict):
            raise RuntimeError("OpenRouter embeddings response did not include vectors.")
        raw = item.get("embedding")
        if not isinstance(raw, list) or not raw:
            raise RuntimeError("OpenRouter embeddings response included an empty vector.")
        vector = [float(value) for value in raw]
        if locked is None:
            locked = len(vector)
        elif len(vector) != locked:
            raise RuntimeError(
                f"OpenRouter returned {len(vector)} dimensions, expected {locked}."
            )
        vectors.append(vector)
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or prompt_tokens)
    return vectors, prompt_tokens, total_tokens
