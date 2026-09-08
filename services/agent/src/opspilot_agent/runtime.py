from __future__ import annotations

from agents import Agent, RunConfig, Runner, set_tracing_disabled
from agents.mcp import MCPServerStreamableHttp

from .config import Settings
from .prompts import SYSTEM_INSTRUCTIONS, build_investigation_prompt
from .rag.tool import build_search_knowledge_tool
from .schemas import IncidentReport

EXPECTED_MCP_TOOLS = {
    "k8s_list_pods",
    "k8s_get_pod",
    "k8s_get_pod_logs",
    "k8s_get_events",
    "k8s_get_deployment",
}


class IncidentAgentRuntime:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._started = False
        self._mcp = MCPServerStreamableHttp(
            name="OpsPilot Kubernetes MCP",
            params={
                "url": settings.k8s_mcp_url,
                "timeout": settings.mcp_timeout_seconds,
            },
            cache_tools_list=True,
            use_structured_content=True,
            max_retry_attempts=settings.mcp_retries,
            require_approval="never",
        )
        local_tools = []
        if settings.rag_enabled:
            local_tools.append(build_search_knowledge_tool(settings))

        self._agent = Agent(
            name="OpsPilot Incident Investigator",
            instructions=SYSTEM_INSTRUCTIONS,
            model=settings.openai_model,
            mcp_servers=[self._mcp],
            tools=local_tools,
            output_type=IncidentReport,
        )

    async def start(self) -> None:
        if self._started:
            return

        set_tracing_disabled(self.settings.disable_tracing)
        await self._mcp.connect()
        self._started = True

        available = set(await self.list_mcp_tools())
        missing = EXPECTED_MCP_TOOLS - available
        if missing:
            await self.close()
            missing_tools = ", ".join(sorted(missing))
            raise RuntimeError(f"Kubernetes MCP server is missing tools: {missing_tools}")

    async def close(self) -> None:
        if not self._started:
            return
        try:
            await self._mcp.cleanup()
        finally:
            self._started = False

    async def list_mcp_tools(self) -> list[str]:
        if not self._started:
            raise RuntimeError("IncidentAgentRuntime is not started")
        tools = await self._mcp.list_tools()
        return sorted(tool.name for tool in tools)

    async def list_tools(self) -> list[str]:
        tools = await self.list_mcp_tools()
        if self.settings.rag_enabled:
            tools.append("search_knowledge")
        return sorted(tools)

    async def investigate(self, query: str, namespace: str | None = None) -> IncidentReport:
        if not self._started:
            raise RuntimeError("IncidentAgentRuntime is not started")

        self.settings.require_openai_key()
        target_namespace = (namespace or self.settings.default_namespace).strip()
        if not target_namespace:
            raise ValueError("namespace cannot be empty")

        result = await Runner.run(
            self._agent,
            build_investigation_prompt(query, target_namespace),
            max_turns=self.settings.max_turns,
            run_config=RunConfig(
                workflow_name="OpsPilot Incident Investigation",
                trace_include_sensitive_data=self.settings.trace_sensitive_data,
                trace_metadata={
                    "namespace": target_namespace,
                    "model": self.settings.openai_model,
                    "rag_enabled": str(self.settings.rag_enabled).lower(),
                    "component": "opspilot-agent",
                },
            ),
        )

        output = result.final_output
        if isinstance(output, IncidentReport):
            return output
        return IncidentReport.model_validate(output)

    async def __aenter__(self) -> "IncidentAgentRuntime":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()
