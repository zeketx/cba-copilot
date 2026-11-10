from __future__ import annotations

import hashlib
import math
from typing import Protocol

import httpx

from app.config import Settings
from app.retrieval.text import tokens


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
