import unittest

from opspilot_agent.assessment import assess_evidence
from opspilot_agent.schemas import AgentIncidentReport, Confidence


class AssessmentTests(unittest.TestCase):
    def _report(self):
        return AgentIncidentReport.model_validate(
            {
                "namespace": "opspilot-demo",
                "status": "incident",
                "affected_resources": ["deployment/payment"],
                "summary": "Payment fails.",
                "root_cause": "DATABASE_URL is missing.",
                "confidence": "high",
                "evidence": [],
                "remediation": [],
                "follow_up_checks": [],
            }
        )

    def test_high_confidence_requires_corroborated_live_evidence(self):
        assessment = assess_evidence(
            self._report(),
            [
                "k8s_list_pods",
                "k8s_get_pod",
                "k8s_get_pod_logs",
                "k8s_get_events",
                "k8s_get_deployment",
                "search_knowledge",
            ],
        )
        self.assertEqual(assessment.confidence, Confidence.HIGH)
        self.assertTrue(assessment.corroborated)
        self.assertTrue(assessment.knowledge_used)
        self.assertFalse(assessment.change_intelligence_used)
        self.assertEqual(assessment.evidence_score, 100)

    def test_github_tools_are_recorded_as_change_intelligence(self):
        assessment = assess_evidence(
            self._report(),
            ["k8s_list_pods", "k8s_get_deployment", "k8s_get_pod_logs", "github_compare_commits"],
        )
        self.assertTrue(assessment.change_intelligence_used)
        self.assertEqual(assessment.confidence, Confidence.HIGH)

    def test_single_live_source_caps_confidence(self):
        assessment = assess_evidence(self._report(), ["k8s_list_pods"])
        self.assertEqual(assessment.confidence, Confidence.LOW)
        self.assertFalse(assessment.corroborated)
        self.assertLess(assessment.confidence_score, 50)


if __name__ == "__main__":
    unittest.main()
