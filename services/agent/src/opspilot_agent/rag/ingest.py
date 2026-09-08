from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from pgvector import Vector

from psycopg.types.json import Jsonb

from .chunking import MarkdownChunk, chunk_markdown, extract_title, parse_front_matter
from .database import KnowledgeDatabase
from .embeddings import EmbeddingClient


DOCUMENT_TYPES = {
    "runbooks": "runbook",
    "postmortems": "postmortem",
    "architecture": "architecture",
    "incidents": "incident",
}


@dataclass(frozen=True)
class IngestStats:
    scanned: int = 0
    indexed: int = 0
    skipped: int = 0
    chunks: int = 0


def _document_type(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    if len(relative.parts) > 1:
        return DOCUMENT_TYPES.get(relative.parts[0], "other")
    return "other"


def _embed_chunks(
    embedder: EmbeddingClient,
    chunks: list[MarkdownChunk],
    batch_size: int = 64,
) -> list[list[float]]:
    embeddings: list[list[float]] = []
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        texts = [
            f"{chunk.heading}\n\n{chunk.content}" if chunk.heading else chunk.content
            for chunk in batch
        ]
        embeddings.extend(embedder.embed_many(texts))
    return embeddings


def ingest_directory(
    *,
    root: Path,
    database_url: str,
    openai_api_key: str,
    embedding_model: str,
    embedding_dimensions: int,
    max_chars: int,
    overlap_chars: int,
) -> IngestStats:
    if not root.exists():
        raise FileNotFoundError(f"Knowledge directory does not exist: {root}")

    database = KnowledgeDatabase(database_url)
    embedder = EmbeddingClient(openai_api_key, embedding_model, embedding_dimensions)
    files = sorted(root.rglob("*.md"))

    indexed = 0
    skipped = 0
    chunk_count = 0

    with database.connect() as conn:
        for path in files:
            text = path.read_text(encoding="utf-8")
            digest = sha256(text.encode("utf-8")).hexdigest()
            source_path = path.relative_to(root.parent).as_posix()
            metadata, body = parse_front_matter(text)
            title = metadata.get("title") or extract_title(
                body, path.stem.replace("-", " ").title()
            )
            doc_type = metadata.get("document_type") or _document_type(path, root)
            if doc_type not in {"runbook", "postmortem", "architecture", "incident", "other"}:
                raise ValueError(f"Unsupported document_type {doc_type!r} in {source_path}")
            service = metadata.get("service")

            existing = conn.execute(
                """
                SELECT id, content_sha256, embedding_model, embedding_dimensions
                FROM knowledge.documents
                WHERE source_path = %s
                """,
                (source_path,),
            ).fetchone()

            if (
                existing
                and existing[1] == digest
                and existing[2] == embedding_model
                and existing[3] == embedding_dimensions
            ):
                skipped += 1
                continue

            chunks = chunk_markdown(
                body,
                max_chars=max_chars,
                overlap_chars=overlap_chars,
            )
            embeddings = _embed_chunks(embedder, chunks)

            row = conn.execute(
                """
                INSERT INTO knowledge.documents (
                    source_path,
                    title,
                    document_type,
                    service,
                    content_sha256,
                    embedding_model,
                    embedding_dimensions,
                    metadata,
                    updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (source_path) DO UPDATE SET
                    title = EXCLUDED.title,
                    document_type = EXCLUDED.document_type,
                    service = EXCLUDED.service,
                    content_sha256 = EXCLUDED.content_sha256,
                    embedding_model = EXCLUDED.embedding_model,
                    embedding_dimensions = EXCLUDED.embedding_dimensions,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
                RETURNING id
                """,
                (
                    source_path,
                    title,
                    doc_type,
                    service,
                    digest,
                    embedding_model,
                    embedding_dimensions,
                    Jsonb(metadata),
                ),
            ).fetchone()
            document_id = row[0]

            conn.execute(
                "DELETE FROM knowledge.chunks WHERE document_id = %s",
                (document_id,),
            )
            conn.executemany(
                """
                INSERT INTO knowledge.chunks (
                    document_id,
                    chunk_index,
                    heading,
                    content,
                    embedding
                ) VALUES (%s, %s, %s, %s, %s)
                """,
                [
                    (
                        document_id,
                        chunk.index,
                        chunk.heading,
                        chunk.content,
                        Vector(embedding),
                    )
                    for chunk, embedding in zip(chunks, embeddings, strict=True)
                ],
            )
            conn.commit()
            indexed += 1
            chunk_count += len(chunks)

    return IngestStats(
        scanned=len(files),
        indexed=indexed,
        skipped=skipped,
        chunks=chunk_count,
    )
