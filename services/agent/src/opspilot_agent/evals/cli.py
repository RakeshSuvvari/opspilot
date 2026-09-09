from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from opspilot_agent.config import Settings
from opspilot_agent.runtime import IncidentAgentRuntime

from .models import EvaluationCase
from .scoring import score_report


def load_cases(path: str) -> list[EvaluationCase]:
    cases: list[EvaluationCase] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            cases.append(EvaluationCase.model_validate_json(line))
    return cases


async def _evaluate(args: argparse.Namespace) -> int:
    cases = load_cases(args.cases)
    selected = next((case for case in cases if case.id == args.case), None)
    if selected is None:
        raise ValueError(f"Unknown evaluation case: {args.case}")

    settings = Settings.from_env()
    async with IncidentAgentRuntime(settings) as runtime:
        report = await runtime.investigate(selected.query, args.namespace)

    result = score_report(selected, report)

    artifact_dir = Path(os.getenv("OPSPILOT_EVAL_ARTIFACT_DIR", ".opspilot/evals"))
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / (
        f"{selected.id}-{report.metrics.investigation_id}.json"
    )
    artifact_path.write_text(
        json.dumps(result.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )

    if args.json:
        print(json.dumps(result.model_dump(mode="json"), indent=2))
    else:
        print(f"OpsPilot Evaluation {result.case_id}")
        print("=" * 72)
        print(f"Score:   {result.score:.2f}/100")
        print(f"Passed:  {'yes' if result.passed else 'no'}")
        print("\nBreakdown")
        for name, score in result.breakdown.model_dump().items():
            print(f"- {name}: {score:.2f}")
        if result.missing_tools:
            print(f"\nMissing tools: {', '.join(result.missing_tools)}")
        if result.missing_root_cause_groups:
            print("\nMissing root-cause signal groups:")
            for group in result.missing_root_cause_groups:
                print(f"- {' | '.join(group)}")
        if result.missing_change_tools:
            print(f"\nMissing change tools: {', '.join(result.missing_change_tools)}")
        if result.missing_change_groups:
            print("\nMissing change-correlation signal groups:")
            for group in result.missing_change_groups:
                print(f"- {' | '.join(group)}")
        print(f"\nRoot cause: {result.report.root_cause}")
        print(f"Confidence: {result.report.confidence.value}")
        print(f"Tools: {', '.join(result.report.tools_used)}")
        print(f"Artifact: {artifact_path}")

    return 0 if result.passed else 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="opspilot-eval")
    parser.add_argument("--cases", default="evals/cases/incidents.jsonl")
    parser.add_argument("--case", required=True)
    parser.add_argument("--namespace", default="opspilot-demo")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> None:
    args = _parser().parse_args()
    try:
        exit_code = asyncio.run(_evaluate(args))
    except KeyboardInterrupt:
        exit_code = 130
    except Exception as exc:
        print(f"opspilot-eval: {exc}", file=sys.stderr)
        exit_code = 1
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
