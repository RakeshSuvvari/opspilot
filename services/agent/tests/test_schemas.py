import unittest

from opspilot_agent.schemas import Confidence, IncidentReport, IncidentStatus


class SchemaTests(unittest.TestCase):
    def test_incident_report_validates(self):
        report = IncidentReport.model_validate(
            {
                "namespace": "opspilot-demo",
                "status": "incident",
                "affected_resources": ["deployment/payment"],
                "summary": "Payment is failing to start.",
                "root_cause": "Required configuration is missing.",
                "confidence": "high",
                "evidence": [],
                "timeline": [],
                "remediation": ["Restore the required deployment configuration."],
                "follow_up_checks": ["Verify the replacement pod becomes Ready."],
                "tools_used": ["k8s_list_pods", "k8s_get_deployment"],
                "assessment": {
                    "evidence_score": 75,
                    "confidence_score": 75,
                    "confidence": "high",
                    "model_confidence": "high",
                    "live_source_count": 2,
                    "knowledge_used": False,
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
                    "tool_call_count": 2,
                    "unique_tool_count": 2,
                },
            }
        )
        self.assertEqual(report.status, IncidentStatus.INCIDENT)
        self.assertEqual(report.confidence, Confidence.HIGH)


if __name__ == "__main__":
    unittest.main()
