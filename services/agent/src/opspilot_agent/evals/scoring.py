from __future__ import annotations

from .models import EvaluationBreakdown, EvaluationCase, EvaluationResult
from opspilot_agent.schemas import Confidence, IncidentReport


def _contains_any(text: str, signals: list[str]) -> bool:
    lower = text.lower()
    return any(signal.lower() in lower for signal in signals)


def score_report(case: EvaluationCase, report: IncidentReport) -> EvaluationResult:
    status_score = 15.0 if report.status == case.expected_status else 0.0

    matched_groups = [
        group for group in case.root_cause_signal_groups if _contains_any(report.root_cause, group)
    ]
    group_count = max(1, len(case.root_cause_signal_groups))
    root_score = 40.0 * len(matched_groups) / group_count
    missing_groups = [group for group in case.root_cause_signal_groups if group not in matched_groups]

    actual_tools = set(report.tools_used)
    required = set(case.required_tools)
    missing_tools = sorted(required - actual_tools)
    tools_score = 20.0 if not required else 20.0 * len(required & actual_tools) / len(required)

    affected_text = " ".join(report.affected_resources).lower()
    affected_score = 10.0 if (
        not case.expected_affected_any
        or any(signal.lower() in affected_text for signal in case.expected_affected_any)
    ) else 0.0

    confidence_score = 5.0 if report.confidence == Confidence.HIGH else (
        2.5 if report.confidence == Confidence.MEDIUM else 0.0
    )

    knowledge_used = "search_knowledge" in actual_tools
    knowledge_score = 5.0 if knowledge_used == case.expect_knowledge else 0.0

    timeline_score = 5.0 if len(report.timeline) >= case.minimum_timeline_events else 0.0

    breakdown = EvaluationBreakdown(
        status=status_score,
        root_cause=root_score,
        tools=tools_score,
        affected_resource=affected_score,
        confidence=confidence_score,
        knowledge=knowledge_score,
        timeline=timeline_score,
    )
    score = round(sum(breakdown.model_dump().values()), 2)

    return EvaluationResult(
        case_id=case.id,
        score=score,
        passed=score >= case.pass_score,
        breakdown=breakdown,
        missing_root_cause_groups=missing_groups,
        missing_tools=missing_tools,
        report=report,
    )
