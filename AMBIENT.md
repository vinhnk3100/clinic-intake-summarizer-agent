# Ambient (Event-Driven) Service

The Clinic Intake Summarizer can run as an **ambient** service: instead of a chat
UI, it accepts **Pub/Sub-style push messages** over HTTP and feeds each intake
note into the existing ADK 2.0 graph Workflow
(`screen_node → extract_node → route_node → human_review_node → finalize_node`).

This is implemented in `app/ambient_app.py` and is separate from the Playground /
dev server (`app/fast_api_app.py`, unchanged). Synthetic data only.

---

## 1. How to run the service (port 8080)

```bash
make ambient
# or directly (e.g. on Windows without `make`):
uv run uvicorn app.ambient_app:app --host 0.0.0.0 --port 8080
```

- Uses Google AI Studio **API key mode** from `.env` (`GOOGLE_GENAI_USE_VERTEXAI=FALSE`,
  `GOOGLE_API_KEY`, `GEMINI_MODEL`). **No GCP credentials required.**
- **No cloud telemetry** (`otel_to_cloud` is effectively False — the cloud chat
  server `get_fast_api_app` is not used here). Standard Python `logging` only.

## 2. Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/pubsub/push` | Pub/Sub push endpoint (standard envelope) |
| `POST` | `/` | Relaxed endpoint for local testing (envelope **or** plain note body) |
| `POST` | `/human-review/{session_id}` | Resume a paused review with a clinician decision + note |
| `GET`  | `/health` | Health check |

## 3. Expected Pub/Sub payload shape

```json
{
  "message": {
    "data": "<base64 of the intake note OR JSON {\"intake_note\": \"...\"}>",
    "messageId": "1001",
    "attributes": {}
  },
  "subscription": "projects/demo/subscriptions/clinic-intake-sub"
}
```

- `message.data` is **base64-encoded**. After decoding, if it is a JSON object
  with `intake_note` / `note` / `text`, that field is used as the note; otherwise
  the decoded text itself is the note.
- A malformed payload (missing `message`, bad base64, empty note) returns **400**.

## 4. Subscription normalization

The fully-qualified subscription path is shortened to a readable name and used to
build readable session/user identifiers:

```
projects/demo/subscriptions/clinic-intake-sub   ->   clinic-intake-sub
```

- `user_id`    = `clinic-intake-sub`
- `session_id` = `clinic-intake-sub-<messageId>`  (e.g. `clinic-intake-sub-1001`)

## 5. Sample NORMAL intake event

```bash
curl -s -X POST http://127.0.0.1:8080/pubsub/push \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "data": "SGksIEkgaGFkIGEgbWlsZCBzb3JlIHRocm9hdCBhbmQgYSBydW5ueSBub3NlIGZvciBhYm91dCAzIGRheXMuIE5vIGZldmVyLiBJIHNvbWV0aW1lcyB0YWtlIHBhcmFjZXRhbW9sLiBObyBrbm93biBhbGxlcmdpZXMu",
      "messageId": "1001"
    },
    "subscription": "projects/demo/subscriptions/clinic-intake-sub"
  }'
```

Expected (when the model has quota): `routing_decision: "NORMAL_INTAKE"`,
`pending_human_review: false`, full `summary`.

Simplest local form (no base64, via `POST /`):

```bash
curl -s -X POST http://127.0.0.1:8080/ \
  -H "Content-Type: application/json" \
  -d '{"intake_note": "Mild sore throat and runny nose for 3 days, no fever."}'
```

## 6. Sample RED-FLAG intake event (pauses for human review)

```bash
curl -s -X POST http://127.0.0.1:8080/pubsub/push \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "data": "SSBoYXZlIGhhZCBjaGVzdCBkaXNjb21mb3J0IHNpbmNlIHRoaXMgbW9ybmluZywgYW5kIHNvbWV0aW1lcyBzaG9ydG5lc3Mgb2YgYnJlYXRoLiBJIHRha2UgYmxvb2QgcHJlc3N1cmUgbWVkaWNhdGlvbiBkYWlseS4=",
      "messageId": "2002"
    },
    "subscription": "projects/demo/subscriptions/clinic-intake-sub"
  }'
```

