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
            }
        )
        self.assertEqual(report.status, IncidentStatus.INCIDENT)
        self.assertEqual(report.confidence, Confidence.HIGH)


if __name__ == "__main__":
    unittest.main()
