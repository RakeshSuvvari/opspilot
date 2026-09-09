from __future__ import annotations

from .schemas import AgentIncidentReport, Confidence, EvidenceAssessment, IncidentStatus


TOOL_WEIGHTS = {
    "k8s_list_pods": 20,
    "k8s_get_pod": 20,
    "k8s_get_pod_logs": 20,
    "k8s_get_events": 15,
    "k8s_get_deployment": 20,
    "search_knowledge": 5,
}

LIVE_TOOLS = {
    "k8s_list_pods",
    "k8s_get_pod",
    "k8s_get_pod_logs",
    "k8s_get_events",
    "k8s_get_deployment",
}

DIRECT_DIAGNOSTIC_TOOLS = {
    "k8s_get_pod",
    "k8s_get_pod_logs",
    "k8s_get_deployment",
}


def _confidence_from_score(score: int) -> Confidence:
    if score >= 75:
        return Confidence.HIGH
    if score >= 50:
        return Confidence.MEDIUM
    return Confidence.LOW


def assess_evidence(
    report: AgentIncidentReport,
    actual_tools: list[str],
) -> EvidenceAssessment:
    unique_tools = set(actual_tools)
    live_tools = unique_tools & LIVE_TOOLS
    evidence_score = min(100, sum(TOOL_WEIGHTS.get(name, 0) for name in unique_tools))

    if len(live_tools) >= 2:
        evidence_score = min(100, evidence_score + 10)

    confidence_score = evidence_score
    reasons: list[str] = []
    corroborated = len(live_tools) >= 2

    if corroborated:
        reasons.append(f"Collected live evidence through {len(live_tools)} independent Kubernetes tools.")
    else:
        confidence_score = min(confidence_score, 49)
        reasons.append("Fewer than two independent live Kubernetes evidence sources were collected.")

    if report.status in {IncidentStatus.INCIDENT, IncidentStatus.DEGRADED}:
        if not (unique_tools & DIRECT_DIAGNOSTIC_TOOLS):
            confidence_score = min(confidence_score, 49)
            reasons.append("No direct pod, log, or deployment diagnostic was collected.")
        else:
            reasons.append("At least one direct pod/log/deployment diagnostic supports the investigation.")

    if report.status == IncidentStatus.INSUFFICIENT_EVIDENCE:
        confidence_score = min(confidence_score, 40)
        reasons.append("The agent explicitly reported insufficient evidence.")

    knowledge_used = "search_knowledge" in unique_tools
    if knowledge_used:
        reasons.append("RAG knowledge was used as supporting context, not as live cluster proof.")

    confidence = _confidence_from_score(confidence_score)
    return EvidenceAssessment(
        evidence_score=evidence_score,
        confidence_score=confidence_score,
        confidence=confidence,
        model_confidence=report.confidence,
        live_source_count=len(live_tools),
        knowledge_used=knowledge_used,
        corroborated=corroborated,
        reasons=reasons,
    )
