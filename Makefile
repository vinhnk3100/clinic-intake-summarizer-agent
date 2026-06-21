.PHONY: install ambient playground frontend test lint

# Install project dependencies.
install:
	uv sync

# Run the ambient (event-driven) Pub/Sub-style web service on port 8080.
# Direct equivalent (e.g. on Windows without `make`):
#   uv run uvicorn app.ambient_app:app --host 0.0.0.0 --port 8080
ambient:
	uv run uvicorn app.ambient_app:app --host 0.0.0.0 --port 8080

# Run the interactive ADK dev playground on port 8081.
# Note: prefer this over `agents-cli playground` on Windows (the latter passes an
# unquoted --allow_origins * that gets glob-expanded). See PLAYGROUND.md.
playground:
	uv run adk web . --host 127.0.0.1 --port 8081

# Run the optional Next.js demo UI on port 3000.
# The UI proxies intake and review requests to the ambient service on port 8080.
frontend:
	cd frontend && pnpm dev --hostname 127.0.0.1 --port 3000

# Run unit tests (deterministic, no model needed).
test:
	uv run pytest tests/unit -q

# Lint with ruff.
lint:
	uv run --extra lint ruff check app tests
