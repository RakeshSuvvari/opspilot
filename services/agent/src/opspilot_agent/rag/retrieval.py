from __future__ import annotations

from .database import KnowledgeDatabase
from .embeddings import EmbeddingClient
from .models import KnowledgeHit


class KnowledgeRetriever:
    def __init__(
        self,
        *,
        database_url: str,
        openai_api_key: str,
        embedding_model: str,
        embedding_dimensions: int,
        top_k: int,
        min_similarity: float,
    ):
        self.database = KnowledgeDatabase(database_url)
        self.embedder = EmbeddingClient(
            openai_api_key,
            embedding_model,
            embedding_dimensions,
        )
        self.top_k = top_k
        self.min_similarity = min_similarity

    async def search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        document_type: str | None = None,
        service: str | None = None,
    ) -> list[KnowledgeHit]:
        normalized = query.strip()
        if not normalized:
            raise ValueError("knowledge search query cannot be empty")

        limit = min(max(top_k or self.top_k, 1), 10)
        embedding = await self.embedder.embed_query(normalized)
        return await self.database.search(
            embedding,
            top_k=limit,
            min_similarity=self.min_similarity,
            document_type=document_type,
            service=service,
        )
