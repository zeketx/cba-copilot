
from __future__ import annotations

import hashlib
import math
from typing import Protocol

from app.config import Settings
from app.retrieval.text import tokens


class Embedder(Protocol):
    def embed_query(self, text: str) -> list[float]: ...

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

class OpenAIEmbedder:

    def __init__(self, settings: Settings) -> None:
        self._model = settings.openai_embedding_model
        self._dimensions = settings.openai_embedding_dimensions

    def embed_query(self, text: str) -> list[float]:
        raise RuntimeError(
            f"OpenAI embeddings ({self._model}, {self._dimensions} dimensions) "
            "are disabled in this skeleton."
        )
