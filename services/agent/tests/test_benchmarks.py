import unittest

from opspilot_agent.benchmarks.models import BenchmarkCaseResult
from opspilot_agent.benchmarks.summary import build_summary, estimate_cost, percentile_nearest_rank


class BenchmarkSummaryTests(unittest.TestCase):
    def test_estimate_cost(self):
        value = estimate_cost(1_000_000, 1_000_000, 0.75, 4.50)
        self.assertEqual(value, 5.25)

    def test_percentile_nearest_rank(self):
        self.assertEqual(percentile_nearest_rank([100, 200, 300, 400], 0.95), 400)

    def test_build_summary(self):
        base = {
            "repeat": 1,
            "passed": True,
            "score": 90.0,
            "status_correct": True,
            "root_cause_group_coverage": 100.0,
            "tool_coverage": 100.0,
            "remediation_group_coverage": 100.0,
            "confidence": "high",
            "evidence_score": 100,
            "model_requests": 2,
            "input_tokens": 1000,
            "output_tokens": 100,
            "total_tokens": 1100,
            "tool_calls": 5,
            "unique_tools": 4,
            "estimated_cost_usd": 0.0012,
            "root_cause": "root cause",
            "tools_used": ["k8s_list_pods"],
        }
        results = [
            BenchmarkCaseResult(case_id="INC-001", elapsed_ms=1000, investigation_id="inv-1", **base),
            BenchmarkCaseResult(case_id="INC-002", elapsed_ms=3000, investigation_id="inv-2", **base),
        ]
        summary = build_summary(
            benchmark_id="bench-test",
            model="gpt-5.4-mini",
            rag_enabled=True,
            github_enabled=False,
            repeats=1,
            case_count=2,
            results=results,
            input_price_per_million=0.75,
            output_price_per_million=4.50,
        )
        self.assertEqual(summary.pass_rate_pct, 100.0)
        self.assertEqual(summary.median_latency_ms, 2000)
        self.assertEqual(summary.p95_latency_ms, 3000)
        self.assertEqual(summary.total_tokens, 2200)


if __name__ == "__main__":
    unittest.main()
