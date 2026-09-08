from __future__ import annotations

from collections.abc import Sequence

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector, register_vector_async

from .models import KnowledgeHit


class KnowledgeDatabase:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def connect(self) -> psycopg.Connection:
        conn = psycopg.connect(self.database_url)
        register_vector(conn)
        return conn

    async def search(
        self,
        embedding: Sequence[float],
        *,
        top_k: int,
        min_similarity: float,
        document_type: str | None = None,
        service: str | None = None,
    ) -> list[KnowledgeHit]:
        conn = await psycopg.AsyncConnection.connect(self.database_url)
        try:
            await register_vector_async(conn)
            filters = ["TRUE"]
            params: list[object] = []

            if document_type:
                filters.append("d.document_type = %s")
                params.append(document_type)
            if service:
                filters.append("d.service = %s")
                params.append(service)

            vector = Vector(embedding)
            sql = f"""
                SELECT
                    d.title,
                    d.source_path,
                    d.document_type,
                    d.service,
                    c.chunk_index,
                    c.heading,
                    c.content,
                    1 - (c.embedding <=> %s) AS similarity
                FROM knowledge.chunks c
                JOIN knowledge.documents d ON d.id = c.document_id
                WHERE {' AND '.join(filters)}
                ORDER BY c.embedding <=> %s
                LIMIT %s
            """
            query_params = [vector, *params, vector, max(top_k * 2, top_k)]
            rows = await (await conn.execute(sql, query_params)).fetchall()
        finally:
            await conn.close()

        hits = [
            KnowledgeHit(
                title=row[0],
                source_path=row[1],
                document_type=row[2],
                service=row[3],
                chunk_index=row[4],
                heading=row[5],
                content=row[6],
                similarity=float(row[7]),
            )
            for row in rows
            if float(row[7]) >= min_similarity
        ]
        return hits[:top_k]

    def stats(self) -> list[dict[str, object]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT document_type, COUNT(*) AS documents, COALESCE(SUM(chunk_count), 0)
                FROM knowledge.document_stats
                GROUP BY document_type
                ORDER BY document_type
                """
            ).fetchall()
        return [
            {
                "document_type": row[0],
                "documents": int(row[1]),
                "chunks": int(row[2]),
            }
            for row in rows
        ]
