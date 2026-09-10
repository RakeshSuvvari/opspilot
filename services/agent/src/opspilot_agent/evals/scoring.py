from __future__ import annotations

from .models import EvaluationBreakdown, EvaluationCase, EvaluationResult
from opspilot_agent.schemas import Confidence, IncidentReport


def _contains_any(text: str, signals: list[str]) -> bool:
    lower = text.lower()
    return any(signal.lower() in lower for signal in signals)


def score_report(case: EvaluationCase, report: IncidentReport) -> EvaluationResult:
    status_score = 15.0 if report.status == case.expected_status else 0.0

    root_max = 30.0 if case.expect_change_correlation else 40.0
    tools_max = 15.0 if case.expect_change_correlation else 20.0

    matched_groups = [group for group in case.root_cause_signal_groups if _contains_any(report.root_cause, group)]
    group_count = max(1, len(case.root_cause_signal_groups))
    root_score = root_max * len(matched_groups) / group_count
    missing_groups = [group for group in case.root_cause_signal_groups if group not in matched_groups]

    actual_tools = set(report.tools_used)
    required = set(case.required_tools)
    missing_tools = sorted(required - actual_tools)
    tools_score = tools_max if not required else tools_max * len(required & actual_tools) / len(required)

    affected_text = " ".join(report.affected_resources).lower()
    affected_score = 10.0 if (
        not case.expected_affected_any
        or any(signal.lower() in affected_text for signal in case.expected_affected_any)
    ) else 0.0

    confidence_score = 5.0 if report.confidence == Confidence.HIGH else (2.5 if report.confidence == Confidence.MEDIUM else 0.0)

    knowledge_used = "search_knowledge" in actual_tools
    knowledge_score = 5.0 if case.expect_knowledge is None or knowledge_used == case.expect_knowledge else 0.0
    timeline_score = 5.0 if len(report.timeline) >= case.minimum_timeline_events else 0.0

    change_score = 0.0
    missing_change_groups: list[list[str]] = []
    missing_change_tools: list[str] = []
    if case.expect_change_correlation:
        correlation = report.change_correlation
        if correlation is not None:
            change_score += 5.0
            change_text = " ".join(
                part for part in [
                    correlation.repository or "",
                    correlation.current_revision or "",
                    correlation.previous_revision or "",
                    correlation.commit_sha or "",
                    str(correlation.pull_request_number or ""),
                    correlation.summary,
                    correlation.causal_link,
                ] if part
            )
            matched_change = [
                group for group in case.expected_change_signal_groups if _contains_any(change_text, group)
            ]
            change_group_count = max(1, len(case.expected_change_signal_groups))
            if case.expected_change_signal_groups:
                change_score += 5.0 * len(matched_change) / change_group_count
            else:
                change_score += 5.0
            missing_change_groups = [group for group in case.expected_change_signal_groups if group not in matched_change]
        else:
            missing_change_groups = case.expected_change_signal_groups

        required_change = set(case.required_change_tools)
        missing_change_tools = sorted(required_change - actual_tools)
        if not required_change:
            change_score += 5.0
        else:
            change_score += 5.0 * len(required_change & actual_tools) / len(required_change)

    breakdown = EvaluationBreakdown(
        status=status_score,
        root_cause=root_score,
        tools=tools_score,
        affected_resource=affected_score,
        confidence=confidence_score,
        knowledge=knowledge_score,
        timeline=timeline_score,
        change_correlation=change_score,
    )
    score = round(sum(breakdown.model_dump().values()), 2)

    return EvaluationResult(
        case_id=case.id,
        score=score,
        passed=score >= case.pass_score,
        breakdown=breakdown,
        missing_root_cause_groups=missing_groups,
        missing_tools=missing_tools,
        missing_change_groups=missing_change_groups,
        missing_change_tools=missing_change_tools,
        report=report,
    )
