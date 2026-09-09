from __future__ import annotations

from datetime import datetime
from typing import Any

from .observability import ToolRecord
from .schemas import TimelineEvent


def _timestamp_key(timestamp: str) -> tuple[int, datetime | str]:
    value = timestamp.strip()
    try:
        return (0, datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return (1, value)


def _append(events: list[TimelineEvent], timestamp: Any, event: str) -> None:
    if not isinstance(timestamp, str) or not timestamp.strip():
        return
    events.append(TimelineEvent(timestamp=timestamp.strip(), event=event.strip()))


def _resource(kind: str | None, name: str | None) -> str:
    if kind and name:
        return f"{kind}/{name}"
    return name or kind or "Kubernetes object"


def _pod_timeline(output: dict[str, Any], events: list[TimelineEvent]) -> None:
    pod_name = output.get("name") or "pod"
    _append(events, output.get("start_time"), f"Pod {pod_name} started.")

    for condition in output.get("conditions") or []:
        if not isinstance(condition, dict):
            continue
        condition_type = condition.get("type", "condition")
        status = condition.get("status", "unknown")
        reason = condition.get("reason")
        suffix = f" ({reason})" if reason else ""
        _append(events, condition.get("last_transition_time"), f"Pod {pod_name} condition {condition_type} became {status}{suffix}.")

    containers = output.get("container_details") or output.get("containers") or []
    for container in containers:
        if not isinstance(container, dict):
            continue
        name = container.get("name", "container")
        _append(events, container.get("started_at"), f"Container {pod_name}/{name} started.")
        reason = container.get("last_termination_reason") or container.get("reason") or "terminated"
        exit_code = container.get("last_exit_code")
        exit_suffix = f" with exit code {exit_code}" if exit_code not in (None, 0) else ""
        _append(events, container.get("last_finished_at"), f"Container {pod_name}/{name} last terminated as {reason}{exit_suffix}.")
        _append(events, container.get("finished_at"), f"Container {pod_name}/{name} terminated as {reason}{exit_suffix}.")


def _event_timeline(output: dict[str, Any], events: list[TimelineEvent]) -> None:
    for item in output.get("events") or []:
        if not isinstance(item, dict):
            continue
        resource = _resource(item.get("object_kind"), item.get("object_name"))
        reason = item.get("reason", "Kubernetes event")
        message = item.get("message", "")
        count = item.get("count", 1)
        description = f"{resource}: {reason} — {message}".strip(" —")
        first = item.get("first_timestamp")
        last = item.get("last_timestamp")
        _append(events, first, f"First observed {description}.")
        if last and last != first:
            suffix = f" (count={count})" if isinstance(count, int) and count > 1 else ""
            _append(events, last, f"Last observed {description}{suffix}.")


def _deployment_timeline(output: dict[str, Any], events: list[TimelineEvent]) -> None:
    name = output.get("name") or "deployment"
    for condition in output.get("conditions") or []:
        if not isinstance(condition, dict):
            continue
        condition_type = condition.get("type", "condition")
        status = condition.get("status", "unknown")
        reason = condition.get("reason")
        suffix = f" ({reason})" if reason else ""
        _append(events, condition.get("last_transition_time"), f"Deployment {name} condition {condition_type} became {status}{suffix}.")


def _commit_timeline(output: dict[str, Any], events: list[TimelineEvent]) -> None:
    sha = str(output.get("sha") or "")

    message_text = str(output.get("message") or "").strip()
    message = message_text.splitlines()[0] if message_text else "(no commit message)"

    _append(
        events,
        output.get("authored_at"),
        f"Source commit {sha[:12]} authored: {message}.",
    )

def _compare_timeline(output: dict[str, Any], events: list[TimelineEvent]) -> None:
    for commit in output.get("commits") or []:
        if isinstance(commit, dict):
            _commit_timeline(commit, events)


def _pull_request_timeline(output: dict[str, Any], events: list[TimelineEvent]) -> None:
    number = output.get("number")
    title = output.get("title", "")
    if number:
        _append(events, output.get("merged_at"), f"Pull request #{number} merged: {title}.")


def _remediation_timeline(name: str, output: dict[str, Any], events: list[TimelineEvent]) -> None:
    deployment = output.get("deployment", "deployment")
    if name == "k8s_restart_deployment":
        _append(events, output.get("restarted_at"), f"Human-approved remediation restarted Deployment {deployment}.")
    elif name == "k8s_scale_deployment":
        _append(
            events,
            output.get("scaled_at"),
            f"Human-approved remediation scaled Deployment {deployment} from {output.get('previous_replicas')} to {output.get('replicas')} replicas.",
        )
    elif name == "k8s_rollback_deployment":
        _append(
            events,
            output.get("rolled_back_at"),
            f"Human-approved remediation rolled back Deployment {deployment} from revision {output.get('from_revision')} to {output.get('to_revision')}.",
        )


def build_timeline(records: list[ToolRecord], max_events: int = 20) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    for record in records:
        output = record.output
        if not isinstance(output, dict):
            continue
        if record.name == "k8s_get_pod":
            _pod_timeline(output, events)
        elif record.name == "k8s_list_pods":
            for pod in output.get("pods") or []:
                if isinstance(pod, dict):
                    _pod_timeline(pod, events)
        elif record.name == "k8s_get_events":
            _event_timeline(output, events)
        elif record.name == "k8s_get_deployment":
            _deployment_timeline(output, events)
        elif record.name == "github_get_commit":
            _commit_timeline(output, events)
        elif record.name == "github_compare_commits":
            _compare_timeline(output, events)
        elif record.name == "github_get_pull_request":
            _pull_request_timeline(output, events)
        elif record.name in {"k8s_restart_deployment", "k8s_scale_deployment", "k8s_rollback_deployment"}:
            _remediation_timeline(record.name, output, events)

    deduplicated: dict[tuple[str, str], TimelineEvent] = {}
    for event in events:
        deduplicated[(event.timestamp, event.event)] = event
    ordered = sorted(deduplicated.values(), key=lambda item: _timestamp_key(item.timestamp))
    return ordered[-max_events:]
