# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Ambient (event-driven) entrypoint for the Clinic Intake Summarizer.

A small FastAPI service that accepts Pub/Sub-style push messages and feeds each
intake note into the existing ADK 2.0 graph Workflow (screen -> extract -> route
-> human_review -> finalize). This is an alternative to the chat Playground
(`app/fast_api_app.py`), which is left untouched.

Design notes:
  * Local development uses Google AI Studio API key mode (`.env`); no GCP
    credentials are required and no cloud telemetry is configured (otel_to_cloud
    is effectively False — get_fast_api_app is not used here).
  * Standard Python logging only. The raw intake note (which may contain PII) is
    never logged; only the subscription name, message id, and routing decision.
  * Review cases (red flag / injection / insufficient info) pause at the
    RequestInput HITL node. The push response reports `pending_human_review`
    with a readable `session_id`; the clinician decision is NOT faked. Resume
    via POST /human-review/{session_id} or from the Playground.
"""

import base64
import binascii
import json
import logging

from fastapi import FastAPI, HTTPException
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel

from app.agent import (
    CLINICIAN_DECISIONS,
    REVIEW_INTERRUPT_ID,
)
from app.agent import (
    app as adk_app,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("clinic_intake.ambient")

# One runner per process so in-memory sessions persist across requests
# (needed so a paused review can be resumed by a later /human-review call).
_runner = InMemoryRunner(app=adk_app)

# Maps readable session_id -> user_id so the resume endpoint can locate sessions.
_SESSIONS: dict[str, str] = {}

app = FastAPI(
    title="clinic-intake-summarizer-ambient",
    description="Ambient Pub/Sub-style intake intake service for the Clinic "
    "Intake Summarizer agent.",
)


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested without the model)
# ---------------------------------------------------------------------------
class PubSubError(ValueError):
    """Raised when a Pub/Sub push payload is malformed."""


def normalize_subscription(subscription: str) -> str:
    """Turn a fully-qualified subscription path into a short readable name.

    ``projects/demo/subscriptions/clinic-intake-sub`` -> ``clinic-intake-sub``.
    """
    if not subscription:
        return "unknown-subscription"
    cleaned = subscription.strip().rstrip("/")
    if "subscriptions/" in cleaned:
        cleaned = cleaned.split("subscriptions/")[-1]
    else:
        cleaned = cleaned.rsplit("/", 1)[-1]
    return cleaned or "unknown-subscription"


def decode_pubsub_data(data_b64: str) -> str:
    """Base64-decode Pub/Sub message data into UTF-8 text."""
    try:
        return base64.b64decode(data_b64, validate=True).decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise PubSubError("message.data is not valid base64 UTF-8") from exc


def extract_note(decoded: str) -> str:
    """Extract the intake note from decoded data.

    If the decoded text is a JSON object with ``intake_note`` / ``note`` /
    ``text``, use that field; otherwise use the decoded text directly.
    """
    try:
        obj = json.loads(decoded)
    except (ValueError, TypeError):
        return decoded
    if isinstance(obj, dict):
        for key in ("intake_note", "note", "text"):
            value = obj.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return decoded


def build_ids(short_sub: str, message_id: str) -> tuple[str, str]:
    """Build a readable (user_id, session_id) from the short sub + message id."""
    mid = (message_id or "nomsgid").strip() or "nomsgid"
    return short_sub, f"{short_sub}-{mid}"


def parse_push_envelope(payload: dict) -> dict:
    """Parse a Pub/Sub push envelope into intake fields. Raises PubSubError."""
    if not isinstance(payload, dict):
        raise PubSubError("payload must be a JSON object")
    message = payload.get("message")
    if not isinstance(message, dict):
        raise PubSubError("missing 'message' object")
    data_b64 = message.get("data")
    if not data_b64 or not isinstance(data_b64, str):
        raise PubSubError("missing 'message.data'")

    note = extract_note(decode_pubsub_data(data_b64))
    if not note or not note.strip():
        raise PubSubError("no intake note found in message data")

    message_id = str(
        message.get("messageId") or message.get("message_id") or "nomsgid"
    )
    short_sub = normalize_subscription(str(payload.get("subscription", "")))
    user_id, session_id = build_ids(short_sub, message_id)
    return {
        "note": note,
        "short_sub": short_sub,
        "message_id": message_id,
        "user_id": user_id,
        "session_id": session_id,
    }


def parse_relaxed(payload: dict) -> dict:
    """Lenient parser for POST / local testing.

    Accepts either a full Pub/Sub envelope (has ``message``) or a plain body
    with ``intake_note`` / ``note`` / ``text``.
    """
    if isinstance(payload, dict) and "message" in payload:
        return parse_push_envelope(payload)
    if not isinstance(payload, dict):
        raise PubSubError("payload must be a JSON object")
    note = ""
    for key in ("intake_note", "note", "text"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            note = value
            break
    if not note:
        raise PubSubError("no intake note found (expected intake_note/note/text)")
    message_id = str(payload.get("messageId") or payload.get("message_id") or "local")
    short_sub = normalize_subscription(str(payload.get("subscription", "local")))
    user_id, session_id = build_ids(short_sub, message_id)
    return {
        "note": note,
        "short_sub": short_sub,
        "message_id": message_id,
        "user_id": user_id,
        "session_id": session_id,
    }


# ---------------------------------------------------------------------------
# Workflow execution
# ---------------------------------------------------------------------------
def _is_quota_error(exc: Exception) -> bool:
    text = str(exc).upper()
    return "RESOURCE_EXHAUSTED" in text or "429" in text


async def _create_session(user_id: str, session_id: str) -> None:
    try:
        await _runner.session_service.create_session(
            app_name=adk_app.name, user_id=user_id, session_id=session_id
        )
    except Exception:  # session already exists (e.g. duplicate message id)
        logger.info("reusing existing session %s", session_id)


async def _run_and_collect(user_id: str, session_id: str, message: types.Content):
    """Run the workflow and return the latest IntakeSummary dict seen."""
    last_summary = None
    async for event in _runner.run_async(
        user_id=user_id, session_id=session_id, new_message=message
    ):
        out = getattr(event, "output", None)
        if isinstance(out, dict) and "routing_decision" in out:
            last_summary = out
    return last_summary


def _build_response(fields: dict, summary: dict) -> dict:
    pending = summary.get("routing_decision") == "HUMAN_REVIEW_REQUIRED"
    return {
        "status": "ok",
        "message_id": fields["message_id"],
        "subscription": fields["short_sub"],
        "routing_decision": summary.get("routing_decision"),
        "pending_human_review": pending,
        "session_id": fields["session_id"],
        "summary": summary,
    }


async def _process(fields: dict) -> dict:
    user_id, session_id = fields["user_id"], fields["session_id"]
    _SESSIONS[session_id] = user_id
    await _create_session(user_id, session_id)
    message = types.Content(
        role="user", parts=[types.Part.from_text(text=fields["note"])]
    )
    try:
        summary = await _run_and_collect(user_id, session_id, message)
    except Exception as exc:
        if _is_quota_error(exc):
            logger.warning(
                "model quota exhausted (429) for msg=%s sub=%s",
                fields["message_id"],
                fields["short_sub"],
            )
            raise HTTPException(
                status_code=503,
                detail="Model quota exhausted (429 RESOURCE_EXHAUSTED). "
                "Top up the Google AI Studio API key and retry.",
            ) from exc
        raise
    if summary is None:
        raise HTTPException(status_code=500, detail="Workflow produced no summary.")
    # PII-safe logging only.
    logger.info(
        "processed intake: sub=%s msg=%s routing=%s",
        fields["short_sub"],
        fields["message_id"],
        summary.get("routing_decision"),
    )
    return _build_response(fields, summary)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
class ResumeBody(BaseModel):
    decision: str
    note: str = ""


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/pubsub/push")
async def pubsub_push(payload: dict) -> dict:
    """Pub/Sub push endpoint. Expects the standard push envelope."""
    try:
        fields = parse_push_envelope(payload)
    except PubSubError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await _process(fields)


@app.post("/")
async def root_push(payload: dict) -> dict:
    """Relaxed endpoint for local testing (envelope or plain note body)."""
    try:
        fields = parse_relaxed(payload)
    except PubSubError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await _process(fields)


@app.post("/human-review/{session_id}")
async def resume_human_review(session_id: str, body: ResumeBody) -> dict:
    """Resume a paused review with a clinician decision + note.

    Sends a FunctionResponse keyed by the review interrupt id so the paused
    workflow resumes at human_review_node (no model call). The model is not
    invoked again, per v1 option A.
    """
    decision = body.decision.strip().upper().replace("-", "_")
    if decision not in CLINICIAN_DECISIONS:
        raise HTTPException(
            status_code=422,
            detail=f"decision must be one of {', '.join(CLINICIAN_DECISIONS)}",
        )
    user_id = _SESSIONS.get(session_id)
    if not user_id:
        raise HTTPException(
            status_code=404, detail=f"No pending session '{session_id}'."
        )

    message = types.Content(
        role="user",
        parts=[
            types.Part(
                function_response=types.FunctionResponse(
                    id=REVIEW_INTERRUPT_ID,
                    name=REVIEW_INTERRUPT_ID,
                    response={"decision": decision, "note": body.note or ""},
                )
            )
        ],
    )
    summary = await _run_and_collect(user_id, session_id, message)
    if summary is None:
        raise HTTPException(
            status_code=409,
            detail="Could not resume the session (no output produced).",
        )
    logger.info(
        "resumed review: session=%s decision=%s", session_id, decision
    )
    return {"status": "ok", "session_id": session_id, "summary": summary}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
