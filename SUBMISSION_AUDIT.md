# Submission Readiness Audit — Clinic Intake Summarizer Agent

Audit run on **2026-06-20**. Model `gemini-2.5-flash-lite`, ADK 2.3.0, Google AI
Studio API-key mode (no GCP). Synthetic data only.

## Summary

| Area | Result |
|------|--------|
| Backend unit tests | ✅ PASS — 85 passed |
| Backend lint (ruff) | ✅ PASS — all checks passed |
| Local eval (6 scenarios) | ✅ PASS — 6/6 |
| Frontend lint (eslint) | ✅ PASS |
| Frontend build (next build) | ✅ PASS |
| Ambient proxies end-to-end (curl) | ✅ PASS — intake / review / resume |
| Secrets & .gitignore | ✅ PASS — no leak; `.env` untracked |
| Doc / config consistency | ✅ PASS (1 issue found & fixed) |
| Repo hygiene | ✅ PASS — no temp files / TODOs |
| QA evidence (Playground) | ✅ PASS — 6 cases (JSON + screenshots) |
| QA evidence (Next.js UI) | ⚠️ ACTION — 4 screenshots captured; save into `qa-evidence/ui/` |
| Git commit state | ⚠️ ACTION — audit edits uncommitted |

## 1. Functional verification

- `uv run pytest tests/unit -q` → **85 passed**.
- `uv run --extra lint ruff check app tests` → **All checks passed**.
- `uv run python tests/eval/run_local_eval.py` → **6/6 scenarios PASSED**
  (normal, pii_heavy, chest_pain_red_flag, prompt_injection, sparse_unclear,
  out_of_scope).
- `cd frontend && pnpm lint` → clean; `pnpm build` → success
  (routes `/`, `/api/intake`, `/api/human-review/[sessionId]`).
- Next.js proxies verified end-to-end via curl: `/api/intake` (normal →
  `NORMAL_INTAKE`; review → `pending_human_review`), `/api/human-review/{id}` →
  `clinician_review` filled.

## 2. Security & secrets

- `.env` is **not** tracked by git; the AI Studio API key does **not** appear in
  any non-`.env` file.
- `.gitignore` covers `.env`, `.env.local`, `.next`, `node_modules`.
- Ambient service never logs the raw intake note (only subscription, message id,
  routing). Verified by code + earlier live logs.

## 3. Consistency (1 issue found & fixed)

- **Fixed:** the model fallback default was still `gemini-3.1-flash-lite` in
  `app/agent.py`, `tests/eval/capture_qa_evidence.py`, and `README.md`. Updated
  all three to `gemini-2.5-flash-lite` to match the configured demo model. No
  `gemini-3.1` references remain.
- Playground port `8081` consistent across Makefile, README, PLAYGROUND.md,
  frontend/README.md.
- 6 eval scenarios consistent across dataset, `eval_config.yaml`, harness, and
  `qa-evidence/SCREENSHOTS.md`.

## 4. Repo hygiene

- No leftover `_*.py` / `_*.json` temp files in the repo root.
- No `TODO` / `FIXME` / `PLACEHOLDER` in `app/` or `frontend/` source.

## 5. QA evidence

- **Playground (`qa-evidence/`):** 6 per-case JSON files + `SUMMARY.json` +
  `SCREENSHOTS.md` + screenshots; routing/PII/HITL outcomes documented.
- **Next.js UI:** 4 screenshots captured this session via Chrome
  (dashboard, review-pending, review-resolved, final-JSON). Chrome MCP attaches
  images inline only, so **save them into `qa-evidence/ui/`** as
  `ui-01-dashboard.png`, `ui-02-review-pending.png`, `ui-03-review-resolved.png`,
  `ui-04-final-json.png` (manual step; see `frontend/README.md`).

## Action items before submitting

1. Save the 4 UI screenshots into `qa-evidence/ui/` (filenames above).
2. Commit the working-tree changes (model-consistency fixes, README updates,
   this audit file).

## Verdict

**Technically submission-ready.** All tests, lint, build, and eval pass; secrets
are safe; docs are consistent. Two manual housekeeping items remain (save UI
screenshots, commit changes) — neither blocks functionality.
