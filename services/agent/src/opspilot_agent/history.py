from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .observability import ToolRecord
from .schemas import (
    IncidentReport,
    InvestigationHistoryDetail,
    InvestigationHistoryItem,
)


def _normalize_history_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    completed_at = normalized.get("completed_at")
    if completed_at is not None and hasattr(completed_at, "isoformat"):
        normalized["completed_at"] = completed_at.isoformat().replace("+00:00", "Z")
    return normalized


@dataclass(frozen=True)
class HistoryStore:
    database_url: str

    async def save_investigation(
        self,
        report: IncidentReport,
        *,
        query: str,
        run_mode: str,
        tool_records: list[ToolRecord],
        job_id: str | None = None,
    ) -> None:
        payload = report.model_dump(mode="json")
        conn = await psycopg.AsyncConnection.connect(self.database_url, connect_timeout=3)
        try:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO operations.investigations (
                        investigation_id,
                        job_id,
                        query,
                        namespace,
                        run_mode,
                        status,
                        confidence,
                        summary,
                        root_cause,
                        evidence_score,
                        confidence_score,
                        started_at,
                        completed_at,
                        elapsed_ms,
                        total_tokens,
                        tool_call_count,
                        report
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (investigation_id) DO UPDATE SET
                        job_id = EXCLUDED.job_id,
                        query = EXCLUDED.query,
                        namespace = EXCLUDED.namespace,
                        run_mode = EXCLUDED.run_mode,
                        status = EXCLUDED.status,
                        confidence = EXCLUDED.confidence,
                        summary = EXCLUDED.summary,
                        root_cause = EXCLUDED.root_cause,
                        evidence_score = EXCLUDED.evidence_score,
                        confidence_score = EXCLUDED.confidence_score,
                        started_at = EXCLUDED.started_at,
                        completed_at = EXCLUDED.completed_at,
                        elapsed_ms = EXCLUDED.elapsed_ms,
                        total_tokens = EXCLUDED.total_tokens,
                        tool_call_count = EXCLUDED.tool_call_count,
                        report = EXCLUDED.report
                    """,
                    (
                        report.metrics.investigation_id,
                        job_id,
                        query,
                        report.namespace,
                        run_mode,
                        report.status.value,
                        report.confidence.value,
                        report.summary,
                        report.root_cause,
                        report.assessment.evidence_score,
                        report.assessment.confidence_score,
                        report.metrics.started_at,
                        report.metrics.completed_at,
                        report.metrics.elapsed_ms,
                        report.metrics.total_tokens,
                        report.metrics.tool_call_count,
                        Jsonb(payload),
                    ),
                )

                await conn.execute(
                    "DELETE FROM operations.tool_calls WHERE investigation_id = %s",
                    (report.metrics.investigation_id,),
                )
                if tool_records:
                    async with conn.cursor() as cur:
                        await cur.executemany(
                            """
                            INSERT INTO operations.tool_calls (
                                investigation_id, ordinal, tool_name, call_id, arguments
                            ) VALUES (%s, %s, %s, %s, %s)
                            """,
                            [
                                (
                                    report.metrics.investigation_id,
                                    ordinal,
                                    record.name,
                                    record.call_id,
                                    Jsonb(record.arguments),
                                )
                                for ordinal, record in enumerate(tool_records)
                            ],
                        )

                await conn.execute(
                    "DELETE FROM operations.remediation_actions WHERE investigation_id = %s",
                    (report.metrics.investigation_id,),
                )
                if report.remediation_actions:
                    async with conn.cursor() as cur:
                        await cur.executemany(
                            """
                            INSERT INTO operations.remediation_actions (
                                investigation_id,
                                ordinal,
                                tool_name,
                                resource,
                                approved,
                                status,
                                arguments,
                                result
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            [
                                (
                                    report.metrics.investigation_id,
                                    ordinal,
                                    action.tool_name,
                                    action.resource,
                                    action.approved,
                                    action.status,
                                    Jsonb(action.arguments),
                                    Jsonb(action.result) if action.result is not None else None,
                                )
                                for ordinal, action in enumerate(report.remediation_actions)
                            ],
                        )
        finally:
            await conn.close()

    async def list_investigations(self, *, limit: int = 25) -> list[InvestigationHistoryItem]:
        safe_limit = min(max(limit, 1), 100)
        conn = await psycopg.AsyncConnection.connect(self.database_url, row_factory=dict_row, connect_timeout=3)
        try:
            cursor = await conn.execute(
                """
                SELECT
                    investigation_id,
                    job_id,
                    query,
                    namespace,
                    run_mode,
                    status,
                    confidence,
                    summary,
                    root_cause,
                    evidence_score,
                    completed_at,
                    elapsed_ms,
                    total_tokens,
                    tool_call_count
                FROM operations.investigations
                ORDER BY completed_at DESC
                LIMIT %s
                """,
                (safe_limit,),
            )
            rows = await cursor.fetchall()
        finally:
            await conn.close()
        return [InvestigationHistoryItem.model_validate(_normalize_history_row(row)) for row in rows]

    async def get_investigation(self, investigation_id: str) -> InvestigationHistoryDetail | None:
        conn = await psycopg.AsyncConnection.connect(self.database_url, row_factory=dict_row, connect_timeout=3)
        try:
            cursor = await conn.execute(
                """
                SELECT
                    investigation_id,
                    job_id,
                    query,
                    namespace,
                    run_mode,
                    status,
                    confidence,
                    summary,
                    root_cause,
                    evidence_score,
                    completed_at,
                    elapsed_ms,
                    total_tokens,
                    tool_call_count,
                    report
                FROM operations.investigations
                WHERE investigation_id = %s
                """,
                (investigation_id,),
            )
            row: dict[str, Any] | None = await cursor.fetchone()
        finally:
            await conn.close()
        if row is None:
            return None
        return InvestigationHistoryDetail.model_validate(_normalize_history_row(row))

    async def ping(self) -> bool:
        try:
            conn = await psycopg.AsyncConnection.connect(self.database_url, connect_timeout=3)
            try:
                await conn.execute("SELECT 1 FROM operations.investigations LIMIT 1")
            finally:
                await conn.close()
            return True
        except psycopg.Error:
            return False
