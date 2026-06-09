# Agent Engine Deployment

Deploy gcp-finops-agent ADK agent to Vertex AI Agent Engine.

## Quick Start

### 1. Set Up Staging Bucket

```bash
# First time only: create the bucket and grant permissions
./deploy/setup-staging-bucket.sh your-project-id your-agent@your-project-id.iam.gserviceaccount.com
```

This creates:
- GCS bucket: `gs://your-project-id-agent-engine-staging`
- Grants `storage.objectAdmin` to your service account
- Sets auto-delete lifecycle (30 days)

### 2. Deploy via CLI

For local or manual deployment:

```bash
# Set environment variables
export GCP_PROJECT_ID=your-project-id
export GCP_LOCATION=us-central1
export GEMINI_MODEL=gemini-2.5-flash-lite
export GCP_BILLING_DATASET=your-billing-project.your_billing_dataset.gcp_billing_export_v1_XXXXXX
export GCP_DETAILED_BILLING_DATASET=your-billing-project.your_billing_dataset.gcp_billing_export_resource_v1_XXXXXX
export GCP_PROJECT_SCOPE=your-project-a,your-project-b
export AGENT_ENGINE_STAGING_BUCKET=gs://your-agent-engine-staging-bucket
export GOOGLE_GENAI_USE_VERTEXAI=true

# Authenticate as your service account
gcloud auth application-default login
gcloud auth application-default set-quota-project $GCP_PROJECT_ID

# Create initial deployment
python deploy/agent_engine_deploy.py --create

# Save the resource name for future updates
RESOURCE_NAME="projects/your-project-id/locations/us-central1/reasoningEngines/YOUR_ENGINE_ID"

# Update existing deployment (subsequent deploys)
python deploy/agent_engine_deploy.py --update --resource-name "$RESOURCE_NAME"
```

### 3. Deploy via GitLab CI

#### Option A: Include the template

In your `.gitlab-ci.yml`:

```yaml
stages:
  - test
  - deploy-stage

variables:
  GCP_PROJECT_ID: your-project-id
  GCP_LOCATION: us-central1
  SERVICE_ACCOUNT_EMAIL: your-agent@your-project-id.iam.gserviceaccount.com
  AGENT_ENGINE_STAGING_BUCKET: gs://your-agent-engine-staging-bucket

include:
  - local: deploy/.gitlab-ci-agent-engine.yml
```

#### Option B: Manual integration

If you have an existing OIDC pipeline, add these jobs:

```yaml
deploy-agent-engine:
  stage: deploy
  image: python:3.12
  script:
    # Authenticate via OIDC
    - gcloud auth application-default login \
        --impersonate-service-account="${SERVICE_ACCOUNT_EMAIL}"
    - gcloud auth application-default set-quota-project "$GCP_PROJECT_ID"
    
    # Install dependencies
    - pip install -e ".[dev]"
    
    # Deploy
    - python deploy/agent_engine_deploy.py --create
  environment:
    name: vertex-ai-agent-engine
  only:
    - main
  when: manual
```

## Prerequisites

Before deploying, ensure:

1. **APIs enabled** in GCP project:
   ```bash
   gcloud services enable aiplatform.googleapis.com \
     bigquery.googleapis.com \
     recommender.googleapis.com \
     storage.googleapis.com
   ```

2. **Service account exists** with IAM roles:
   - `roles/aiplatform.user` - Create/update Reasoning Engines
   - `roles/bigquery.jobUser` - Execute BigQuery jobs
   - `roles/bigquery.dataViewer` - Read billing export data
   - `roles/recommender.viewer` - Read recommendations
   - `roles/storage.objectAdmin` - Manage staging bucket

3. **BigQuery billing export** configured:
   - Standard export table: `GCP_BILLING_DATASET`
   - Detailed export table: `GCP_DETAILED_BILLING_DATASET`

4. **Staging bucket** created:
   ```bash
   ./deploy/setup-staging-bucket.sh $PROJECT_ID $SERVICE_ACCOUNT_EMAIL
   ```

5. **OIDC configured** (for GitLab CI):
   - Workload identity pool set up
   - GitLab OIDC provider registered
   - Service account configured for OIDC federation
   - GitLab runners with proper IAM bindings

## Files

| File | Purpose |
|------|---------|
| `agent_engine_deploy.py` | CLI script to create/update Reasoning Engine |
| `setup-staging-bucket.sh` | GCS bucket setup and IAM wiring |
| `.gitlab-ci-agent-engine.yml` | GitLab CI template for automated deployment |

## Testing the Deployment

After deployment, test the agent:

```bash
# Get the Reasoning Engine resource name from create output
RESOURCE_NAME="projects/.../locations/.../reasoningEngines/..."

# Test via Vertex AI API (requires gcloud auth)
gcloud ai reasoning-engines query \
  --resource="$RESOURCE_NAME" \
  --query="What did we spend in GCP this month?"
```

Or use the Vertex AI console: **Vertex AI → Reasoning Engines → Select engine → Test**

## Troubleshooting

**Error: "Permission denied on storage bucket"**
- Verify service account has `roles/storage.objectAdmin` on bucket
- Re-run: `./deploy/setup-staging-bucket.sh`

**Error: "API not enabled"**
- Run the APIs enable commands above

**Error: "BigQuery dataset not found"**
- Verify `GCP_BILLING_DATASET` points to correct project.dataset.table
- Check service account has `roles/bigquery.dataViewer` on billing export project

**Error: "No quota project set"**
- Run: `gcloud auth application-default set-quota-project $GCP_PROJECT_ID`

**OIDC authentication fails**
- Verify GitLab OIDC provider is registered in GCP
- Verify service account has workload identity federation bindings
- Check GitLab CI environment variables are set correctly
