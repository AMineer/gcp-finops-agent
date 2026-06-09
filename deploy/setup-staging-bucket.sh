#!/bin/bash
# Setup Agent Engine staging bucket for Reasoning Engine deployments
#
# Usage:
#   ./deploy/setup-staging-bucket.sh your-project-id your-agent@your-project-id.iam.gserviceaccount.com
#
# Required args:
#   PROJECT_ID           - GCP project where Reasoning Engine will run
#   SERVICE_ACCOUNT      - Service account email (must exist)
#
# Optional env vars:
#   BUCKET_NAME          - Custom bucket name (default: gs://{PROJECT_ID}-agent-engine-staging)
#   REGION               - GCS region (default: us-central1)

set -euo pipefail

PROJECT_ID="${1:-}"
SERVICE_ACCOUNT="${2:-}"

if [[ -z "$PROJECT_ID" || -z "$SERVICE_ACCOUNT" ]]; then
    echo "Usage: $0 PROJECT_ID SERVICE_ACCOUNT_EMAIL"
    echo ""
    echo "Example: $0 your-project-id your-agent@your-project-id.iam.gserviceaccount.com"
    exit 1
fi

BUCKET_NAME="${BUCKET_NAME:-gs://${PROJECT_ID}-agent-engine-staging}"
BUCKET_NAME_NO_GS="${BUCKET_NAME#gs://}"
REGION="${REGION:-us-central1}"

echo "Creating Agent Engine staging bucket..."
echo "  Project:         $PROJECT_ID"
echo "  Bucket:          $BUCKET_NAME"
echo "  Region:          $REGION"
echo "  Service Account: $SERVICE_ACCOUNT"
echo ""

# Create bucket if it doesn't exist
if gsutil ls -b "$BUCKET_NAME" &>/dev/null; then
    echo "✓ Bucket already exists: $BUCKET_NAME"
else
    echo "Creating bucket..."
    gsutil mb -p "$PROJECT_ID" -l "$REGION" "$BUCKET_NAME"
    echo "✓ Bucket created: $BUCKET_NAME"
fi

# Grant storage.objectAdmin on bucket to service account (for Agent Engine create/update)
echo ""
echo "Granting storage.objectAdmin on bucket to $SERVICE_ACCOUNT..."
gcloud storage buckets add-iam-policy-binding "$BUCKET_NAME" \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/storage.objectAdmin" \
    --project="$PROJECT_ID"
echo "✓ Storage permissions granted"

# Set lifecycle to auto-delete old artifacts after 30 days
echo ""
echo "Setting lifecycle policy (auto-delete after 30 days)..."
cat > /tmp/lifecycle.json <<EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {"age": 30}
      }
    ]
  }
}
EOF
gsutil lifecycle set /tmp/lifecycle.json "$BUCKET_NAME"
rm /tmp/lifecycle.json
echo "✓ Lifecycle policy set"

echo ""
echo "Done! Export this for your pipeline:"
echo "  export AGENT_ENGINE_STAGING_BUCKET=$BUCKET_NAME"
