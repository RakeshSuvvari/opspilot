from __future__ import annotations

import inspect
import json
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4

from agents import Agent, ModelSettings, RunConfig, Runner, set_tracing_disabled
from agents.mcp import MCPServerStreamableHttp, create_static_tool_filter

from .assessment import assess_evidence
from .config import Settings
from .history import HistoryStore
from .observability import ToolRecord, extract_tool_records, ordered_unique_tool_names, save_run_artifact
from .prompts import (
    REMEDIATION_INSTRUCTIONS,
    SYSTEM_INSTRUCTIONS,
    build_investigation_prompt,
    build_remediation_prompt,
)
from .rag.tool import build_search_knowledge_tool
from .schemas import (
    AgentIncidentReport,
    ApprovalRequest,
    IncidentReport,
    RemediationAction,
    RunMetrics,
)
from .timeline import build_timeline

READ_K8S_MCP_TOOLS = {
    "k8s_list_pods",
    "k8s_get_pod",
    "k8s_get_pod_logs",
    "k8s_get_events",
    "k8s_get_deployment",
}

REMEDIATION_K8S_MCP_TOOLS = {
    "k8s_restart_deployment",
    "k8s_scale_deployment",
    "k8s_rollback_deployment",
}

EXPECTED_GITHUB_MCP_TOOLS = {
    "github_list_recent_commits",
    "github_get_commit",
    "github_compare_commits",
    "github_find_pull_requests_for_commit",
    "github_get_pull_request",
}

ApprovalHandler = Callable[[ApprovalRequest], bool | Awaitable[bool]]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _ApprovalDecision:
    request: ApprovalRequest
    approved: bool

@dataclass(frozen=True)
class _RemediationSelection:
    tool_name: str
    deployment_name: str
    replicas: int | None = None

