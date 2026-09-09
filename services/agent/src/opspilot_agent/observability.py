from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .schemas import IncidentReport


@dataclass(frozen=True)
class ToolRecord:
    name: str
    call_id: str | None
    arguments: dict[str, Any]
    output: Any | None


def _parse_json(value: Any) -> Any:
    if isinstance(value, (dict, list, int, float, bool)) or value is None:
        return value
    if not isinstance(value, str):
        return value

    text = value.strip()
    if not text:
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def _tool_arguments(item: Any) -> dict[str, Any]:
    raw = getattr(item, "raw_item", None)
    if isinstance(raw, dict):
        arguments = raw.get("arguments", {})
    else:
        arguments = getattr(raw, "arguments", {})

    parsed = _parse_json(arguments)
    return parsed if isinstance(parsed, dict) else {}


def extract_tool_records(new_items: Iterable[Any]) -> list[ToolRecord]:
    calls: list[tuple[str, str | None, dict[str, Any]]] = []
    outputs: dict[str, Any] = {}

    for item in new_items:
        item_type = getattr(item, "type", "")
        if item_type == "tool_call_item":
            name = getattr(item, "tool_name", None)
            if name:
                calls.append((name, getattr(item, "call_id", None), _tool_arguments(item)))
        elif item_type == "tool_call_output_item":
            call_id = getattr(item, "call_id", None)
            if call_id:
                outputs[call_id] = _parse_json(getattr(item, "output", None))

    return [
        ToolRecord(
            name=name,
            call_id=call_id,
            arguments=arguments,
            output=outputs.get(call_id) if call_id else None,
        )
        for name, call_id, arguments in calls
    ]


def ordered_unique_tool_names(records: Iterable[ToolRecord]) -> list[str]:
    seen: set[str] = set()
    names: list[str] = []
    for record in records:
        if record.name in seen:
            continue
        seen.add(record.name)
        names.append(record.name)
    return names


def save_run_artifact(
    directory: str,
    report: IncidentReport,
    query: str,
    model: str,
    tool_records: list[ToolRecord],
) -> Path:
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    target = path / f"{report.metrics.investigation_id}.json"

    payload = {
        "query": query,
        "model": model,
        "report": report.model_dump(mode="json"),
        "tool_calls": [
            {
                "name": record.name,
                "call_id": record.call_id,
                "arguments": record.arguments,
            }
            for record in tool_records
        ],
    }
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return target
