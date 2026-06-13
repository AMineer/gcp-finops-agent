# gcp-finops-agent

GCP FinOps ADK agent powered by Google ADK and deployed to Vertex AI Agent Engine.

**New here?** See [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) for a step-by-step setup walkthrough after cloning.

## What This Repo Contains

- ADK agent package in `gcp_finops_agent/`
- Vertex Agent Engine deployment script in `deploy/agent_engine_deploy.py`
- Agent-to-Agent (A2A) integration examples in `examples/`
- Python project metadata in `pyproject.toml`

## Prerequisites

1. Enable APIs in your host project:
   - `aiplatform.googleapis.com`
   - `bigquery.googleapis.com`
   - `recommender.googleapis.com`
   - `storage.googleapis.com`
2. Configure BigQuery billing export tables used by the agent.
3. Grant IAM to the runtime principal:
   - `roles/aiplatform.user`
   - `roles/bigquery.jobUser`
   - `roles/bigquery.dataViewer` (billing export project)
   - `roles/recommender.viewer` (each scoped project)

## Install

```bash
uv pip install -e ".[dev]"
```

## Configure Environment

Copy `.env.example` to `.env` and fill in your values:

```bash
# Required
GCP_PROJECT_ID=your-project-id
GCP_LOCATION=us-central1
GEMINI_MODEL=gemini-2.5-flash
GCP_BILLING_DATASET=your-billing-project.your_billing_dataset.gcp_billing_export_v1_XXXXXX
GCP_DETAILED_BILLING_DATASET=your-billing-project.your_billing_dataset.gcp_billing_export_resource_v1_XXXXXX
GCP_PROJECT_SCOPE=your-project-a,your-project-b
AGENT_ENGINE_STAGING_BUCKET=gs://your-agent-engine-staging-bucket
GOOGLE_GENAI_USE_VERTEXAI=true

# Optional — enable A2A executor delegation
# A2A_EXECUTOR_ENABLED=false
# A2A_EXECUTOR_RESOURCE_NAME=projects/your-project-id/locations/us-central1/reasoningEngines/ENGINE_ID
```

## Authenticate

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project "$GCP_PROJECT_ID"
```

## Deploy To Agent Engine

Create a new deployment:

```bash
python deploy/agent_engine_deploy.py --create
```

Update an existing deployment:

```bash
python deploy/agent_engine_deploy.py \
  --update \
  --resource-name projects/PROJECT/locations/us-central1/reasoningEngines/ENGINE_ID
```

## Optional Local Smoke Run

```bash
adk web
```

This is optional and only for quick local validation.

## Agent-to-Agent (A2A) Integration

gcp-finops-agent supports optional A2A delegation to a downstream executor agent. When enabled, it can hand off remediation actions after identifying wasteful resources.

See [docs/A2A_SETUP.md](docs/A2A_SETUP.md) for detailed setup instructions.

**Quick setup:**

```bash
# After deploying your executor agent, grant gcp-finops-agent permission to invoke it
export A2A_EXECUTOR_RESOURCE_NAME="projects/your-project-id/locations/us-central1/reasoningEngines/YOUR_ENGINE_ID"
./deploy/setup-a2a-permissions.sh "$A2A_EXECUTOR_RESOURCE_NAME"

# Enable A2A in the agent's environment
export A2A_EXECUTOR_ENABLED=true
```

**Example integration code:** See [examples/a2a_executor_example.py](examples/a2a_executor_example.py)
