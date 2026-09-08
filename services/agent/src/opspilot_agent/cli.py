from __future__ import annotations

import argparse
import asyncio
import json
import sys

from .config import Settings
from .runtime import IncidentAgentRuntime
from .schemas import IncidentReport


DEFAULT_QUERY = (
    "Investigate the current Kubernetes incident. Identify the most likely root cause, "
    "support it with live evidence, and recommend a safe remediation."
)


def _print_report(report: IncidentReport) -> None:
    print("OpsPilot Investigation")
    print("=" * 72)
    print(f"Namespace:   {report.namespace}")
    print(f"Status:      {report.status.value}")
    print(f"Confidence:  {report.confidence.value}")
    if report.affected_resources:
        print(f"Affected:    {', '.join(report.affected_resources)}")
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
        print("\nTimeline")
        for item in report.timeline:
            print(f"- {item.timestamp}: {item.event}")

    print("\nRecommended remediation")
    for step in report.remediation:
        print(f"- {step}")

    if report.follow_up_checks:
        print("\nFollow-up checks")
        for step in report.follow_up_checks:
            print(f"- {step}")

    print("\nTools used")
    print(", ".join(report.tools_used) if report.tools_used else "none")


async def _run_tools(settings: Settings) -> int:
    async with IncidentAgentRuntime(settings) as runtime:
        tools = await runtime.list_tools()
        print("Connected to Kubernetes MCP server.")
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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="opspilot-agent",
        description="OpsPilot OpenAI-powered Kubernetes incident investigator",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "tools", help="Connect to the Go MCP server and list Kubernetes diagnostic tools"
    )

    investigate = subparsers.add_parser(
        "investigate", help="Run an evidence-backed Kubernetes incident investigation"
    )
    investigate.add_argument("--query", default=DEFAULT_QUERY)
    investigate.add_argument("--namespace", default=None)
    investigate.add_argument("--json", action="store_true")
    return parser


def main() -> None:
    args = _parser().parse_args()
    try:
        settings = Settings.from_env()
        if args.command == "tools":
            exit_code = asyncio.run(_run_tools(settings))
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
