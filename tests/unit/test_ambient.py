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
"""Unit tests for the ambient Pub/Sub-style service (no model calls).

Covers the deterministic parsing/normalization helpers, the clinician-review
coercion, and endpoint *validation* paths (400/404/422/health). Endpoint paths
that would invoke the model are intentionally not exercised here (that needs
quota and belongs in eval / manual testing).
"""

import base64
import json

import pytest
from fastapi.testclient import TestClient

from app.agent import coerce_clinician_review
from app.ambient_app import (
    PubSubError,
    app,
    build_ids,
    decode_pubsub_data,
    extract_note,
    normalize_subscription,
    parse_push_envelope,
    parse_relaxed,
)

client = TestClient(app)


def _b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


# --- normalize_subscription -----------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("projects/demo/subscriptions/clinic-intake-sub", "clinic-intake-sub"),
        ("projects/p/subscriptions/sub-a/", "sub-a"),
        ("clinic-intake-sub", "clinic-intake-sub"),
        ("", "unknown-subscription"),
    ],
)
def test_normalize_subscription(raw, expected):
    assert normalize_subscription(raw) == expected


# --- decode_pubsub_data ----------------------------------------------------
def test_decode_pubsub_data_valid():
    assert decode_pubsub_data(_b64("hello note")) == "hello note"


def test_decode_pubsub_data_invalid():
    with pytest.raises(PubSubError):
        decode_pubsub_data("!!!not-base64!!!")


# --- extract_note ----------------------------------------------------------
def test_extract_note_plain_text():
    assert extract_note("I have a sore throat") == "I have a sore throat"


@pytest.mark.parametrize("key", ["intake_note", "note", "text"])
def test_extract_note_from_json(key):
    decoded = json.dumps({key: "chest pain since morning"})
    assert extract_note(decoded) == "chest pain since morning"


def test_extract_note_json_without_known_key_falls_back_to_text():
    decoded = json.dumps({"foo": "bar"})
    assert extract_note(decoded) == decoded


# --- build_ids -------------------------------------------------------------
def test_build_ids_readable():
    user_id, session_id = build_ids("clinic-intake-sub", "1001")
    assert user_id == "clinic-intake-sub"
    assert session_id == "clinic-intake-sub-1001"


def test_build_ids_missing_message_id():
    _, session_id = build_ids("clinic-intake-sub", "")
    assert session_id == "clinic-intake-sub-nomsgid"


# --- parse_push_envelope ---------------------------------------------------
def test_parse_push_envelope_full():
    payload = {
        "message": {"data": _b64("sore throat for 3 days"), "messageId": "1001"},
        "subscription": "projects/demo/subscriptions/clinic-intake-sub",
    }
    fields = parse_push_envelope(payload)
    assert fields["note"] == "sore throat for 3 days"
    assert fields["short_sub"] == "clinic-intake-sub"
    assert fields["message_id"] == "1001"
    assert fields["session_id"] == "clinic-intake-sub-1001"


def test_parse_push_envelope_json_data():
    payload = {
        "message": {"data": _b64(json.dumps({"intake_note": "chest pain"}))},
        "subscription": "projects/demo/subscriptions/sub",
    }
    assert parse_push_envelope(payload)["note"] == "chest pain"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"message": "not-an-object"},
        {"message": {}},
        {"message": {"data": ""}},
        {"message": {"data": _b64("   ")}},
    ],
)
def test_parse_push_envelope_bad(payload):
    with pytest.raises(PubSubError):
        parse_push_envelope(payload)


# --- parse_relaxed ---------------------------------------------------------
def test_parse_relaxed_plain_note():
    fields = parse_relaxed({"intake_note": "headache for a week"})
    assert fields["note"] == "headache for a week"
    assert fields["short_sub"] == "local"


def test_parse_relaxed_envelope():
    payload = {"message": {"data": _b64("note text"), "messageId": "7"}}
    assert parse_relaxed(payload)["note"] == "note text"


def test_parse_relaxed_bad():
    with pytest.raises(PubSubError):
        parse_relaxed({"foo": "bar"})


# --- coerce_clinician_review (resume payload normalization) ----------------
def test_coerce_review_structured_dict():
    assert coerce_clinician_review({"decision": "ESCALATE", "note": "cardio"}) == (
        "ESCALATE",
        "cardio",
    )


def test_coerce_review_hyphenated_decision():
    assert coerce_clinician_review({"decision": "needs-more-info"}) == (
        "NEEDS_MORE_INFO",
        "",
    )


def test_coerce_review_free_text_string():
    assert coerce_clinician_review("APPROVED routine follow-up") == (
        "APPROVED",
        "routine follow-up",
    )


def test_coerce_review_free_text_in_dict():
    assert coerce_clinician_review({"reply": "ESCALATE call cardiology"}) == (
        "ESCALATE",
        "call cardiology",
    )


# --- endpoint validation (no model calls) ----------------------------------
def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_pubsub_push_bad_payload_returns_400():
    resp = client.post("/pubsub/push", json={"message": {}})
    assert resp.status_code == 400


def test_pubsub_push_bad_base64_returns_400():
    resp = client.post(
        "/pubsub/push",
        json={"message": {"data": "!!!notbase64!!!"}, "subscription": "s"},
    )
    assert resp.status_code == 400


def test_root_bad_payload_returns_400():
    resp = client.post("/", json={"foo": "bar"})
    assert resp.status_code == 400


def test_resume_unknown_session_returns_404():
    resp = client.post(
        "/human-review/does-not-exist", json={"decision": "APPROVED", "note": ""}
    )
    assert resp.status_code == 404


def test_resume_bad_decision_returns_422():
    resp = client.post(
        "/human-review/any-session", json={"decision": "MAYBE", "note": ""}
    )
    assert resp.status_code == 422
