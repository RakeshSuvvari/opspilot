from __future__ import annotations

from pydantic import BaseModel, Field

from opspilot_agent.schemas import IncidentReport, IncidentStatus


class EvaluationCase(BaseModel):
    id: str
    query: str
    expected_status: IncidentStatus = IncidentStatus.INCIDENT
    root_cause_signal_groups: list[list[str]]
    required_tools: list[str]
    expected_affected_any: list[str] = Field(default_factory=list)
    expect_knowledge: bool = True
    minimum_timeline_events: int = 1
    pass_score: int = 80
    expect_change_correlation: bool = False
    required_change_tools: list[str] = Field(default_factory=list)
    expected_change_signal_groups: list[list[str]] = Field(default_factory=list)


class EvaluationBreakdown(BaseModel):
    status: float
    root_cause: float
    tools: float
    affected_resource: float
    confidence: float
    knowledge: float
    timeline: float
    change_correlation: float = 0.0


class EvaluationResult(BaseModel):
    case_id: str
    score: float
    passed: bool
    breakdown: EvaluationBreakdown
    missing_root_cause_groups: list[list[str]]
    missing_tools: list[str]
    missing_change_groups: list[list[str]] = Field(default_factory=list)
    missing_change_tools: list[str] = Field(default_factory=list)
    report: IncidentReport
