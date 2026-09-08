from __future__ import annotations

import argparse
from pathlib import Path
import sys

import psycopg
from psycopg import sql

from opspilot_agent.config import Settings


def create_database(settings: Settings) -> None:
    if not settings.postgres_admin_url:
        raise ValueError("OPSPILOT_POSTGRES_ADMIN_URL is required for db-create")

    with psycopg.connect(settings.postgres_admin_url, autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (settings.database_name,),
        ).fetchone()
        if exists:
            print(f"Database '{settings.database_name}' already exists.")
            return
        conn.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(settings.database_name))
        )
        print(f"Created database '{settings.database_name}'.")


def apply_schema(settings: Settings, schema_path: Path) -> None:
    if not schema_path.exists():
        raise FileNotFoundError(schema_path)
    script = schema_path.read_text(encoding="utf-8")
    try:
        with psycopg.connect(settings.database_url, autocommit=True) as conn:
            conn.execute(script)
    except psycopg.Error as exc:
        message = str(exc)
        if "extension \"vector\" is not available" in message:
            raise RuntimeError(
                "pgvector is not installed in this PostgreSQL server. Install pgvector, "
                "restart PostgreSQL if required, then rerun make db-init."
            ) from exc
        raise
    print(f"Applied schema from {schema_path}.")


def check_database(settings: Settings) -> None:
    with psycopg.connect(settings.database_url) as conn:
        database = conn.execute("SELECT current_database()").fetchone()[0]
        postgres_version = conn.execute("SHOW server_version").fetchone()[0]
        vector = conn.execute(
            "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
        ).fetchone()
        docs = conn.execute(
            "SELECT COUNT(*) FROM knowledge.documents"
        ).fetchone()[0]
        chunks = conn.execute(
            "SELECT COUNT(*) FROM knowledge.chunks"
        ).fetchone()[0]

    print(f"database: {database}")
    print(f"postgres: {postgres_version}")
    print(f"pgvector: {vector[0] if vector else 'NOT INSTALLED'}")
    print(f"documents: {docs}")
    print(f"chunks: {chunks}")


def main() -> None:
    parser = argparse.ArgumentParser(description="OpsPilot PostgreSQL administration")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("create")
    init = sub.add_parser("init")
    init.add_argument("--schema", default="infra/postgres/01-schema.sql")
    sub.add_parser("check")
    args = parser.parse_args()

    try:
        settings = Settings.from_env()
        if args.command == "create":
            create_database(settings)
        elif args.command == "init":
            apply_schema(settings, Path(args.schema))
        else:
            check_database(settings)
    except Exception as exc:
        print(f"opspilot-db: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
