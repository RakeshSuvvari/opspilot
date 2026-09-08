from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class IncidentStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    INCIDENT = "incident"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class Confidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EvidenceItem(BaseModel):
    source: str = Field(
        description="Evidence source, such as pod, logs, events, deployment, runbook, or historical incident."
    )
    resource: str = Field(
        description="Exact Kubernetes resource, component, or knowledge document that produced the evidence."
    )
    observation: str = Field(
        description="Concise factual observation returned by a diagnostic tool."
    )
    supports: str = Field(
        description="How this observation supports or weakens the root-cause hypothesis."
    )


class TimelineEvent(BaseModel):
    timestamp: str = Field(
        description="Timestamp from Kubernetes evidence, or 'unknown' if no timestamp exists."
    )
    event: str = Field(description="Concise incident event supported by collected evidence.")


class IncidentReport(BaseModel):
    namespace: str
    status: IncidentStatus
    affected_resources: list[str]
    summary: str
    root_cause: str
    confidence: Confidence
    evidence: list[EvidenceItem]
    timeline: list[TimelineEvent]
    remediation: list[str]
    follow_up_checks: list[str]
    tools_used: list[str]


class InvestigationRequest(BaseModel):
    query: str = Field(min_length=3)
    namespace: str | None = None
