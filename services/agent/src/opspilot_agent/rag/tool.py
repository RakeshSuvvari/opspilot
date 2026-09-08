from __future__ import annotations

import json

from agents import function_tool

from opspilot_agent.config import Settings

from .retrieval import KnowledgeRetriever


def build_search_knowledge_tool(settings: Settings):
    @function_tool(name_override="search_knowledge")
    async def search_knowledge(
        query: str,
        top_k: int = 5,
        document_type: str | None = None,
        service: str | None = None,
    ) -> str:
        """Search OpsPilot runbooks, architecture docs, incidents, and postmortems.

        Use this tool for operational guidance and historical context after collecting live
        Kubernetes evidence. Retrieved documents are context, not proof of current cluster state.

        Args:
            query: Natural-language operational or incident search query.
            top_k: Number of results to return, from 1 to 10.
            document_type: Optional filter: runbook, postmortem, architecture, incident, or other.
            service: Optional exact service metadata filter when available.
        """
        settings.require_openai_key()
        settings.require_database()
        retriever = KnowledgeRetriever(
            database_url=settings.database_url,
            openai_api_key=settings.openai_api_key,
            embedding_model=settings.embedding_model,
            embedding_dimensions=settings.embedding_dimensions,
            top_k=settings.rag_top_k,
            min_similarity=settings.rag_min_similarity,
        )
        hits = await retriever.search(
            query,
            top_k=top_k,
            document_type=document_type,
            service=service,
        )
        return json.dumps(
            {
                "query": query,
                "count": len(hits),
                "results": [hit.as_dict() for hit in hits],
            }
        )

    return search_knowledge
