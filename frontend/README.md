# Clinic Intake Summarizer — Demo UI

A small **Next.js (App Router) + TypeScript + Tailwind + shadcn/ui** dashboard for
the Clinic Intake Summarizer Agent. This is a **demo UI only** — it does **not**
implement any agent logic. The Python ADK agent (ambient service) is the source
of truth; the UI calls it through server-side Next.js proxy routes (so there are
no CORS issues). Synthetic data only.

## Architecture

```
Browser (this UI)
   └─ POST /api/intake ───────────────► (proxy) wraps note into a Pub/Sub
                                          base64 envelope, forwards to
                                          http://localhost:8080/pubsub/push
   └─ POST /api/human-review/[id] ────► (proxy) forwards decision/note to
                                          http://localhost:8080/human-review/{id}
                                                │
                                                ▼
                                   Python ambient FastAPI service (uvicorn :8080)
                                   → ADK 2.0 graph Workflow (source of truth)
```

## Prerequisites

- Backend deps installed (repo root): `agents-cli install`
- A working `.env` at the repo root (Google AI Studio API key mode, `GEMINI_MODEL`)
- Node.js + pnpm
- Frontend deps: `cd frontend && pnpm install`
- Config: `cp .env.local.example .env.local` (defaults already point at port 8080)

## Run with the full local demo (three terminals)

**Terminal 1 — backend (ambient service, port 8080):**

```bash
uv run uvicorn app.ambient_app:app --host 0.0.0.0 --port 8080
# or, if you have GNU Make:  make ambient
```

**Terminal 2 — ADK Playground (graph inspector, port 8081):**

```bash
uv run adk web . --host 127.0.0.1 --port 8081      # or: make playground
```

Open http://localhost:8081/dev-ui/?app=app.

**Terminal 3 — frontend (Next.js, port 3000):**

```bash
pnpm dev --hostname 127.0.0.1 --port 3000      # or: make frontend
```

Open http://localhost:3000.

> The UI calls the **ambient** service on port 8080, not the ADK Playground.
> Playground runs separately on port 8081. Submit the same sample in both UIs
> when you want to show the product flow and graph visualization side by side.

## Demo steps

1. Pick a **sample case** (or edit the intake note in the textarea).
2. Click **Submit intake**. The summary cards show routing decision, chief
   complaint, symptoms, duration, medications, allergies, medical history, red
   flags, PII findings, and safety notes.
3. **Normal cases** (`NORMAL_INTAKE`) return the full summary directly.
4. **Review cases** (`HUMAN_REVIEW_REQUIRED` — chest pain, prompt injection,
   sparse) show a **Clinician review** panel with the paused `session_id`:
   - pick a decision: `APPROVED` / `ESCALATE` / `NEEDS_MORE_INFO`
   - add a note (e.g. `call cardiology now`)
   - click **Submit review** → the final JSON updates with `clinician_review`.
5. Expand **Show final JSON** to view the raw structured output.

## Build / lint

```bash
pnpm lint
pnpm build
```

## QA screenshots (manual)

The data layer was verified end-to-end via the proxy (both routes return 200
with the correct routing / `clinician_review`). To capture UI evidence for the
capstone, take screenshots manually:

1. Start both servers: `uv run uvicorn app.ambient_app:app --host 0.0.0.0 --port 8080`
   (terminal 1) and `cd frontend && pnpm dev` (terminal 2). Open http://localhost:3000.
2. Capture: (a) the empty dashboard, (b) a **normal** case result
   (`NORMAL_INTAKE`), (c) a **review** case showing the Clinician review panel +
   `session_id`, and (d) the same case after **Submit review** (final JSON with
   `clinician_review`). Use the OS screenshot tool (Win: `Win+Shift+S`).
3. Save them under `qa-evidence/ui/` (e.g. `ui-01-dashboard.png`,
   `ui-02-normal.png`, `ui-03-review-pending.png`, `ui-04-review-resolved.png`).

> Automated browser capture (Chrome MCP) was used for the Playground screenshots
> in `qa-evidence/`; it was unavailable when the UI was finished, so UI shots are
> captured manually.

## Scripts

| Command | Purpose |
|---------|---------|
| `pnpm dev` | Run the dev server (port 3000) |
| `pnpm build` | Production build (type-check + compile; no backend needed) |
| `pnpm start` | Serve the production build |
| `pnpm lint` | ESLint |

## Notes

- Configuration: `.env.local` (`NEXT_PUBLIC_APP_NAME`, `BACKEND_BASE_URL`).
- If the UI shows a backend error, ensure the ambient service (`uvicorn ... :8080`) is running and the
  AI Studio API key has quota (otherwise the model step returns 429 → 503).
- shadcn/ui components live in `components/ui/`.
