# Contributing

## Development Setup

```bash
# Clone the repo and install in editable mode with dev extras
git clone https://github.com/your-handle/gcp-finops-agent.git
cd gcp-finops-agent
uv pip install -e ".[dev]"
```

Copy `.env.example` to `.env` and fill in your GCP project, billing dataset, and
project scope. You need a GCP project with BigQuery billing export enabled to run
the agent against live data.

## Running Tests

```bash
# Unit tests only (no GCP credentials required)
uv run pytest -m "not eval" -v

# Evaluation tests (requires GCP credentials and a deployed agent)
uv run pytest tests/evals/ -v
```

## Lint and Type Checking

All PRs must pass these before merge:

```bash
uv run ruff check .
uv run mypy gcp_finops_agent
```

Fix ruff issues automatically with:

```bash
uv run ruff check --fix .
```

## Running the Agent Locally

```bash
adk web
```

This starts the ADK development server at `http://localhost:8000`. Requires
`GCP_PROJECT_ID`, `GCP_BILLING_DATASET`, `GCP_DETAILED_BILLING_DATASET`, and
valid GCP credentials (`gcloud auth application-default login`).

## Project Structure

```
gcp_finops_agent/ # Agent package
  agent.py        # ADK root_agent definition
  config.py       # Pydantic-settings config (all env vars here)
  gcp.py          # BigQuery + Recommender API connectors
  gcs.py          # Cloud Storage connector
  tools.py        # ADK tool wrappers
  prompts.py      # System instruction builder
  models.py       # Pydantic data models
  sanitize.py     # LLM output sanitization
  a2a_executor.py # Optional A2A extension (disabled by default)
tests/            # Unit and eval tests
deploy/           # Agent Engine deployment scripts
docs/             # Architecture and permission docs
examples/         # Runnable reference scripts
```

## PR Guidelines

- One logical change per PR — keep diffs reviewable.
- Update `.env.example` if you add a new environment variable.
- Add or update tests for any behavioral change.
- Do not commit `.env`, credentials, or real project IDs.
- Keep the agent's core behavior intact; configuration and tooling changes are welcome.

## Environment Variables

See `.env.example` for the full list. Required variables:

| Variable | Description |
|----------|-------------|
| `GCP_PROJECT_ID` | Host project for Agent Engine and quota |
| `GCP_LOCATION` | Region (default: `us-central1`) |
| `GEMINI_MODEL` | Model to use (default: `gemini-2.5-flash`) |
| `GCP_BILLING_DATASET` | Fully-qualified standard billing export table |
| `GCP_DETAILED_BILLING_DATASET` | Fully-qualified detailed billing export table |
| `GCP_PROJECT_SCOPE` | Comma-separated project IDs for Recommender API |
| `AGENT_ENGINE_STAGING_BUCKET` | GCS bucket for deployment artifacts |

Optional (A2A executor):

| Variable | Description |
|----------|-------------|
| `A2A_EXECUTOR_ENABLED` | Set `true` to enable A2A delegation (default: `false`) |
| `A2A_EXECUTOR_RESOURCE_NAME` | Reasoning Engine resource name of the executor agent |
