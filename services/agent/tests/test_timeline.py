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

    def test_includes_github_change_events(self):
        records = [
            ToolRecord(
                name="github_get_commit",
                call_id="g1",
                arguments={"sha": "aaaa"},
                output={
                    "sha": "aaaaaaaaaaaaaaaa",
                    "message": "Remove DATABASE_URL",
                    "authored_at": "2026-09-08T09:00:00Z",
                },
            ),
            ToolRecord(
                name="github_get_pull_request",
                call_id="g2",
                arguments={"number": 42},
                output={
                    "number": 42,
                    "title": "Clean up payment config",
                    "merged_at": "2026-09-08T09:05:00Z",
                },
            ),
        ]
        timeline = build_timeline(records)
        self.assertEqual(len(timeline), 2)
        self.assertIn("Source commit", timeline[0].event)
        self.assertIn("Pull request #42", timeline[1].event)


    def test_includes_human_approved_remediation_events(self):
        records = [
            ToolRecord(
                name="k8s_rollback_deployment",
                call_id="call-rb",
                arguments={"deployment_name": "payment"},
                output={
                    "deployment": "payment",
                    "from_revision": 2,
                    "to_revision": 1,
                    "rolled_back_at": "2026-09-09T10:05:00Z",
                },
            )
        ]
        timeline = build_timeline(records)
        self.assertEqual(len(timeline), 1)
        self.assertIn("Human-approved remediation rolled back Deployment payment", timeline[0].event)


if __name__ == "__main__":
    unittest.main()
