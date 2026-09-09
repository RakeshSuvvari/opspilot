from __future__ import annotations

import argparse
import asyncio
import json
import sys

from .config import Settings
from .runtime import IncidentAgentRuntime
from .schemas import ApprovalRequest, IncidentReport


DEFAULT_QUERY = (
    "Investigate the current Kubernetes incident. Identify the most likely root cause, "
    "support it with live evidence, and recommend a safe remediation."
)


def _print_report(report: IncidentReport) -> None:
    print("OpsPilot Investigation")
    print("=" * 72)
    print(f"Investigation: {report.metrics.investigation_id}")
    print(f"Namespace:     {report.namespace}")
    print(f"Status:        {report.status.value}")
    print(f"Confidence:    {report.confidence.value} ({report.assessment.confidence_score}/100)")
    print(f"Evidence:      {report.assessment.evidence_score}/100")
    if report.affected_resources:
        print(f"Affected:      {', '.join(report.affected_resources)}")
    print()
    print("Summary")
    print(report.summary)
    print()
    print("Root cause")
    print(report.root_cause)

    print("\nEvidence")
    if not report.evidence:
        print("- No conclusive evidence collected.")
    for index, item in enumerate(report.evidence, start=1):
        print(f"{index}. [{item.source}] {item.resource}: {item.observation}")
        print(f"   Supports: {item.supports}")

    if report.timeline:
        print("\nDeterministic timeline")
        for item in report.timeline:
            print(f"- {item.timestamp}: {item.event}")

    print("\nRecommended remediation")
    for step in report.remediation:
        print(f"- {step}")

    if report.change_correlation is not None:
        change = report.change_correlation
        print("\nDeployment/source change correlation")
        if change.repository:
            print(f"- Repository: {change.repository}")
        if change.current_revision:
            print(f"- Current revision: {change.current_revision}")
        if change.previous_revision:
            print(f"- Previous revision: {change.previous_revision}")
        if change.pull_request_number:
            print(f"- Pull request: #{change.pull_request_number}")
        print(f"- Change: {change.summary}")
        print(f"- Causal link: {change.causal_link}")

    if report.follow_up_checks:
        print("\nFollow-up checks")
        for step in report.follow_up_checks:
            print(f"- {step}")

    print("\nEvidence assessment")
    print(f"- Live sources: {report.assessment.live_source_count}")
    print(f"- Corroborated: {'yes' if report.assessment.corroborated else 'no'}")
    print(f"- RAG used: {'yes' if report.assessment.knowledge_used else 'no'}")
    print(f"- GitHub change intelligence: {'yes' if report.assessment.change_intelligence_used else 'no'}")
    print(f"- Model confidence: {report.assessment.model_confidence.value}")
    for reason in report.assessment.reasons:
        print(f"- {reason}")

    print("\nTools used")
    print(", ".join(report.tools_used) if report.tools_used else "none")

    print("\nRun metrics")
    print(f"- Elapsed: {report.metrics.elapsed_ms} ms")
    print(f"- Model requests: {report.metrics.model_requests}")
    print(f"- Tokens: {report.metrics.total_tokens} total "
          f"({report.metrics.input_tokens} input / {report.metrics.output_tokens} output)")
    print(f"- Tool calls: {report.metrics.tool_call_count} "
          f"({report.metrics.unique_tool_count} unique)")
    if report.metrics.approval_requests:
        print(f"- Approval requests: {report.metrics.approval_requests} "
              f"({report.metrics.approved_actions} approved / {report.metrics.rejected_actions} rejected)")

    if report.remediation_actions:
        print("\nHuman-approved remediation actions")
        for action in report.remediation_actions:
            print(f"- {action.tool_name} -> {action.resource}: {action.status}")


async def _run_tools(settings: Settings, include_remediation: bool = False) -> int:
    async with IncidentAgentRuntime(settings) as runtime:
        tools = await runtime.list_tools(include_remediation=include_remediation)
        print("Connected to OpsPilot MCP/tool services.")
        for tool in tools:
            print(f"- {tool}")
    return 0


async def _run_investigation(args: argparse.Namespace, settings: Settings) -> int:
    async with IncidentAgentRuntime(settings) as runtime:
        report = await runtime.investigate(args.query, args.namespace)

    if args.json:
        print(json.dumps(report.model_dump(mode="json"), indent=2))
    else:
        _print_report(report)
    return 0


async def _prompt_approval(request: ApprovalRequest) -> bool:
    print("\n" + "!" * 72)
    print("HUMAN APPROVAL REQUIRED")
    print(f"Tool:   {request.tool_name}")
    print(f"Risk:   {request.risk.upper()}")
    print(f"Reason: {request.reason}")
    print("Arguments:")
    print(json.dumps(request.arguments, indent=2, sort_keys=True))
    print("!" * 72)

    answer = await asyncio.to_thread(
        input,
        "Approve this exact Kubernetes action? [y/N]: ",
    )

    return answer.strip().lower() in {"y", "yes"}


async def _run_remediation(args: argparse.Namespace, settings: Settings) -> int:
    async with IncidentAgentRuntime(settings) as runtime:
        report = await runtime.remediate(args.query, args.namespace, _prompt_approval)

    if args.json:
        print(json.dumps(report.model_dump(mode="json"), indent=2))
    else:
        _print_report(report)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="opspilot-agent",
        description="OpsPilot OpenAI-powered Kubernetes incident investigator",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    tools_parser = subparsers.add_parser(
        "tools", help="Connect to configured MCP servers and list available diagnostic/change tools"
    )
    tools_parser.add_argument("--remediation", action="store_true", help="Include Phase 7 mutating tools (requires remediation enabled)")

    investigate = subparsers.add_parser(
        "investigate", help="Run an evidence-backed Kubernetes incident investigation"
    )
    investigate.add_argument("--query", default=DEFAULT_QUERY)
    investigate.add_argument("--namespace", default=None)
    investigate.add_argument("--json", action="store_true")

    remediate = subparsers.add_parser(
        "remediate", help="Investigate and, when justified, request human approval for narrowly scoped Kubernetes remediation"
    )
    remediate.add_argument("--query", default=DEFAULT_QUERY)
    remediate.add_argument("--namespace", default=None)
    remediate.add_argument("--json", action="store_true")
    return parser


def main() -> None:
    args = _parser().parse_args()
    try:
        settings = Settings.from_env()
        if args.command == "tools":
            exit_code = asyncio.run(_run_tools(settings, args.remediation))
        elif args.command == "remediate":
            exit_code = asyncio.run(_run_remediation(args, settings))
        else:
            exit_code = asyncio.run(_run_investigation(args, settings))
    except KeyboardInterrupt:
        exit_code = 130
    except Exception as exc:
        print(f"opspilot-agent: {exc}", file=sys.stderr)
        exit_code = 1
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
