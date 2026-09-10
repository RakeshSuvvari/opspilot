import asyncio
import unittest

from opspilot_agent.remediation_jobs import RemediationJobManager
from opspilot_agent.schemas import ApprovalRequest, RemediationJobStatus


class _FakeRuntime:
    async def remediate(self, query, namespace, approval_handler, *, job_id=None):
        approved = await approval_handler(
            ApprovalRequest(
                call_id="call-1",
                tool_name="k8s_rollback_deployment",
                arguments={"namespace": namespace, "deployment_name": "payment"},
                risk="high",
                reason="test approval",
            )
        )
        if not approved:
            raise RuntimeError("approval rejected in fake runtime")
        from opspilot_agent.schemas import IncidentReport

        return IncidentReport.model_validate(
            {
                "namespace": namespace,
                "status": "healthy",
                "affected_resources": ["deployment/payment"],
                "summary": "Recovered.",
                "root_cause": "Test.",
                "confidence": "high",
                "evidence": [],
                "timeline": [],
                "remediation": [],
                "follow_up_checks": [],
                "tools_used": ["k8s_rollback_deployment"],
                "assessment": {
                    "evidence_score": 100,
                    "confidence_score": 100,
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
                    "started_at": "2026-09-09T00:00:00Z",
                    "completed_at": "2026-09-09T00:00:01Z",
                    "elapsed_ms": 1000,
                    "model_requests": 1,
                    "input_tokens": 1,
                    "output_tokens": 1,
                    "total_tokens": 2,
                    "tool_call_count": 1,
                    "unique_tool_count": 1,
                    "approval_requests": 1,
                    "approved_actions": 1,
                    "rejected_actions": 0,
                },
                "remediation_actions": [],
            }
        )


class RemediationJobManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_job_pauses_and_resumes_after_approval(self):
        manager = RemediationJobManager(_FakeRuntime())
        job = await manager.start("fix payment", "opspilot-demo")

        for _ in range(50):
            job = await manager.get(job.job_id)
            if job.status == RemediationJobStatus.AWAITING_APPROVAL:
                break
            await asyncio.sleep(0.01)

        self.assertEqual(job.status, RemediationJobStatus.AWAITING_APPROVAL)
        self.assertIsNotNone(job.pending_approval)
        self.assertEqual(job.pending_approval.tool_name, "k8s_rollback_deployment")

        await manager.decide(job.job_id, approved=True, call_id="call-1")
        for _ in range(50):
            job = await manager.get(job.job_id)
            if job.status == RemediationJobStatus.COMPLETED:
                break
            await asyncio.sleep(0.01)

        self.assertEqual(job.status, RemediationJobStatus.COMPLETED)
        self.assertIsNotNone(job.report)
        await manager.close()


if __name__ == "__main__":
    unittest.main()