Expected: `routing_decision: "HUMAN_REVIEW_REQUIRED"`, `pending_human_review: true`,
`session_id: "clinic-intake-sub-2002"`. The workflow pauses at the `RequestInput`
HITL node — the clinician decision is **not** faked.

## 7. Pending human review + resume

Review cases (red flag, prompt injection, or insufficient information) route to
`HUMAN_REVIEW_REQUIRED` and **pause** at the HITL node. The push response carries
`pending_human_review: true` and a `session_id`. Resolve it with:

```bash
curl -s -X POST http://127.0.0.1:8080/human-review/clinic-intake-sub-2002 \
  -H "Content-Type: application/json" \
  -d '{"decision": "ESCALATE", "note": "call cardiology now"}'
```

- `decision` must be one of `APPROVED`, `ESCALATE`, `NEEDS_MORE_INFO` (else **422**).
- Unknown `session_id` returns **404**.
- On success the finalized `summary` is returned with
  `clinician_review: { "reviewed": true, "decision": "ESCALATE", "note": "..." }`.
  The model is **not** called again (v1 option A).

Alternatively, the same paused review can be resumed interactively from the
**Playground** (`make playground`) by entering, for example,
`ESCALATE call cardiology now` in the `adk_request_input` card's
**`Enter your response...`** field. Using the main chat box starts a new
invocation instead of resuming the paused workflow. See `PLAYGROUND.md`.

> The resume endpoint requires a previously-created paused session in the same
> running process (sessions are in-memory).

### HITL resume — manual live test (verified)

The RequestInput pause/resume cycle cannot be automated by `agents-cli eval`
(there is no simulated clinician, and the CLI eval path needs GCP anyway — see
§9). It is therefore validated as a **manual live test**, which has been run
end-to-end successfully:

1. `POST /pubsub/push` with the red-flag note (messageId `2002`) →
   `routing_decision: HUMAN_REVIEW_REQUIRED`, `pending_human_review: true`,
   `session_id: clinic-intake-sub-2002` (workflow paused at `RequestInput`).
2. `POST /human-review/clinic-intake-sub-2002` with
   `{"decision": "ESCALATE", "note": "call cardiology now"}` → `200`, final
   summary with `clinician_review: {"reviewed": true, "decision": "ESCALATE",
   "note": "call cardiology now"}`. The model was **not** called again.

The normal, sparse, and prompt-injection ambient flows were verified live the
same way. Re-run them with the curl commands above (or via `DEMO_SCRIPT.md`).

## 8. About the 429 quota error (live testing)

Live workflow execution calls the Gemini model at `extract_node` and may return
`429 RESOURCE_EXHAUSTED — prepayment credits depleted` until the Google AI Studio
API key has quota/credit. In that case the push endpoint returns HTTP **503** (so
a real Pub/Sub subscription would retry). The deterministic parsing, routing, and
validation paths work without the model — see `uv run pytest tests/unit`.
Top up or swap `GOOGLE_API_KEY` in `.env` to run full end-to-end tests.

## 9. Evaluation note (`agents-cli eval` vs the local harness)

`agents-cli eval generate` and `agents-cli eval grade` both construct a
`vertexai.Client`, which requires **GCP Application Default Credentials (ADC)** —
even for local custom (code) metrics. This project runs in **Google AI Studio API
key mode with no GCP ADC**, so the CLI eval path cannot run here. Instead, use the
**local deterministic eval harness**:

```bash
uv run python tests/eval/run_local_eval.py
```

It runs all 6 scenarios through the workflow (real model, API key) and prints a
PASS/FAIL table. `tests/eval/eval_config.yaml` is kept as a documented artifact
encoding the same checks (and would work if ADC were configured).
