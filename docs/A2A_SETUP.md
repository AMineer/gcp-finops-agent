# Agent-to-Agent (A2A) Setup

## Overview

gcp-finops-agent supports an optional A2A extension that lets it delegate remediation actions
to a separately deployed executor agent. This is **disabled by default** — gcp-finops-agent
operates as a standalone analysis agent unless you explicitly configure and enable it.

**Architecture:**

```
gcp-finops-agent (FinOps analysis)  ──delegate_action──▶  Executor Agent (takes action)
```

gcp-finops-agent identifies wasteful resources and, when an executor is configured, can hand off
a structured action request. The executor agent (which you supply and deploy
separately) is responsible for actually modifying or deleting resources.

## Prerequisites

1. gcp-finops-agent deployed to Vertex AI Agent Engine
2. A downstream executor agent deployed to a separate Reasoning Engine
3. Both agents running as dedicated service accounts

## Step 1: Create Service Accounts

```bash
export PROJECT_ID=your-project-id
gcloud config set project $PROJECT_ID

# gcp-finops-agent service account
gcloud iam service-accounts create gcp-finops-agent \
  --display-name="GCP FinOps Agent" \
  --description="Service account for gcp-finops-agent"

# Executor service account (for the agent that takes action)
gcloud iam service-accounts create executor-agent \
  --display-name="Executor Agent" \
  --description="Service account for the A2A executor agent"
```

## Step 2: Grant Base Permissions to gcp-finops-agent

```bash
# BigQuery: read billing exports
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:gcp-finops-agent@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:gcp-finops-agent@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataViewer"

# Recommender API
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:gcp-finops-agent@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/recommender.viewer"
```

## Step 3: Configure A2A Permissions

Grant gcp-finops-agent permission to invoke the executor agent's Reasoning Engine:

```bash
export EXECUTOR_RESOURCE_NAME="projects/$PROJECT_ID/locations/us-central1/reasoningEngines/EXECUTOR_ENGINE_ID"

gcloud ai reasoning-engines add-iam-policy-binding "$EXECUTOR_RESOURCE_NAME" \
  --member="serviceAccount:gcp-finops-agent@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user" \
  --project="$PROJECT_ID" \
  --location="us-central1"
```

Or use the helper script:

```bash
export GCP_PROJECT_ID=your-project-id
./deploy/setup-a2a-permissions.sh "$EXECUTOR_RESOURCE_NAME"
```

## Step 4: Enable A2A in gcp-finops-agent's Deployment

Set these environment variables in gcp-finops-agent's deployment:

```bash
A2A_EXECUTOR_ENABLED=true
A2A_EXECUTOR_RESOURCE_NAME=projects/your-project-id/locations/us-central1/reasoningEngines/EXECUTOR_ENGINE_ID
```

When `A2A_EXECUTOR_ENABLED=false` (the default), gcp-finops-agent operates as a standalone
analysis agent and never attempts remote calls to an executor.

## Step 5: Test the Connection

```bash
export A2A_EXECUTOR_RESOURCE_NAME="projects/your-project-id/locations/us-central1/reasoningEngines/EXECUTOR_ENGINE_ID"
python examples/test_a2a_connection.py
```

See `examples/a2a_executor_example.py` for a minimal integration reference.

## Security Model

- **Least Privilege**: gcp-finops-agent's SA has only `aiplatform.user` on the executor's Reasoning Engine
- **Unidirectional**: Only gcp-finops-agent can invoke the executor, not the reverse (unless separately configured)
- **No Public Access**: Reasoning Engines are not publicly accessible
- **Disabled by Default**: No executor is contacted unless `A2A_EXECUTOR_ENABLED=true`

### What this setup does NOT prevent

- Compromised gcp-finops-agent SA: attacker could invoke the executor
- Prompt injection relayed through gcp-finops-agent to the executor
- Cost abuse from repeated invocations

### Optional hardening

- VPC Service Controls around your project
- Cloud Audit Logs for Reasoning Engine invocations
- Rate limiting / quota on Reasoning Engine queries

## Monitoring

Track A2A invocations in Cloud Logging:

```bash
gcloud logging read "
  resource.type=\"aiplatform.googleapis.com/ReasoningEngine\"
  AND protoPayload.authenticationInfo.principalEmail=\"gcp-finops-agent@your-project-id.iam.gserviceaccount.com\"
  AND protoPayload.methodName=\"Query\"
" --limit=50 --format=json
```

## Troubleshooting

**"Permission denied"** — gcp-finops-agent cannot invoke the executor. Verify:

```bash
gcloud ai reasoning-engines get-iam-policy "$EXECUTOR_RESOURCE_NAME" \
  --project=your-project-id --location=us-central1
```

**"Resource not found"** — Executor resource name is incorrect. List engines:

```bash
gcloud ai reasoning-engines list --project=your-project-id --region=us-central1
```

**"disabled" status returned** — `A2A_EXECUTOR_ENABLED` is not set to `true`, or
`A2A_EXECUTOR_RESOURCE_NAME` is empty. Check gcp-finops-agent's environment variables.

## References

- [Vertex AI Reasoning Engines IAM](https://cloud.google.com/vertex-ai/docs/reasoning-engine/access-control)
- [Service Account Best Practices](https://cloud.google.com/iam/docs/best-practices-service-accounts)
