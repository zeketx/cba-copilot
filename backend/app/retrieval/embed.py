from __future__ import annotations

import hashlib
import math
from typing import Protocol

import httpx

from app.config import Settings
from app.retrieval.text import tokens

OPENROUTER_EMBEDDINGS_URL = "https://openrouter.ai/api/v1/embeddings"
_EMBED_BATCH = 16


class Embedder(Protocol):
    def embed_query(self, text: str) -> list[float]: ...


class DocumentEmbedder(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbedder:
    def __init__(self, dimensions: int = 1536) -> None:
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


class OpenRouterEmbedder:
    def __init__(self, settings: Settings, *, client: httpx.Client | None = None) -> None:
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
        self.prompt_tokens = 0
        self.total_tokens = 0
        self._client = client or httpx.Client(timeout=120.0)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for start in range(0, len(texts), _EMBED_BATCH):
            vectors.extend(self._embed_batch(texts[start : start + _EMBED_BATCH]))
        return vectors

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        try:
            response = self._client.post(
                OPENROUTER_EMBEDDINGS_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": self.model, "input": texts, "encoding_format": "float"},
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
