#!/bin/bash
# setup-a2a-permissions.sh - Configure A2A permissions for gcp-finops-agent executor integration
#
# Grants gcp-finops-agent permission to invoke a downstream executor agent (Reasoning Engine).
# Flow: gcp-finops-agent (analyzes costs) → invokes → Executor Agent (takes action)
#
# Usage:
#   ./deploy/setup-a2a-permissions.sh <EXECUTOR_RESOURCE_NAME>
#
# Example:
#   ./deploy/setup-a2a-permissions.sh projects/your-project-id/locations/us-central1/reasoningEngines/987654321

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
LOCATION="${GCP_LOCATION:-us-central1}"
AGENT_SA="gcp-finops-agent@${PROJECT_ID}.iam.gserviceaccount.com"
EXECUTOR_SA="executor-agent@${PROJECT_ID}.iam.gserviceaccount.com"

# Check arguments
if [ $# -ne 1 ]; then
    echo -e "${RED}Error: Missing executor agent Reasoning Engine resource name${NC}"
    echo ""
    echo "Usage: $0 <EXECUTOR_RESOURCE_NAME>"
    echo ""
    echo "Example:"
    echo "  $0 projects/your-project-id/locations/us-central1/reasoningEngines/987654321"
    echo ""
    echo "To find the executor resource name, run:"
    echo "  gcloud ai reasoning-engines list --project=$PROJECT_ID --region=$LOCATION"
    exit 1
fi

EXECUTOR_RESOURCE_NAME="$1"

echo -e "${GREEN}=== gcp-finops-agent A2A Permission Setup ===${NC}"
echo ""
echo "Project:                    $PROJECT_ID"
echo "Location:                   $LOCATION"
echo "Agent Service Account:        $AGENT_SA"
echo "Executor Service Account:   $EXECUTOR_SA"
echo "Executor Resource Name:     $EXECUTOR_RESOURCE_NAME"
echo ""

# Verify agent SA exists
echo -e "${YELLOW}[1/4] Verifying agent service account exists...${NC}"
if gcloud iam service-accounts describe "$AGENT_SA" --project="$PROJECT_ID" &>/dev/null; then
    echo -e "${GREEN}✓ Agent service account exists${NC}"
else
    echo -e "${RED}✗ Agent service account not found. Creating...${NC}"
    gcloud iam service-accounts create gcp-finops-agent \
        --project="$PROJECT_ID" \
        --display-name="GCP FinOps Agent" \
        --description="Service account for gcp-finops-agent"
    echo -e "${GREEN}✓ Agent service account created${NC}"
fi

# Verify executor SA exists
echo -e "${YELLOW}[2/4] Verifying executor service account exists...${NC}"
if gcloud iam service-accounts describe "$EXECUTOR_SA" --project="$PROJECT_ID" &>/dev/null; then
    echo -e "${GREEN}✓ Executor service account exists${NC}"
else
    echo -e "${RED}✗ Executor service account not found. Creating...${NC}"
    gcloud iam service-accounts create executor-agent \
        --project="$PROJECT_ID" \
        --display-name="Executor Agent" \
        --description="Service account for the A2A executor agent"
    echo -e "${GREEN}✓ Executor service account created${NC}"
fi

# Grant agent permission to invoke executor
echo -e "${YELLOW}[3/4] Granting agent permission to invoke executor agent...${NC}"
if gcloud ai reasoning-engines add-iam-policy-binding "$EXECUTOR_RESOURCE_NAME" \
    --member="serviceAccount:$AGENT_SA" \
    --role="roles/aiplatform.user" \
    --project="$PROJECT_ID" \
    --location="$LOCATION" &>/dev/null; then
    echo -e "${GREEN}✓ Agent granted aiplatform.user on executor Reasoning Engine${NC}"
else
    echo -e "${RED}✗ Failed to grant permissions. Check that the executor resource name is correct.${NC}"
    exit 1
fi

# Verify IAM binding
echo -e "${YELLOW}[4/4] Verifying IAM binding...${NC}"
BINDING_CHECK=$(gcloud ai reasoning-engines get-iam-policy "$EXECUTOR_RESOURCE_NAME" \
    --project="$PROJECT_ID" \
    --location="$LOCATION" \
    --flatten="bindings[].members" \
    --filter="bindings.members:$AGENT_SA" \
    --format="value(bindings.role)" 2>/dev/null || echo "")

if [[ "$BINDING_CHECK" == *"roles/aiplatform.user"* ]]; then
    echo -e "${GREEN}✓ IAM binding verified successfully${NC}"
else
    echo -e "${RED}✗ IAM binding verification failed${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}=== A2A Setup Complete ===${NC}"
echo ""
echo "gcp-finops-agent can now invoke the executor agent for action delegation."
echo ""
echo "Set these environment variables for gcp-finops-agent:"
echo "  export A2A_EXECUTOR_ENABLED=true"
echo "  export A2A_EXECUTOR_RESOURCE_NAME='$EXECUTOR_RESOURCE_NAME'"
echo ""
echo "Next steps:"
echo "  1. Set A2A_EXECUTOR_RESOURCE_NAME in gcp-finops-agent's deployment environment"
echo "  2. Test A2A communication (see examples/a2a_executor_example.py)"
echo "  3. Monitor A2A invocations in Cloud Logging"
echo ""
