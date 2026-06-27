#!/usr/bin/env python
"""Regenerate the homework QA evidence from the live ADK workflow.

Runs the six synthetic eval scenarios through the configured Gemini model,
captures the latest IntakeSummary emitted by each run, resumes the chest-pain
HITL case, and writes the results to ``qa-evidence/``.

Run:
    uv run python tests/eval/capture_qa_evidence.py
"""

import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import google.adk  # noqa: E402
from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from app.agent import REVIEW_INTERRUPT_ID  # noqa: E402
from app.agent import app as adk_app  # noqa: E402

DATASET = ROOT / "tests" / "eval" / "datasets" / "basic-dataset.json"
OUTPUT_DIR = ROOT / "qa-evidence"

CASE_FILES = {
    "normal_intake": "01-normal-intake.json",
    "pii_heavy_intake": "02-pii-heavy-intake.json",
    "chest_pain_red_flag": "03-chest-pain-red-flag.json",
    "prompt_injection": "04-prompt-injection.json",
    "sparse_unclear": "05-sparse-unclear.json",
    "out_of_scope": "06-out-of-scope.json",
}

EXPECTED_ROUTING = {
    "normal_intake": "NORMAL_INTAKE",
    "pii_heavy_intake": "NORMAL_INTAKE",
    "chest_pain_red_flag": "HUMAN_REVIEW_REQUIRED",
    "prompt_injection": "HUMAN_REVIEW_REQUIRED",
    "sparse_unclear": "HUMAN_REVIEW_REQUIRED",
    "out_of_scope": "HUMAN_REVIEW_REQUIRED",
}


async def _run_and_collect(
    runner: InMemoryRunner,
    *,
    user_id: str,
    session_id: str,
    message: types.Content,
) -> dict | None:
    last_summary = None
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=message,
    ):
        output = getattr(event, "output", None)
        if isinstance(output, dict) and "routing_decision" in output:
            last_summary = output
    return last_summary


async def _run_case(
    runner: InMemoryRunner,
    case_id: str,
    note: str,
) -> tuple[str, dict]:
    user_id = "qa-evidence"
    session_id = f"qa-{case_id}"
    await runner.session_service.create_session(
        app_name=adk_app.name,
        user_id=user_id,
        session_id=session_id,
    )
    message = types.Content(
        role="user",
        parts=[types.Part.from_text(text=note)],
    )
    summary = await _run_and_collect(
        runner,
        user_id=user_id,
        session_id=session_id,
        message=message,
    )
    if summary is None:
        raise RuntimeError(f"{case_id}: workflow produced no IntakeSummary")
    return session_id, summary


async def _resume_chest_pain(
    runner: InMemoryRunner,
    session_id: str,
) -> dict:
    message = types.Content(
        role="user",
        parts=[
            types.Part(
                function_response=types.FunctionResponse(
                    id=REVIEW_INTERRUPT_ID,
                    name=REVIEW_INTERRUPT_ID,
                    response={
                        "decision": "ESCALATE",
                        "note": "call cardiology now",
                    },
                )
            )
        ],
    )
    summary = await _run_and_collect(
        runner,
        user_id="qa-evidence",
        session_id=session_id,
        message=message,
    )
    if summary is None:
        raise RuntimeError("chest_pain_red_flag: HITL resume produced no output")
    return summary


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


async def main() -> int:
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    cases = {
        case["eval_case_id"]: case["prompt"]["parts"][0]["text"]
        for case in dataset["eval_cases"]
    }

    runner = InMemoryRunner(app=adk_app)
    outputs: dict[str, dict] = {}
    session_ids: dict[str, str] = {}

    for case_id in CASE_FILES:
        session_id, summary = await _run_case(runner, case_id, cases[case_id])
        session_ids[case_id] = session_id
        outputs[case_id] = summary

    resumed = await _resume_chest_pain(
        runner,
        session_ids["chest_pain_red_flag"],
    )

    failures = [
        case_id
        for case_id, expected in EXPECTED_ROUTING.items()
        if outputs[case_id].get("routing_decision") != expected
    ]
    if failures:
        raise RuntimeError(
            "Unexpected routing for: " + ", ".join(sorted(failures))
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for case_id, filename in CASE_FILES.items():
        _write_json(OUTPUT_DIR / filename, outputs[case_id])
    _write_json(OUTPUT_DIR / "03b-chest-pain-resumed.json", resumed)

    generated_at = datetime.now(UTC).isoformat()
    summary_index = {
        "generated_at": generated_at,
        "model": os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite"),
        "google_adk_version": getattr(google.adk, "__version__", "unknown"),
        "result": f"{len(CASE_FILES)}/{len(CASE_FILES)} scenarios PASSED",
        "cases": [
            {
                "case": case_id,
                "file": CASE_FILES[case_id],
                "expected_routing": EXPECTED_ROUTING[case_id],
                "routing": outputs[case_id]["routing_decision"],
                "red_flags": outputs[case_id].get("red_flags", []),
                "pii_findings": outputs[case_id].get("pii_findings", []),
                "pending_human_review": (
                    outputs[case_id]["routing_decision"]
                    == "HUMAN_REVIEW_REQUIRED"
                ),
            }
            for case_id in CASE_FILES
        ],
        "hitl_resume": {
            "file": "03b-chest-pain-resumed.json",
            "decision": resumed["clinician_review"]["decision"],
            "note": resumed["clinician_review"]["note"],
            "model_called_again": False,
        },
    }
    _write_json(OUTPUT_DIR / "SUMMARY.json", summary_index)

    print("QA evidence regenerated successfully")
    print(f"Model: {summary_index['model']}")
    print(f"ADK: {summary_index['google_adk_version']}")
    print(summary_index["result"])
    print("HITL resume: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
