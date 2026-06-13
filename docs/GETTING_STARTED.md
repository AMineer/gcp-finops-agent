# Getting Started

This guide picks up right after you've cloned the repo.

## Prerequisites

Install these before anything else:

- **Python 3.12+** — [python.org](https://www.python.org/downloads/)
- **uv** — `pip install uv` or see [docs.astral.sh/uv](https://docs.astral.sh/uv/)
- **gcloud CLI** — [cloud.google.com/sdk/docs/install](https://cloud.google.com/sdk/docs/install)
- **Google ADK** — installed automatically via `uv sync` below

Your GCP project also needs these APIs enabled:

```bash
gcloud services enable \
  aiplatform.googleapis.com \
  bigquery.googleapis.com \
  recommender.googleapis.com \
  storage.googleapis.com
```

## 1. Install dependencies

```bash
uv sync --all-extras
```

This installs the agent package, ADK, and all dev tools (ruff, mypy, pytest).

## 2. Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in your values. The required fields are:

| Variable | Description |
|---|---|
| `GCP_PROJECT_ID` | Your GCP project ID |
| `GCP_LOCATION` | Region (e.g. `us-central1`) |
| `GEMINI_MODEL` | Model to use (e.g. `gemini-2.5-flash`) |
| `GCP_BILLING_DATASET` | Full path to your standard billing export table |
| `GCP_DETAILED_BILLING_DATASET` | Full path to your detailed billing export table |
| `GCP_PROJECT_SCOPE` | Comma-separated list of projects the agent can query |
| `AGENT_ENGINE_STAGING_BUCKET` | GCS bucket for Agent Engine staging (e.g. `gs://my-bucket`) |

> **BigQuery billing export:** If you haven't set up billing export yet, see [Setting up Cloud Billing data export](https://cloud.google.com/billing/docs/how-to/export-data-bigquery-setup). The tables take up to 24 hours to populate after first activation.

## 3. Authenticate

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project "$GCP_PROJECT_ID"
```

This sets up Application Default Credentials (ADC) that the agent and ADK use locally.

## 4. Verify your setup

Run the unit tests to confirm everything is wired up correctly:

```bash
uv run pytest -m "not eval" -v
```

All tests should pass without any GCP calls — they use mocked responses.

## 5. Run locally

```bash
uv run adk web
```

This launches the ADK developer UI at `http://localhost:8000`. You can chat with the agent directly to verify it can reach BigQuery and the Recommender API.

## 6. Deploy to Agent Engine

Create a staging bucket if you don't have one:

```bash
./deploy/setup-staging-bucket.sh
```

Then deploy:

```bash
python deploy/agent_engine_deploy.py --create
```

To update an existing deployment:

```bash
python deploy/agent_engine_deploy.py \
  --update \
  --resource-name projects/PROJECT/locations/us-central1/reasoningEngines/ENGINE_ID
```

## 7. (Optional) Enable A2A delegation

If you want the agent to delegate remediation actions to a downstream executor agent, see [docs/A2A_SETUP.md](A2A_SETUP.md).

## IAM requirements

The principal running the agent (your ADC locally, or the Agent Engine service account in prod) needs:

| Role | Scope |
|---|---|
| `roles/aiplatform.user` | Host project |
| `roles/bigquery.jobUser` | Host project |
| `roles/bigquery.dataViewer` | Billing export project |
| `roles/recommender.viewer` | Each scoped project |

See [docs/PERMISSIONS.md](PERMISSIONS.md) for the full breakdown.
