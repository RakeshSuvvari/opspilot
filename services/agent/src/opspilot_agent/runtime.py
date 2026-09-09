from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from agents import Agent, RunConfig, Runner, set_tracing_disabled
from agents.mcp import MCPServerStreamableHttp

from .assessment import assess_evidence
from .config import Settings
from .observability import extract_tool_records, ordered_unique_tool_names, save_run_artifact
from .prompts import SYSTEM_INSTRUCTIONS, build_investigation_prompt
from .rag.tool import build_search_knowledge_tool
from .schemas import AgentIncidentReport, IncidentReport, RunMetrics
from .timeline import build_timeline

EXPECTED_K8S_MCP_TOOLS = {
    "k8s_list_pods",
    "k8s_get_pod",
    "k8s_get_pod_logs",
    "k8s_get_events",
    "k8s_get_deployment",
}

EXPECTED_GITHUB_MCP_TOOLS = {
    "github_list_recent_commits",
    "github_get_commit",
    "github_compare_commits",
    "github_find_pull_requests_for_commit",
    "github_get_pull_request",
}


class IncidentAgentRuntime:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._started = False
        self._k8s_mcp = MCPServerStreamableHttp(
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
        self._github_mcp = None
        if settings.github_enabled:
            self._github_mcp = MCPServerStreamableHttp(
                name="OpsPilot GitHub MCP",
                params={
                    "url": settings.github_mcp_url,
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

        mcp_servers = [self._k8s_mcp]
        if self._github_mcp is not None:
            mcp_servers.append(self._github_mcp)

        self._agent = Agent(
            name="OpsPilot Incident Investigator",
            instructions=SYSTEM_INSTRUCTIONS,
            model=settings.openai_model,
            mcp_servers=mcp_servers,
            tools=local_tools,
            output_type=AgentIncidentReport,
        )

    async def start(self) -> None:
        if self._started:
            return

        set_tracing_disabled(self.settings.disable_tracing)
        try:
            await self._k8s_mcp.connect()
            if self._github_mcp is not None:
                await self._github_mcp.connect()
            self._started = True

            available_k8s = set(await self.list_k8s_mcp_tools())
            missing_k8s = EXPECTED_K8S_MCP_TOOLS - available_k8s
            if missing_k8s:
                missing_tools = ", ".join(sorted(missing_k8s))
                raise RuntimeError(f"Kubernetes MCP server is missing tools: {missing_tools}")

            if self._github_mcp is not None:
                available_github = set(await self.list_github_mcp_tools())
                missing_github = EXPECTED_GITHUB_MCP_TOOLS - available_github
                if missing_github:
                    missing_tools = ", ".join(sorted(missing_github))
                    raise RuntimeError(f"GitHub MCP server is missing tools: {missing_tools}")
        except Exception:
            await self.close()
            raise

    async def close(self) -> None:
        if not self._started:
            return
        errors: list[Exception] = []
        if self._github_mcp is not None:
            try:
                await self._github_mcp.cleanup()
            except Exception as exc:  # pragma: no cover - cleanup best effort
                errors.append(exc)
        try:
            await self._k8s_mcp.cleanup()
        except Exception as exc:  # pragma: no cover - cleanup best effort
            errors.append(exc)
        self._started = False
        if errors:
            raise errors[0]

    async def list_k8s_mcp_tools(self) -> list[str]:
        if not self._started:
            raise RuntimeError("IncidentAgentRuntime is not started")
        tools = await self._k8s_mcp.list_tools()
        return sorted(tool.name for tool in tools)

    async def list_github_mcp_tools(self) -> list[str]:
        if not self._started:
            raise RuntimeError("IncidentAgentRuntime is not started")
        if self._github_mcp is None:
            return []
        tools = await self._github_mcp.list_tools()
        return sorted(tool.name for tool in tools)

    async def list_mcp_tools(self) -> list[str]:
        tools = await self.list_k8s_mcp_tools()
        tools.extend(await self.list_github_mcp_tools())
        return sorted(tools)

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

        investigation_id = f"inv-{uuid4().hex[:12]}"
        started_at = datetime.now(timezone.utc)
        started = perf_counter()

        result = await Runner.run(
            self._agent,
            build_investigation_prompt(
                query,
                target_namespace,
                github_enabled=self.settings.github_enabled,
            ),
            max_turns=self.settings.max_turns,
            run_config=RunConfig(
                workflow_name="OpsPilot Incident Investigation",
                trace_include_sensitive_data=self.settings.trace_sensitive_data,
                trace_metadata={
                    "investigation_id": investigation_id,
                    "namespace": target_namespace,
                    "model": self.settings.openai_model,
                    "rag_enabled": str(self.settings.rag_enabled).lower(),
                    "github_enabled": str(self.settings.github_enabled).lower(),
                    "component": "opspilot-agent",
                    "phase": "6",
                },
            ),
        )

        completed_at = datetime.now(timezone.utc)
        elapsed_ms = int((perf_counter() - started) * 1000)

        output = result.final_output
        if isinstance(output, AgentIncidentReport):
            agent_report = output
        else:
            agent_report = AgentIncidentReport.model_validate(output)

        tool_records = extract_tool_records(result.new_items)
        actual_tools = ordered_unique_tool_names(tool_records)
        timeline = build_timeline(tool_records, max_events=self.settings.timeline_max_events)
        assessment = assess_evidence(agent_report, actual_tools)

        usage = result.context_wrapper.usage
        metrics = RunMetrics(
            investigation_id=investigation_id,
            started_at=started_at.isoformat().replace("+00:00", "Z"),
            completed_at=completed_at.isoformat().replace("+00:00", "Z"),
            elapsed_ms=elapsed_ms,
            model_requests=usage.requests,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.total_tokens,
            tool_call_count=len(tool_records),
            unique_tool_count=len(actual_tools),
        )

        report = IncidentReport(
            namespace=agent_report.namespace,
            status=agent_report.status,
            affected_resources=agent_report.affected_resources,
            summary=agent_report.summary,
            root_cause=agent_report.root_cause,
            confidence=assessment.confidence,
            evidence=agent_report.evidence,
            timeline=timeline,
            remediation=agent_report.remediation,
            follow_up_checks=agent_report.follow_up_checks,
            change_correlation=agent_report.change_correlation,
            tools_used=actual_tools,
            assessment=assessment,
            metrics=metrics,
        )

        if self.settings.save_run_artifacts:
            save_run_artifact(
                self.settings.run_artifact_dir,
                report,
                query=query,
                model=self.settings.openai_model,
                tool_records=tool_records,
            )

        return report

    async def __aenter__(self) -> "IncidentAgentRuntime":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()
