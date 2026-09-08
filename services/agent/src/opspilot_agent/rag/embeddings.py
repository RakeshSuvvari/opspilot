from __future__ import annotations

from openai import AsyncOpenAI, OpenAI


class EmbeddingClient:
    def __init__(self, api_key: str, model: str, dimensions: int):
        self.model = model
        self.dimensions = dimensions
        self._sync = OpenAI(api_key=api_key)
        self._async = AsyncOpenAI(api_key=api_key)

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self._sync.embeddings.create(
            model=self.model,
            input=texts,
            dimensions=self.dimensions,
        )
        ordered = sorted(response.data, key=lambda item: item.index)
        return [item.embedding for item in ordered]

    async def embed_query(self, text: str) -> list[float]:
        response = await self._async.embeddings.create(
            model=self.model,
            input=text,
            dimensions=self.dimensions,
        )
        return response.data[0].embedding
