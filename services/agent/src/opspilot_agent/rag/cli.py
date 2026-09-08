from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

from opspilot_agent.config import Settings

from .database import KnowledgeDatabase
from .ingest import ingest_directory
from .retrieval import KnowledgeRetriever


async def _search(args: argparse.Namespace, settings: Settings) -> None:
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
        args.query,
        top_k=args.top_k,
        document_type=args.document_type,
    )
    print(json.dumps([hit.as_dict() for hit in hits], indent=2))


def _ingest(args: argparse.Namespace, settings: Settings) -> None:
    settings.require_openai_key()
    settings.require_database()
    stats = ingest_directory(
        root=Path(args.root),
        database_url=settings.database_url,
        openai_api_key=settings.openai_api_key,
        embedding_model=settings.embedding_model,
        embedding_dimensions=settings.embedding_dimensions,
        max_chars=settings.rag_chunk_chars,
        overlap_chars=settings.rag_chunk_overlap_chars,
    )
    print(
        f"scanned={stats.scanned} indexed={stats.indexed} "
        f"skipped={stats.skipped} chunks={stats.chunks}"
    )


def _stats(settings: Settings) -> None:
    settings.require_database()
    rows = KnowledgeDatabase(settings.database_url).stats()
    print(json.dumps(rows, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="OpsPilot knowledge/RAG utilities")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest")
    ingest.add_argument("--root", default="knowledge")

    search = sub.add_parser("search")
    search.add_argument("--query", required=True)
    search.add_argument("--top-k", type=int, default=None)
    search.add_argument("--document-type", default=None)

    sub.add_parser("stats")
    args = parser.parse_args()

    try:
        settings = Settings.from_env()
        if args.command == "ingest":
            _ingest(args, settings)
        elif args.command == "search":
            asyncio.run(_search(args, settings))
        else:
            _stats(settings)
    except Exception as exc:
        print(f"opspilot-rag: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
