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
        )
        settings.validate()
        return settings

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

    def require_openai_key(self) -> None:
        if not self.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is not set. Add it to your shell environment or .env file."
            )
