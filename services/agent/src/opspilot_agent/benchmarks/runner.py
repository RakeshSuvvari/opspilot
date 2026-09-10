from __future__ import annotations

import json
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from opspilot_agent.evals.models import EvaluationCase
from opspilot_agent.evals.scoring import score_report
from opspilot_agent.runtime import IncidentAgentRuntime

from .models import BenchmarkCaseResult, BenchmarkScenario
from .summary import estimate_cost


def load_scenarios(path: str) -> dict[str, BenchmarkScenario]:
    values = json.loads(Path(path).read_text(encoding="utf-8"))
    return {item.id: item for item in map(BenchmarkScenario.model_validate, values)}


def _run(command: list[str], *, quiet: bool = False) -> None:
    kwargs: dict[str, object] = {"check": True, "text": True}
    if quiet:
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.DEVNULL
    subprocess.run(command, **kwargs)


def prepare_scenario(scenario: BenchmarkScenario, namespace: str) -> None:
    print(f"  setup: {scenario.id} -> {scenario.overlay}")
    _run(["kubectl", "delete", "namespace", namespace, "--ignore-not-found=true", "--wait=true"], quiet=True)
    _run(["kubectl", "apply", "-k", scenario.overlay], quiet=True)
    _run(["kubectl", "apply", "-f", "infra/kubernetes/opspilot/k8s-mcp-server/rbac.yaml"], quiet=True)

    if scenario.wait_healthy:
        for deployment in ("checkout", "payment", "inventory"):
            _run([
                "kubectl", "rollout", "status", f"deployment/{deployment}",
                "-n", namespace, "--timeout=60s",
            ], quiet=True)

    if scenario.settle_seconds:
        time.sleep(scenario.settle_seconds)

    if scenario.trigger_checkout:
        trigger_checkout(namespace)
        time.sleep(1.0)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def trigger_checkout(namespace: str) -> None:
    port = _free_port()
    process = subprocess.Popen(
        [
            "kubectl", "port-forward", "-n", namespace,
            "service/checkout", f"{port}:8080",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        time.sleep(1.2)
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/checkout", timeout=5) as response:
                response.read()
        except urllib.error.HTTPError as exc:
            # A 5xx response is expected in timeout/DNS benchmark scenarios.
            exc.read()
        except urllib.error.URLError as exc:
            raise RuntimeError(f"unable to trigger checkout through port-forward: {exc}") from exc
    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def _coverage(groups: list[list[str]], text: str) -> float:
    if not groups:
        return 100.0
    lower = text.lower()
    matched = sum(any(signal.lower() in lower for signal in group) for group in groups)
    return round(100.0 * matched / len(groups), 2)


def make_case_result(
    *,
    case: EvaluationCase,
    scenario: BenchmarkScenario,
    repeat: int,
    report,
    input_price_per_million: float,
    output_price_per_million: float,
) -> BenchmarkCaseResult:
    evaluation = score_report(case, report)
    root_total = len(case.root_cause_signal_groups)
    root_matched = root_total - len(evaluation.missing_root_cause_groups)
    root_coverage = 100.0 if root_total == 0 else 100.0 * root_matched / root_total

    required_tools = set(case.required_tools)
    if case.expect_change_correlation:
        required_tools.update(case.required_change_tools)
    actual_tools = set(report.tools_used)
    tool_coverage = (
        100.0
        if not required_tools
        else 100.0 * len(required_tools & actual_tools) / len(required_tools)
    )

    change_coverage: float | None = None
    if case.expect_change_correlation:
        correlation_text = ""
        if report.change_correlation is not None:
            correlation_text = " ".join(
                str(part)
                for part in [
                    report.change_correlation.repository or "",
                    report.change_correlation.current_revision or "",
                    report.change_correlation.previous_revision or "",
                    report.change_correlation.commit_sha or "",
                    report.change_correlation.pull_request_number or "",
                    report.change_correlation.summary,
                    report.change_correlation.causal_link,
                ]
                if part
            )
        content_coverage = _coverage(case.expected_change_signal_groups, correlation_text)
        change_tools = set(case.required_change_tools)
        change_tool_coverage = (
            100.0
            if not change_tools
            else 100.0 * len(change_tools & actual_tools) / len(change_tools)
        )
        change_coverage = round((content_coverage + change_tool_coverage) / 2, 2)

    remediation_text = " ".join(report.remediation)
    remediation_coverage = _coverage(scenario.remediation_signal_groups, remediation_text)
    metrics = report.metrics

    return BenchmarkCaseResult(
        case_id=case.id,
        repeat=repeat,
        passed=evaluation.passed,
        score=evaluation.score,
        status_correct=report.status == case.expected_status,
        root_cause_group_coverage=round(root_coverage, 2),
        tool_coverage=round(tool_coverage, 2),
        remediation_group_coverage=remediation_coverage,
        change_correlation_coverage=change_coverage,
        confidence=report.confidence.value,
        evidence_score=report.assessment.evidence_score,
        elapsed_ms=metrics.elapsed_ms,
        model_requests=metrics.model_requests,
        input_tokens=metrics.input_tokens,
        output_tokens=metrics.output_tokens,
        total_tokens=metrics.total_tokens,
        tool_calls=metrics.tool_call_count,
        unique_tools=metrics.unique_tool_count,
        estimated_cost_usd=round(
            estimate_cost(
                metrics.input_tokens,
                metrics.output_tokens,
                input_price_per_million,
                output_price_per_million,
            ),
            6,
        ),
        investigation_id=metrics.investigation_id,
        root_cause=report.root_cause,
        tools_used=report.tools_used,
    )


async def run_case(
    *,
    runtime: IncidentAgentRuntime,
    case: EvaluationCase,
    scenario: BenchmarkScenario,
    namespace: str,
    repeat: int,
    setup: bool,
    input_price_per_million: float,
    output_price_per_million: float,
) -> BenchmarkCaseResult:
    if setup:
        prepare_scenario(scenario, namespace)
    print(f"  investigate: {case.id} repeat={repeat}")
    report = await runtime.investigate(case.query, namespace)
    return make_case_result(
        case=case,
        scenario=scenario,
        repeat=repeat,
        report=report,
        input_price_per_million=input_price_per_million,
        output_price_per_million=output_price_per_million,
    )
