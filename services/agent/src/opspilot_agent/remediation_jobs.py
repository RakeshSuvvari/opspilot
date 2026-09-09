from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from .runtime import IncidentAgentRuntime
from .schemas import (
    ApprovalRequest,
    IncidentReport,
    RemediationJob,
    RemediationJobStatus,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class _JobState:
    job_id: str
    query: str
    namespace: str
    status: RemediationJobStatus = RemediationJobStatus.QUEUED
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    pending_approval: ApprovalRequest | None = None
    report: IncidentReport | None = None
    error: str | None = None
    approval_future: asyncio.Future[bool] | None = None
    task: asyncio.Task[None] | None = None


class RemediationJobManager:
    """Runs remediation workflows while exposing approval pauses over HTTP.

    Phase 8 intentionally keeps jobs in memory. A production persistence layer can
    replace this manager later without changing the dashboard API contract.
    """

    def __init__(self, runtime: "IncidentAgentRuntime"):
        self.runtime = runtime
        self._jobs: dict[str, _JobState] = {}
        self._lock = asyncio.Lock()

    async def start(self, query: str, namespace: str) -> RemediationJob:
        job_id = f"rem-{uuid4().hex[:12]}"
        state = _JobState(job_id=job_id, query=query, namespace=namespace)
        async with self._lock:
            self._jobs[job_id] = state
            state.task = asyncio.create_task(self._run(state), name=f"opspilot-{job_id}")
        return self._snapshot(state)

    async def get(self, job_id: str) -> RemediationJob:
        async with self._lock:
            state = self._jobs.get(job_id)
            if state is None:
                raise KeyError(job_id)
            return self._snapshot(state)

    async def decide(
        self,
        job_id: str,
        *,
        approved: bool,
        call_id: str | None = None,
    ) -> RemediationJob:
        async with self._lock:
            state = self._jobs.get(job_id)
            if state is None:
                raise KeyError(job_id)
            if state.status != RemediationJobStatus.AWAITING_APPROVAL:
                raise ValueError("remediation job is not awaiting approval")
            if state.pending_approval is None or state.approval_future is None:
                raise ValueError("remediation job has no pending approval")
            if call_id and state.pending_approval.call_id and call_id != state.pending_approval.call_id:
                raise ValueError("approval call_id does not match the pending action")
            if state.approval_future.done():
                raise ValueError("approval decision was already submitted")

            state.approval_future.set_result(approved)
            state.updated_at = _utc_now()
            return self._snapshot(state)

    async def close(self) -> None:
        async with self._lock:
            tasks = [state.task for state in self._jobs.values() if state.task and not state.task.done()]
            for task in tasks:
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _run(self, state: _JobState) -> None:
        state.status = RemediationJobStatus.RUNNING
        state.updated_at = _utc_now()

        async def approval_handler(request: ApprovalRequest) -> bool:
            loop = asyncio.get_running_loop()
            future: asyncio.Future[bool] = loop.create_future()
            async with self._lock:
                state.pending_approval = request
                state.approval_future = future
                state.status = RemediationJobStatus.AWAITING_APPROVAL
                state.updated_at = _utc_now()

            approved = await future

            async with self._lock:
                state.pending_approval = None
                state.approval_future = None
                state.status = RemediationJobStatus.RUNNING
                state.updated_at = _utc_now()
            return approved

        try:
            report = await self.runtime.remediate(
                state.query,
                state.namespace,
                approval_handler,
            )
            async with self._lock:
                state.report = report
                state.status = RemediationJobStatus.COMPLETED
                state.updated_at = _utc_now()
        except asyncio.CancelledError:
            async with self._lock:
                state.status = RemediationJobStatus.CANCELLED
                state.updated_at = _utc_now()
            raise
        except Exception as exc:
            async with self._lock:
                state.error = f"{type(exc).__name__}: {exc}"
                state.status = RemediationJobStatus.FAILED
                state.updated_at = _utc_now()

    @staticmethod
    def _snapshot(state: _JobState) -> RemediationJob:
        return RemediationJob(
            job_id=state.job_id,
            status=state.status,
            query=state.query,
            namespace=state.namespace,
            created_at=state.created_at,
            updated_at=state.updated_at,
            pending_approval=state.pending_approval,
            report=state.report,
            error=state.error,
        )
