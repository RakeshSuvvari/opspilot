from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    value = int(raw)
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _env_float(name: str, default: float, minimum: float = 0.1) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    value = float(raw)
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_model: str
    k8s_mcp_url: str
    default_namespace: str
    max_turns: int
    mcp_timeout_seconds: float
    mcp_retries: int
    trace_sensitive_data: bool
    disable_tracing: bool
    host: str
    port: int
    rag_enabled: bool
    database_url: str
    postgres_admin_url: str
    embedding_model: str
    embedding_dimensions: int
    rag_top_k: int
    rag_min_similarity: float
    rag_chunk_chars: int
    rag_chunk_overlap_chars: int

    @classmethod
    def from_env(cls) -> "Settings":
        settings = cls(
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.6-terra").strip(),
            k8s_mcp_url=os.getenv(
                "OPSPILOT_K8S_MCP_URL", "http://localhost:8080/mcp"
            ).strip(),
            default_namespace=os.getenv(
                "OPSPILOT_DEFAULT_NAMESPACE", "opspilot-demo"
            ).strip(),
            max_turns=_env_int("OPSPILOT_AGENT_MAX_TURNS", 12),
            mcp_timeout_seconds=_env_float(
                "OPSPILOT_AGENT_MCP_TIMEOUT_SECONDS", 10.0
            ),
            mcp_retries=_env_int("OPSPILOT_AGENT_MCP_RETRIES", 2, minimum=0),
            trace_sensitive_data=_env_bool(
                "OPSPILOT_AGENT_TRACE_SENSITIVE_DATA", False
            ),
            disable_tracing=_env_bool("OPSPILOT_AGENT_DISABLE_TRACING", False),
            host=os.getenv("OPSPILOT_AGENT_HOST", "127.0.0.1").strip(),
            port=_env_int("OPSPILOT_AGENT_PORT", 8001),
            rag_enabled=_env_bool("OPSPILOT_RAG_ENABLED", True),
            database_url=os.getenv(
                "OPSPILOT_DATABASE_URL",
                os.getenv("DATABASE_URL", "postgresql://postgres@localhost:5432/opspilot"),
            ).strip(),
            postgres_admin_url=os.getenv(
                "OPSPILOT_POSTGRES_ADMIN_URL",
                "postgresql://postgres@localhost:5432/postgres",
            ).strip(),
            embedding_model=os.getenv(
                "OPSPILOT_EMBEDDING_MODEL", "text-embedding-3-small"
            ).strip(),
            embedding_dimensions=_env_int("OPSPILOT_EMBEDDING_DIMENSIONS", 1536),
            rag_top_k=_env_int("OPSPILOT_RAG_TOP_K", 5),
            rag_min_similarity=_env_float(
                "OPSPILOT_RAG_MIN_SIMILARITY", 0.30, minimum=0.0
            ),
            rag_chunk_chars=_env_int("OPSPILOT_RAG_CHUNK_CHARS", 1600, minimum=200),
            rag_chunk_overlap_chars=_env_int(
                "OPSPILOT_RAG_CHUNK_OVERLAP_CHARS", 200, minimum=0
            ),
        )
        settings.validate()
        return settings

    @property
    def database_name(self) -> str:
        parsed = urlparse(self.database_url)
        return parsed.path.lstrip("/") or "opspilot"

    def validate(self) -> None:
        if not self.openai_model:
            raise ValueError("OPENAI_MODEL cannot be empty")
        if not self.default_namespace:
            raise ValueError("OPSPILOT_DEFAULT_NAMESPACE cannot be empty")

        parsed = urlparse(self.k8s_mcp_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(
                "OPSPILOT_K8S_MCP_URL must be an http(s) URL, for example "
                "http://localhost:8080/mcp"
            )

        for name, url in (
            ("OPSPILOT_DATABASE_URL", self.database_url),
            ("OPSPILOT_POSTGRES_ADMIN_URL", self.postgres_admin_url),
        ):
            parsed_db = urlparse(url)
            if parsed_db.scheme not in {"postgres", "postgresql"} or not parsed_db.netloc:
                raise ValueError(f"{name} must be a PostgreSQL connection URL")

        if not self.embedding_model:
            raise ValueError("OPSPILOT_EMBEDDING_MODEL cannot be empty")
        if self.embedding_dimensions != 1536:
            raise ValueError(
                "Phase 4 schema uses vector(1536); set OPSPILOT_EMBEDDING_DIMENSIONS=1536"
            )
        if self.rag_top_k > 10:
            raise ValueError("OPSPILOT_RAG_TOP_K must be <= 10")
        if self.rag_min_similarity > 1.0:
            raise ValueError("OPSPILOT_RAG_MIN_SIMILARITY must be <= 1.0")
        if self.rag_chunk_overlap_chars >= self.rag_chunk_chars:
            raise ValueError(
                "OPSPILOT_RAG_CHUNK_OVERLAP_CHARS must be smaller than OPSPILOT_RAG_CHUNK_CHARS"
            )

    def require_openai_key(self) -> None:
        if not self.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is not set. Add it to your shell environment or .env file."
            )

    def require_database(self) -> None:
        if not self.database_url:
            raise ValueError("OPSPILOT_DATABASE_URL is not set")
