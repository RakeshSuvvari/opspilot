import unittest

from opspilot_agent.evals.models import EvaluationCase
from opspilot_agent.evals.scoring import score_report
from opspilot_agent.schemas import IncidentReport


class EvalScoringTests(unittest.TestCase):
    def test_expected_report_passes(self):
        case = EvaluationCase.model_validate(
            {
                "id": "INC-001",
                "query": "why",
                "root_cause_signal_groups": [["database_url"], ["missing"]],
                "required_tools": ["k8s_list_pods", "k8s_get_pod_logs"],
                "expected_affected_any": ["payment"],
                "expect_knowledge": True,
            }
        )
        report = IncidentReport.model_validate(
            {
                "namespace": "opspilot-demo",
                "status": "incident",
                "affected_resources": ["deployment/payment"],
                "summary": "payment failing",
                "root_cause": "DATABASE_URL is missing from payment configuration",
                "confidence": "high",
                "evidence": [],
                "timeline": [{"timestamp": "2026-09-08T10:00:00Z", "event": "failure"}],
                "remediation": [],
                "follow_up_checks": [],
                "tools_used": ["k8s_list_pods", "k8s_get_pod_logs", "search_knowledge"],
                "assessment": {
                    "evidence_score": 80,
                    "confidence_score": 80,
                    "confidence": "high",
                    "model_confidence": "high",
                    "live_source_count": 2,
                    "knowledge_used": True,
                    "change_intelligence_used": False,
                    "corroborated": True,
                    "reasons": [],
                },
                "metrics": {
                    "investigation_id": "inv-test",
                    "started_at": "2026-09-08T10:00:00Z",
                    "completed_at": "2026-09-08T10:00:01Z",
                    "elapsed_ms": 1000,
                    "model_requests": 2,
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "total_tokens": 150,
                    "tool_call_count": 3,
                    "unique_tool_count": 3,
                },
            }
        )
        result = score_report(case, report)
        self.assertTrue(result.passed)
        self.assertEqual(result.score, 100.0)

    def test_change_aware_report_scores_change_correlation(self):
        case = EvaluationCase.model_validate(
            {
                "id": "INC-001-GIT",
                "query": "why",
                "root_cause_signal_groups": [["database_url"], ["missing"]],
                "required_tools": ["k8s_get_deployment", "k8s_get_pod_logs"],
                "expected_affected_any": ["payment"],
                "expect_knowledge": True,
                "expect_change_correlation": True,
                "required_change_tools": ["github_compare_commits"],
                "expected_change_signal_groups": [["database_url"], ["42"]],
            }
        )
        report = IncidentReport.model_validate(
            {
                "namespace": "opspilot-demo",
                "status": "incident",
                "affected_resources": ["deployment/payment"],
                "summary": "payment failing",
                "root_cause": "DATABASE_URL is missing from payment configuration",
                "confidence": "high",
                "evidence": [],
                "timeline": [{"timestamp": "2026-09-08T10:00:00Z", "event": "failure"}],
                "remediation": [],
                "follow_up_checks": [],
                "change_correlation": {
                    "repository": "opspilot-demo/opspilot-demo-services",
                    "current_revision": "aaaa",
                    "previous_revision": "1111",
                    "commit_sha": "aaaa",
                    "pull_request_number": 42,
                    "summary": "Removed DATABASE_URL from payment deployment",
                    "causal_link": "The deployed change removed the exact configuration required at startup.",
                },
                "tools_used": [
                    "k8s_get_deployment", "k8s_get_pod_logs", "search_knowledge",
                    "github_compare_commits"
                ],
                "assessment": {
                    "evidence_score": 100,
                    "confidence_score": 100,
                    "confidence": "high",
                    "model_confidence": "high",
                    "live_source_count": 2,
                    "knowledge_used": True,
                    "change_intelligence_used": True,
                    "corroborated": True,
                    "reasons": [],
                },
                "metrics": {
                    "investigation_id": "inv-test",
                    "started_at": "2026-09-08T10:00:00Z",
                    "completed_at": "2026-09-08T10:00:01Z",
                    "elapsed_ms": 1000,
                    "model_requests": 2,
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "total_tokens": 150,
                    "tool_call_count": 4,
                    "unique_tool_count": 4,
                },
            }
        )
        result = score_report(case, report)
        self.assertTrue(result.passed)
        self.assertEqual(result.breakdown.change_correlation, 15.0)
        self.assertEqual(result.score, 100.0)


if __name__ == "__main__":
    unittest.main()
