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
    timestamp: str = Field(description="Timestamp derived from live Kubernetes tool output.")
    event: str = Field(description="Deterministic incident event derived from tool output.")


class ChangeCorrelation(BaseModel):
    repository: str | None = None
    current_revision: str | None = None
    previous_revision: str | None = None
    commit_sha: str | None = None
    pull_request_number: int | None = None
    summary: str
    causal_link: str


class ApprovalRequest(BaseModel):
    call_id: str | None = None
    tool_name: str
    arguments: dict[str, object]
    risk: str
    reason: str


class RemediationAction(BaseModel):
    call_id: str | None = None
    tool_name: str
    resource: str
    arguments: dict[str, object]
    approved: bool
    status: str
    result: object | None = None


class AgentIncidentReport(BaseModel):
    """Structured model output before OpsPilot's deterministic trust layer is applied."""

    namespace: str
    status: IncidentStatus
    affected_resources: list[str]
    summary: str
    root_cause: str
    confidence: Confidence
    evidence: list[EvidenceItem]
    remediation: list[str]
    follow_up_checks: list[str]
    change_correlation: ChangeCorrelation | None = None


class EvidenceAssessment(BaseModel):
    evidence_score: int = Field(ge=0, le=100)
    confidence_score: int = Field(ge=0, le=100)
    confidence: Confidence
    model_confidence: Confidence
    live_source_count: int = Field(ge=0)
    knowledge_used: bool
    change_intelligence_used: bool
    corroborated: bool
    reasons: list[str]


class RunMetrics(BaseModel):
    investigation_id: str
    started_at: str
    completed_at: str
    elapsed_ms: int = Field(ge=0)
    model_requests: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    tool_call_count: int = Field(ge=0)
    unique_tool_count: int = Field(ge=0)
    approval_requests: int = Field(default=0, ge=0)
    approved_actions: int = Field(default=0, ge=0)
    rejected_actions: int = Field(default=0, ge=0)


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
    change_correlation: ChangeCorrelation | None = None
    tools_used: list[str]
    assessment: EvidenceAssessment
    metrics: RunMetrics
    remediation_actions: list[RemediationAction] = Field(default_factory=list)


class InvestigationRequest(BaseModel):
    query: str = Field(min_length=3)
    namespace: str | None = None
