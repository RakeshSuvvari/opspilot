from __future__ import annotations

import math
import statistics
from datetime import datetime, timezone

from .models import BenchmarkCaseResult, BenchmarkSummary


def _round2(value: float) -> float:
    return round(value, 2)


def percentile_nearest_rank(values: list[int], percentile: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def estimate_cost(
    input_tokens: int,
    output_tokens: int,
    input_price_per_million: float,
    output_price_per_million: float,
) -> float:
    return (
        input_tokens / 1_000_000 * input_price_per_million
        + output_tokens / 1_000_000 * output_price_per_million
    )


def build_summary(
    *,
    benchmark_id: str,
    model: str,
    rag_enabled: bool,
    github_enabled: bool,
    repeats: int,
    case_count: int,
    results: list[BenchmarkCaseResult],
    input_price_per_million: float,
    output_price_per_million: float,
) -> BenchmarkSummary:
    run_count = len(results)
    passed = sum(result.passed for result in results)
    latencies = [result.elapsed_ms for result in results]
    total_input = sum(result.input_tokens for result in results)
    total_output = sum(result.output_tokens for result in results)
    total_tokens = sum(result.total_tokens for result in results)

    def average(field: str) -> float:
        if not results:
            return 0.0
        return statistics.mean(float(getattr(result, field)) for result in results)

    change_values = [
        result.change_correlation_coverage
        for result in results
        if result.change_correlation_coverage is not None
    ]
    change_accuracy = (
        _round2(statistics.mean(change_values)) if change_values else None
    )

    return BenchmarkSummary(
        benchmark_id=benchmark_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        model=model,
        rag_enabled=rag_enabled,
        github_enabled=github_enabled,
        repeats=repeats,
        case_count=case_count,
        run_count=run_count,
        passed_runs=passed,
        pass_rate_pct=_round2(100 * passed / run_count) if run_count else 0.0,
        status_accuracy_pct=_round2(100 * average("status_correct")),
        root_cause_accuracy_pct=_round2(average("root_cause_group_coverage")),
        tool_coverage_pct=_round2(average("tool_coverage")),
        remediation_accuracy_pct=_round2(average("remediation_group_coverage")),
        change_correlation_accuracy_pct=change_accuracy,
        average_score=_round2(average("score")),
        median_latency_ms=int(statistics.median(latencies)) if latencies else 0,
        p95_latency_ms=percentile_nearest_rank(latencies, 0.95),
        average_tool_calls=_round2(average("tool_calls")),
        average_tokens=_round2(average("total_tokens")),
        total_tokens=total_tokens,
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        estimated_total_cost_usd=round(
            estimate_cost(
                total_input,
                total_output,
                input_price_per_million,
                output_price_per_million,
            ),
            6,
        ),
        input_price_per_million=input_price_per_million,
        output_price_per_million=output_price_per_million,
        results=results,
    )
