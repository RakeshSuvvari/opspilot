from __future__ import annotations

from pydantic import BaseModel, Field


class BenchmarkScenario(BaseModel):
    id: str
    overlay: str
    settle_seconds: float = Field(default=5.0, ge=0)
    trigger_checkout: bool = False
    wait_healthy: bool = False
    remediation_signal_groups: list[list[str]] = Field(default_factory=list)


class BenchmarkCaseResult(BaseModel):
    case_id: str
    repeat: int
    passed: bool
    score: float
    status_correct: bool
    root_cause_group_coverage: float
    tool_coverage: float
    remediation_group_coverage: float
    change_correlation_coverage: float | None = None
    confidence: str
    evidence_score: int
    elapsed_ms: int
    model_requests: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    tool_calls: int
    unique_tools: int
    estimated_cost_usd: float
    investigation_id: str
    root_cause: str
    tools_used: list[str]


class BenchmarkSummary(BaseModel):
    benchmark_id: str
    created_at: str
    model: str
    rag_enabled: bool
    github_enabled: bool
    repeats: int
    case_count: int
    run_count: int
    passed_runs: int
    pass_rate_pct: float
    status_accuracy_pct: float
    root_cause_accuracy_pct: float
    tool_coverage_pct: float
    remediation_accuracy_pct: float
    change_correlation_accuracy_pct: float | None = None
    average_score: float
    median_latency_ms: int
    p95_latency_ms: int
    average_tool_calls: float
    average_tokens: float
    total_tokens: int
    total_input_tokens: int
    total_output_tokens: int
    estimated_total_cost_usd: float
    input_price_per_million: float
    output_price_per_million: float
    results: list[BenchmarkCaseResult]
