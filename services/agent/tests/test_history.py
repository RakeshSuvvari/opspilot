import unittest
from datetime import datetime, timezone

from opspilot_agent.history import _normalize_history_row
from opspilot_agent.schemas import InvestigationHistoryItem


class HistoryTests(unittest.TestCase):
    def test_normalize_history_timestamp(self):
        row = {
            "investigation_id": "inv-1",
            "job_id": None,
            "query": "why is payment failing",
            "namespace": "opspilot-demo",
            "run_mode": "investigate",
            "status": "incident",
            "confidence": "high",
            "summary": "payment is failing",
            "root_cause": "missing config",
            "evidence_score": 95,
            "completed_at": datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc),
            "elapsed_ms": 1000,
            "total_tokens": 1200,
            "tool_call_count": 6,
        }

        normalized = _normalize_history_row(row)
        item = InvestigationHistoryItem.model_validate(normalized)

        self.assertEqual(item.completed_at, "2026-09-09T12:00:00Z")
        self.assertEqual(item.evidence_score, 95)


if __name__ == "__main__":
    unittest.main()
