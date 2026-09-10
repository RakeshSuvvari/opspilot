from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from opspilot_agent.config import Settings
from opspilot_agent.evals.cli import load_cases
from opspilot_agent.runtime import IncidentAgentRuntime

from .models import BenchmarkCaseResult
from .runner import load_scenarios, run_case
from .summary import build_summary


def _price(name: str, fallback: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw and raw.strip() else fallback


def _write_csv(path: Path, results: list[BenchmarkCaseResult]) -> None:
    fields = [
        "case_id", "repeat", "passed", "score", "status_correct",
        "root_cause_group_coverage", "tool_coverage", "remediation_group_coverage",
        "confidence", "evidence_score", "elapsed_ms", "model_requests",
        "input_tokens", "output_tokens", "total_tokens", "tool_calls",
        "unique_tools", "estimated_cost_usd", "investigation_id", "root_cause",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in results:
            row = result.model_dump()
            row.pop("tools_used", None)
            writer.writerow({field: row[field] for field in fields})


def _write_markdown(path: Path, summary) -> None:
    lines = [
        f"# OpsPilot benchmark {summary.benchmark_id}",
        "",
        f"- Model: `{summary.model}`",
        f"- RAG enabled: `{str(summary.rag_enabled).lower()}`",
        f"- GitHub enabled: `{str(summary.github_enabled).lower()}`",
        f"- Runs: {summary.run_count} ({summary.case_count} cases x {summary.repeats} repeat(s))",
        f"- Pass rate: **{summary.pass_rate_pct:.2f}%**",
        f"- Root-cause signal accuracy: **{summary.root_cause_accuracy_pct:.2f}%**",
        f"- Status accuracy: **{summary.status_accuracy_pct:.2f}%**",
        f"- Required-tool coverage: **{summary.tool_coverage_pct:.2f}%**",
        f"- Remediation recommendation coverage: **{summary.remediation_accuracy_pct:.2f}%**",
        *(
            [f"- GitHub change-correlation coverage: **{summary.change_correlation_accuracy_pct:.2f}%**"]
            if summary.change_correlation_accuracy_pct is not None
            else []
        ),
        f"- Average evaluation score: **{summary.average_score:.2f}/100**",
        f"- Median / P95 latency: **{summary.median_latency_ms} / {summary.p95_latency_ms} ms**",
        f"- Average tool calls: **{summary.average_tool_calls:.2f}**",
        f"- Average tokens: **{summary.average_tokens:.2f}**",
        f"- Total tokens: **{summary.total_tokens}**",
        f"- Estimated text-token cost: **${summary.estimated_total_cost_usd:.4f}**",
        "",
        "> Cost estimate uses the configured standard input/output token rates and does not apply cached-input discounts or unrelated tool fees.",
        "",
        "| Case | Pass | Score | RCA | Tools | Remediation | Latency ms | Tokens | Cost $ |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for result in summary.results:
        lines.append(
            f"| {result.case_id} r{result.repeat} | {'yes' if result.passed else 'no'} | "
            f"{result.score:.1f} | {result.root_cause_group_coverage:.0f}% | "
            f"{result.tool_coverage:.0f}% | {result.remediation_group_coverage:.0f}% | "
            f"{result.elapsed_ms} | {result.total_tokens} | {result.estimated_cost_usd:.4f} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def _benchmark(args: argparse.Namespace) -> int:
    cases = load_cases(args.cases)
    scenarios = load_scenarios(args.scenarios)
    if args.case:
        cases = [case for case in cases if case.id == args.case]
        if not cases:
            raise ValueError(f"Unknown benchmark case: {args.case}")

    missing = [case.id for case in cases if case.id not in scenarios]
    if missing:
        raise ValueError(f"Missing benchmark scenarios for: {', '.join(missing)}")

    settings = Settings.from_env()
    input_price = args.input_price_per_million
    output_price = args.output_price_per_million
    results: list[BenchmarkCaseResult] = []

    async with IncidentAgentRuntime(settings) as runtime:
        for repeat in range(1, args.repeats + 1):
            print(f"\n=== Benchmark repeat {repeat}/{args.repeats} ===")
            for case in cases:
                result = await run_case(
                    runtime=runtime,
                    case=case,
                    scenario=scenarios[case.id],
                    namespace=args.namespace,
                    repeat=repeat,
                    setup=not args.no_setup,
                    input_price_per_million=input_price,
                    output_price_per_million=output_price,
                )
                results.append(result)
                print(
                    f"  result: {case.id} score={result.score:.1f} "
                    f"pass={'yes' if result.passed else 'no'} "
                    f"latency={result.elapsed_ms}ms tokens={result.total_tokens}"
                )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    benchmark_id = f"bench-{stamp}"
    summary = build_summary(
        benchmark_id=benchmark_id,
        model=settings.openai_model,
        rag_enabled=settings.rag_enabled,
        github_enabled=settings.github_enabled,
        repeats=args.repeats,
        case_count=len(cases),
        results=results,
        input_price_per_million=input_price,
        output_price_per_million=output_price,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{benchmark_id}.json"
    csv_path = output_dir / f"{benchmark_id}.csv"
    md_path = output_dir / f"{benchmark_id}.md"
    json_path.write_text(json.dumps(summary.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8")
    _write_csv(csv_path, results)
    _write_markdown(md_path, summary)

    print("\nOpsPilot Final Benchmark")
    print("=" * 72)
    print(f"Model:                   {summary.model}")
    print(f"Runs:                    {summary.run_count}")
    print(f"Pass rate:               {summary.pass_rate_pct:.2f}%")
    print(f"Root-cause accuracy:     {summary.root_cause_accuracy_pct:.2f}%")
    print(f"Status accuracy:         {summary.status_accuracy_pct:.2f}%")
    print(f"Required-tool coverage:  {summary.tool_coverage_pct:.2f}%")
    print(f"Remediation coverage:    {summary.remediation_accuracy_pct:.2f}%")
    if summary.change_correlation_accuracy_pct is not None:
        print(f"Change correlation:      {summary.change_correlation_accuracy_pct:.2f}%")
    print(f"Average score:           {summary.average_score:.2f}/100")
    print(f"Median latency:          {summary.median_latency_ms} ms")
    print(f"P95 latency:             {summary.p95_latency_ms} ms")
    print(f"Average tool calls:      {summary.average_tool_calls:.2f}")
    print(f"Total tokens:            {summary.total_tokens}")
    print(f"Estimated token cost:    ${summary.estimated_total_cost_usd:.4f}")
    print(f"JSON: {json_path}")
    print(f"CSV:  {csv_path}")
    print(f"MD:   {md_path}")

    if args.fail_on_case_failure and summary.passed_runs != summary.run_count:
        return 2
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="opspilot-benchmark")
    parser.add_argument("--cases", default="evals/cases/benchmark.jsonl")
    parser.add_argument("--scenarios", default="benchmarks/scenarios.json")
    parser.add_argument("--namespace", default="opspilot-demo")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--case")
    parser.add_argument("--no-setup", action="store_true")
    parser.add_argument("--fail-on-case-failure", action="store_true")
    parser.add_argument("--output-dir", default=os.getenv("OPSPILOT_BENCHMARK_DIR", ".opspilot/benchmarks"))
    parser.add_argument(
        "--input-price-per-million",
        type=float,
        default=_price("OPSPILOT_BENCHMARK_INPUT_USD_PER_MILLION", 0.75),
    )
    parser.add_argument(
        "--output-price-per-million",
        type=float,
        default=_price("OPSPILOT_BENCHMARK_OUTPUT_USD_PER_MILLION", 4.50),
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.repeats < 1:
        raise SystemExit("--repeats must be >= 1")
    try:
        exit_code = asyncio.run(_benchmark(args))
    except KeyboardInterrupt:
        exit_code = 130
    except Exception as exc:
        print(f"opspilot-benchmark: {exc}", file=sys.stderr)
        exit_code = 1
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
