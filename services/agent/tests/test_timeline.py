import unittest

from opspilot_agent.observability import ToolRecord
from opspilot_agent.timeline import build_timeline


class TimelineTests(unittest.TestCase):
    def test_builds_sorted_timeline_from_live_outputs(self):
        records = [
            ToolRecord(
                name="k8s_get_events",
                call_id="2",
                arguments={},
                output={
                    "events": [
                        {
                            "object_kind": "Pod",
                            "object_name": "payment-abc",
                            "reason": "BackOff",
                            "message": "restarting failed container",
                            "count": 3,
                            "first_timestamp": "2026-09-08T10:00:03Z",
                            "last_timestamp": "2026-09-08T10:00:05Z",
                        }
                    ]
                },
            ),
            ToolRecord(
                name="k8s_get_pod",
                call_id="1",
                arguments={},
                output={
                    "name": "payment-abc",
                    "start_time": "2026-09-08T10:00:01Z",
                    "conditions": [],
                    "container_details": [],
                },
            ),
        ]
        timeline = build_timeline(records)
        self.assertEqual(timeline[0].timestamp, "2026-09-08T10:00:01Z")
        self.assertEqual(timeline[-1].timestamp, "2026-09-08T10:00:05Z")
        self.assertEqual(len(timeline), 3)


if __name__ == "__main__":
    unittest.main()
