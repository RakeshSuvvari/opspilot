from __future__ import annotations

import argparse
from pathlib import Path
import sys
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg import sql

from opspilot_agent.config import Settings


def _database_url(base_url: str, database_name: str) -> str:
    """Return base_url with its database path replaced by database_name."""
    parsed = urlsplit(base_url)
    return urlunsplit(
        (parsed.scheme, parsed.netloc, f"/{database_name}", parsed.query, parsed.fragment)
    )


def _runtime_role(settings: Settings) -> str:
    parsed = urlsplit(settings.database_url)
    if not parsed.username:
        raise ValueError("OPSPILOT_DATABASE_URL must include a PostgreSQL username")
    return parsed.username


def _role_exists(conn: psycopg.Connection, role: str) -> bool:
    return (
        conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone()
        is not None
    )


def create_database(settings: Settings) -> None:
    if not settings.postgres_admin_url:
        raise ValueError("OPSPILOT_POSTGRES_ADMIN_URL is required for db-create")

    runtime_role = _runtime_role(settings)
    with psycopg.connect(settings.postgres_admin_url, autocommit=True) as conn:
        if not _role_exists(conn, runtime_role):
            raise RuntimeError(
                f"PostgreSQL role '{runtime_role}' does not exist. Create the runtime role "
                "in PgAdmin (Login/Group Roles) before running db-create."
            )

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
        conn.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(settings.database_name),
                sql.Identifier(runtime_role),
            )
        )
        print(f"Created database '{settings.database_name}'.")


def _grant_runtime_access(
    conn: psycopg.Connection,
    *,
    database_name: str,
    runtime_role: str,
) -> None:
    if not _role_exists(conn, runtime_role):
        raise RuntimeError(
            f"PostgreSQL role '{runtime_role}' does not exist. Create it before db-init."
        )

    conn.execute(
        sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
            sql.Identifier(database_name),
            sql.Identifier(runtime_role),
        )
    )
    for schema_name in ("knowledge", "operations"):
        conn.execute(
            sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                sql.Identifier(schema_name),
                sql.Identifier(runtime_role),
            )
        )
    for schema_name in ("knowledge", "operations"):
        conn.execute(
            sql.SQL(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES "
                "IN SCHEMA {} TO {}"
            ).format(
                sql.Identifier(schema_name),
                sql.Identifier(runtime_role),
            )
        )
        conn.execute(
            sql.SQL(
                "GRANT USAGE, SELECT ON ALL SEQUENCES "
                "IN SCHEMA {} TO {}"
            ).format(
                sql.Identifier(schema_name),
                sql.Identifier(runtime_role),
            )
        )
        conn.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA {} "
                "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}"
            ).format(
                sql.Identifier(schema_name),
                sql.Identifier(runtime_role),
            )
        )
        conn.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA {} "
                "GRANT USAGE, SELECT ON SEQUENCES TO {}"
            ).format(
                sql.Identifier(schema_name),
                sql.Identifier(runtime_role),
            )
        )


def apply_schema(settings: Settings, schema_path: Path) -> None:
    if not settings.postgres_admin_url:
        raise ValueError("OPSPILOT_POSTGRES_ADMIN_URL is required for db-init")
    if not schema_path.exists():
        raise FileNotFoundError(schema_path)

    script = schema_path.read_text(encoding="utf-8")
    admin_database_url = _database_url(
        settings.postgres_admin_url,
        settings.database_name,
    )
    runtime_role = _runtime_role(settings)

    try:
        # DDL and extension installation are intentionally performed with the admin
        # connection. The runtime role only receives the privileges needed for RAG.
        with psycopg.connect(admin_database_url, autocommit=True) as conn:
            conn.execute(script)
            _grant_runtime_access(
                conn,
                database_name=settings.database_name,
                runtime_role=runtime_role,
            )
    except psycopg.Error as exc:
        message = str(exc)
        if 'extension "vector" is not available' in message:
            raise RuntimeError(
                "pgvector is not installed in this PostgreSQL server. Install pgvector, "
                "restart PostgreSQL if required, then rerun make db-init."
            ) from exc
        raise

    print(f"Applied schema from {schema_path} using the admin connection.")
    print(f"Granted OpsPilot runtime access to PostgreSQL role '{runtime_role}'.")


def check_database(settings: Settings) -> None:
    # This check intentionally uses the runtime application role. If it succeeds,
    # OpsPilot ingestion/retrieval has the privileges it needs.
    with psycopg.connect(settings.database_url) as conn:
        database = conn.execute("SELECT current_database()").fetchone()[0]
        current_user = conn.execute("SELECT current_user").fetchone()[0]
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
        investigations = conn.execute(
            "SELECT COUNT(*) FROM operations.investigations"
        ).fetchone()[0]

    print(f"database: {database}")
    print(f"runtime role: {current_user}")
    print(f"postgres: {postgres_version}")
    print(f"pgvector: {vector[0] if vector else 'NOT INSTALLED'}")
    print(f"documents: {docs}")
    print(f"chunks: {chunks}")
    print(f"investigations: {investigations}")


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