class IncidentAgentRuntime:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._started = False
        self.history = HistoryStore(settings.database_url) if settings.history_enabled else None

        common_params = {
            "url": settings.k8s_mcp_url,
            "timeout": settings.mcp_timeout_seconds,
        }
        self._k8s_mcp = MCPServerStreamableHttp(
            name="OpsPilot Kubernetes MCP",
            params=common_params,
            cache_tools_list=True,
            use_structured_content=True,
            max_retry_attempts=settings.mcp_retries,
            require_approval="never",
            tool_filter=create_static_tool_filter(
                blocked_tool_names=sorted(REMEDIATION_K8S_MCP_TOOLS),
            ),
        )

        self._k8s_remediation_mcp = None
        if settings.remediation_enabled:
            self._k8s_remediation_mcp = MCPServerStreamableHttp(
                name="OpsPilot Kubernetes MCP - Remediation",
                params=common_params,
                cache_tools_list=True,
                use_structured_content=True,
                max_retry_attempts=settings.mcp_retries,
                require_approval={
                    "always": {"tool_names": sorted(REMEDIATION_K8S_MCP_TOOLS)},
                },
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

        read_servers = [self._k8s_mcp]
        if self._github_mcp is not None:
            read_servers.append(self._github_mcp)

        self._agent = Agent(
            name="OpsPilot Incident Investigator",
            instructions=SYSTEM_INSTRUCTIONS,
            model=settings.openai_model,
            mcp_servers=read_servers,
            tools=local_tools,
            output_type=AgentIncidentReport,
        )

        self._remediation_agent = None
        if self._k8s_remediation_mcp is not None:
            remediation_servers = [self._k8s_remediation_mcp]
            if self._github_mcp is not None:
                remediation_servers.append(self._github_mcp)
            self._remediation_agent = Agent(
                name="OpsPilot Incident Remediator",
                instructions=REMEDIATION_INSTRUCTIONS,
                model=settings.openai_model,
                mcp_servers=remediation_servers,
                tools=local_tools,
                output_type=AgentIncidentReport,
            )

    async def start(self) -> None:
        if self._started:
            return

        set_tracing_disabled(self.settings.disable_tracing)
        try:
            await self._k8s_mcp.connect()
            if self._k8s_remediation_mcp is not None:
                await self._k8s_remediation_mcp.connect()
            if self._github_mcp is not None:
                await self._github_mcp.connect()
            self._started = True

            available_k8s = set(await self.list_k8s_mcp_tools())
            missing_k8s = READ_K8S_MCP_TOOLS - available_k8s
            if missing_k8s:
                raise RuntimeError(
                    "Kubernetes MCP server is missing tools: " + ", ".join(sorted(missing_k8s))
                )

            if self._k8s_remediation_mcp is not None:
                remediation_tools = set(await self.list_remediation_mcp_tools())
                expected = READ_K8S_MCP_TOOLS | REMEDIATION_K8S_MCP_TOOLS
                missing = expected - remediation_tools
                if missing:
                    raise RuntimeError(
                        "Kubernetes MCP remediation server is missing tools: "
                        + ", ".join(sorted(missing))
                        + ". Enable Phase 7 write tools on the Go MCP server first."
                    )

            if self._github_mcp is not None:
                available_github = set(await self.list_github_mcp_tools())
                missing_github = EXPECTED_GITHUB_MCP_TOOLS - available_github
                if missing_github:
                    raise RuntimeError(
                        "GitHub MCP server is missing tools: "
                        + ", ".join(sorted(missing_github))
                    )
        except Exception:
            await self.close()
            raise

    async def close(self) -> None:
        servers = [self._github_mcp, self._k8s_remediation_mcp, self._k8s_mcp]
        errors: list[Exception] = []
        for server in servers:
            if server is None:
                continue
            try:
                await server.cleanup()
            except Exception as exc:  # pragma: no cover
                errors.append(exc)
        self._started = False
        if errors:
            raise errors[0]

    async def list_k8s_mcp_tools(self) -> list[str]:
        if not self._started:
            raise RuntimeError("IncidentAgentRuntime is not started")
        return sorted(tool.name for tool in await self._k8s_mcp.list_tools())

    async def list_remediation_mcp_tools(self) -> list[str]:
        if not self._started:
            raise RuntimeError("IncidentAgentRuntime is not started")
        if self._k8s_remediation_mcp is None:
            return []
        return sorted(tool.name for tool in await self._k8s_remediation_mcp.list_tools())

    async def list_github_mcp_tools(self) -> list[str]:
        if not self._started:
            raise RuntimeError("IncidentAgentRuntime is not started")
        if self._github_mcp is None:
            return []
        return sorted(tool.name for tool in await self._github_mcp.list_tools())

    async def list_tools(self, include_remediation: bool = False) -> list[str]:
        tools = (
            await self.list_remediation_mcp_tools()
            if include_remediation and self._k8s_remediation_mcp is not None
            else await self.list_k8s_mcp_tools()
        )
        tools.extend(await self.list_github_mcp_tools())
        if self.settings.rag_enabled:
            tools.append("search_knowledge")
        return sorted(set(tools))

    async def investigate(self, query: str, namespace: str | None = None) -> IncidentReport:
        return await self._run(
            query=query,
            namespace=namespace,
            remediation=False,
            approval_handler=None,
        )

    async def remediate(
        self,
        query: str,
        namespace: str | None,
        approval_handler: ApprovalHandler,
        *,
        job_id: str | None = None,
    ) -> IncidentReport:
        if not self.settings.remediation_enabled or self._remediation_agent is None:
            raise ValueError(
                "Human-approved remediation is disabled. Set OPSPILOT_REMEDIATION_ENABLED=true "
                "and enable the Go MCP write tools/RBAC with make phase7-up."
            )
        return await self._run(
            query=query,
            namespace=namespace,
            remediation=True,
            approval_handler=approval_handler,
            job_id=job_id,
        )

    async def _run(
        self,
        query: str,
        namespace: str | None,
        remediation: bool,
        approval_handler: ApprovalHandler | None,
        job_id: str | None = None,
    ) -> IncidentReport:
        if not self._started:
            raise RuntimeError("IncidentAgentRuntime is not started")
        self.settings.require_openai_key()
        target_namespace = (namespace or self.settings.default_namespace).strip()
        if not target_namespace:
            raise ValueError("namespace cannot be empty")

        investigation_id = f"inv-{uuid4().hex[:12]}"
        started_at = datetime.now(timezone.utc)
        started = perf_counter()
        agent = self._remediation_agent if remediation else self._agent
        assert agent is not None
        prompt = (
            build_remediation_prompt(query, target_namespace, self.settings.github_enabled)
            if remediation
            else build_investigation_prompt(query, target_namespace, self.settings.github_enabled)
        )
        run_config = RunConfig(
            workflow_name=(
                "OpsPilot Human-Approved Remediation"
                if remediation
                else "OpsPilot Incident Investigation"
            ),
            trace_include_sensitive_data=self.settings.trace_sensitive_data,
            trace_metadata={
                "investigation_id": investigation_id,
                "namespace": target_namespace,
                "model": self.settings.openai_model,
                "rag_enabled": str(self.settings.rag_enabled).lower(),
                "github_enabled": str(self.settings.github_enabled).lower(),
                "remediation_enabled": str(remediation).lower(),
                "component": "opspilot-agent",
                "phase": "9",
            },
        )

        active_agent = agent

        result = await Runner.run(
            active_agent,
            prompt,
            max_turns=self.settings.max_turns,
            run_config=run_config,
        )

        usage_totals = _usage_totals(result)
        records: list[ToolRecord] = []
        decisions: list[_ApprovalDecision] = []

        records = _merge_tool_records(
            records,
            extract_tool_records(result.new_items),
        )

        #
        # The model may correctly diagnose an incident and recommend remediation
        # without actually emitting the mutating MCP tool call.
        #
        # In remediation mode, convert that recommendation into a dedicated
        # action turn and force the exact supported tool.
        #
        if remediation and not result.interruptions:
            write_tool_used = any(
                record.name in REMEDIATION_K8S_MCP_TOOLS
                for record in records
            )

            if not write_tool_used and result.final_output is not None:
                preliminary_report = (
                    result.final_output
                    if isinstance(result.final_output, AgentIncidentReport)
                    else AgentIncidentReport.model_validate(result.final_output)
                )

                selection = _select_remediation_action(preliminary_report)

                if selection is not None:
                    active_agent = agent.clone(
                        name="OpsPilot Incident Remediator - Action Turn",
                        model_settings=ModelSettings(
                            tool_choice=selection.tool_name,
                        ),
                        reset_tool_choice=True,
                    )

                    action_input = result.to_input_list()

                    action_input.append(
                        {
                            "role": "user",
                            "content": _build_action_prompt(
                                selection,
                                target_namespace,
                            ),
                        }
                    )

                    result = await Runner.run(
                        active_agent,
                        action_input,
                        max_turns=self.settings.max_turns,
                        run_config=run_config,
                    )

                    _accumulate_usage(usage_totals, result)

                    records = _merge_tool_records(
                        records,
                        extract_tool_records(result.new_items),
                    )

        while remediation and result.interruptions:
            if approval_handler is None:
                raise RuntimeError("remediation run requires an approval handler")
            state = result.to_state()
            for interruption in result.interruptions:
                request = _approval_request(interruption)
                answer = approval_handler(request)
                approved = await answer if inspect.isawaitable(answer) else bool(answer)
                decisions.append(_ApprovalDecision(request=request, approved=approved))
                if approved:
                    state.approve(interruption, always_approve=False)
                else:
                    state.reject(
                        interruption,
                        rejection_message=(
                            "The human reviewer rejected this Kubernetes remediation action. "
                            "Do not execute it; continue with safe read-only verification/recommendations."
                        ),
                    )
            result = await Runner.run(
                active_agent,
                state,
                max_turns=self.settings.max_turns,
                run_config=run_config,
            )
            _accumulate_usage(usage_totals, result)
            records = _merge_tool_records(records, extract_tool_records(result.new_items))

        completed_at = datetime.now(timezone.utc)
        elapsed_ms = int((perf_counter() - started) * 1000)
        output = result.final_output
        agent_report = output if isinstance(output, AgentIncidentReport) else AgentIncidentReport.model_validate(output)

        actual_tools = ordered_unique_tool_names(records)
        timeline = build_timeline(records, max_events=self.settings.timeline_max_events)
        assessment = assess_evidence(agent_report, actual_tools)
        actions = _build_remediation_actions(decisions, records)

        metrics = RunMetrics(
            investigation_id=investigation_id,
            started_at=started_at.isoformat().replace("+00:00", "Z"),
            completed_at=completed_at.isoformat().replace("+00:00", "Z"),
            elapsed_ms=elapsed_ms,
            model_requests=usage_totals["requests"],
            input_tokens=usage_totals["input_tokens"],
            output_tokens=usage_totals["output_tokens"],
            total_tokens=usage_totals["total_tokens"],
            tool_call_count=len(records),
            unique_tool_count=len(actual_tools),
            approval_requests=len(decisions),
            approved_actions=sum(1 for decision in decisions if decision.approved),
            rejected_actions=sum(1 for decision in decisions if not decision.approved),
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
            remediation_actions=actions,
        )
        if self.settings.save_run_artifacts:
            save_run_artifact(
                self.settings.run_artifact_dir,
                report,
                query=query,
                model=self.settings.openai_model,
                tool_records=records,
            )

        if self.history is not None:
            try:
                await self.history.save_investigation(
                    report,
                    query=query,
                    run_mode="remediate" if remediation else "investigate",
                    tool_records=records,
                    job_id=job_id,
                )
            except Exception as exc:  # Persistence must not hide a completed RCA.
                logger.warning(
                    "failed to persist investigation history",
                    extra={
                        "investigation_id": report.metrics.investigation_id,
                        "error": str(exc),
                    },
                )
        return report

    async def __aenter__(self) -> "IncidentAgentRuntime":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()


def _deployment_from_report(report: AgentIncidentReport) -> str | None:
    for resource in report.affected_resources:
        value = resource.strip()

        if value.lower().startswith("deployment/"):
            return value.split("/", 1)[1]

    return None


def _select_remediation_action(
        report: AgentIncidentReport,
    ) -> _RemediationSelection | None:
        deployment_name = _deployment_from_report(report)

        if not deployment_name:
            return None

        remediation_text = " ".join(report.remediation).lower()

        if "rollback" in remediation_text:
            return _RemediationSelection(
                tool_name="k8s_rollback_deployment",
                deployment_name=deployment_name,
            )

        if (
            "restart deployment" in remediation_text
            or "restart the deployment" in remediation_text
        ):
            return _RemediationSelection(
                tool_name="k8s_restart_deployment",
                deployment_name=deployment_name,
            )

        scale_match = re.search(
            r"\bscale\b[^.]*?\bto\s+(\d+)\b",
            remediation_text,
        )

        if scale_match:
            return _RemediationSelection(
                tool_name="k8s_scale_deployment",
                deployment_name=deployment_name,
                replicas=int(scale_match.group(1)),
            )

        return None


def _build_action_prompt(
        selection: _RemediationSelection,
        namespace: str,
    ) -> str:
        replicas = ""

        if selection.replicas is not None:
            replicas = f"\nReplicas: {selection.replicas}"

        return f"""
    The investigation is complete and identified a supported remediation action.

    You previously recommended this exact corrective action:
    Tool: {selection.tool_name}
    Namespace: {namespace}
    Deployment: {selection.deployment_name}{replicas}

    This is now the remediation execution turn.

    You MUST call {selection.tool_name} before producing another final report.
    Do not substitute a different mutating action.

    The tool is human-approval protected. The runtime will pause before execution.
    If the human approves it, execute the action, then use read-only Kubernetes
    tools to verify recovery before returning the updated structured incident report.

    If the human rejects it, do not attempt an alternative write action unless
    the rejection explicitly requests one.
    """.strip()


def _usage_totals(result: Any) -> dict[str, int]:
    usage = result.context_wrapper.usage
    return {
        "requests": int(usage.requests),
        "input_tokens": int(usage.input_tokens),
        "output_tokens": int(usage.output_tokens),
        "total_tokens": int(usage.total_tokens),
    }


def _accumulate_usage(totals: dict[str, int], result: Any) -> None:
    current = _usage_totals(result)
    for key, value in current.items():
        totals[key] += value



def _parse_arguments(raw: Any) -> dict[str, object]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _approval_request(interruption: Any) -> ApprovalRequest:
    tool_name = getattr(interruption, "name", None) or getattr(interruption, "tool_name", None) or "unknown_tool"
    arguments = _parse_arguments(getattr(interruption, "arguments", None))
    call_id = getattr(interruption, "call_id", None)
    if tool_name == "k8s_rollback_deployment":
        risk, reason = "high", "Replaces the live Deployment pod template with a previous ReplicaSet revision."
    elif tool_name == "k8s_scale_deployment":
        replicas = arguments.get("replicas")
        risk = "high" if replicas == 0 else "medium"
        reason = "Changes live workload capacity and can affect availability/cost."
    else:
        risk, reason = "medium", "Restarts live workload pods by changing the Deployment pod template."
    return ApprovalRequest(
        call_id=call_id,
        tool_name=tool_name,
        arguments=arguments,
        risk=risk,
        reason=reason,
    )


def _merge_tool_records(existing: list[ToolRecord], new: list[ToolRecord]) -> list[ToolRecord]:
    by_key: dict[str, ToolRecord] = {}
    order: list[str] = []
    for record in [*existing, *new]:
        key = record.call_id or f"{record.name}:{json.dumps(record.arguments, sort_keys=True, default=str)}"
        if key not in by_key:
            order.append(key)
            by_key[key] = record
        elif record.output is not None:
            by_key[key] = record
    return [by_key[key] for key in order]


def _build_remediation_actions(
    decisions: list[_ApprovalDecision],
    records: list[ToolRecord],
) -> list[RemediationAction]:
    by_call_id = {record.call_id: record for record in records if record.call_id}
    actions: list[RemediationAction] = []
    for decision in decisions:
        req = decision.request
        record = by_call_id.get(req.call_id) if req.call_id else None
        if record is None and decision.approved:
            for candidate in records:
                if candidate.name == req.tool_name and candidate.arguments == req.arguments and candidate.output is not None:
                    record = candidate
                    break
        resource_name = str(req.arguments.get("deployment_name", "unknown"))
        namespace = str(req.arguments.get("namespace", "opspilot-demo"))
        result = record.output if record is not None else None
        if not decision.approved:
            status = "rejected"
        elif result is not None:
            status = "executed"
        else:
            status = "approved_no_result"
        actions.append(
            RemediationAction(
                call_id=req.call_id,
                tool_name=req.tool_name,
                resource=f"deployment/{namespace}/{resource_name}",
                arguments=req.arguments,
                approved=decision.approved,
                status=status,
                result=result,
            )
        )
    return actions
