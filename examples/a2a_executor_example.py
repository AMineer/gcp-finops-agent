"""Minimal reference showing how to point gcp-finops-agent at a downstream executor agent.

This example requires a separately deployed executor agent (Reasoning Engine)
that is NOT part of this repository. gcp-finops-agent itself provides the analysis;
the executor is responsible for taking action on identified resources.

Prerequisites:
    1. gcp-finops-agent deployed to Vertex AI Agent Engine
    2. A downstream executor agent deployed separately
    3. A2A IAM permissions configured (see deploy/setup-a2a-permissions.sh)

Environment variables:
    A2A_EXECUTOR_ENABLED=true
    A2A_EXECUTOR_RESOURCE_NAME=projects/your-project-id/locations/us-central1/reasoningEngines/ENGINE_ID
    GCP_PROJECT_ID=your-project-id
    GCP_BILLING_DATASET=your-billing-project.your_billing_dataset.gcp_billing_export_v1_XXXXXX
    GCP_DETAILED_BILLING_DATASET=your-billing-project.your_billing_dataset.gcp_billing_export_resource_v1_XXXXXX
"""

import asyncio
import os

from gcp_finops_agent.a2a_executor import delegate_action, check_executor_capabilities


async def example_check_capabilities():
    """Check what resource types the executor supports."""
    result = await check_executor_capabilities([
        "compute_instance",
        "persistent_disk",
        "storage_bucket",
        "cloud_sql_instance",
    ])
    print("Executor capabilities:", result)


async def example_delegate_cleanup():
    """Delegate cleanup of identified wasteful resources."""
    resources = [
        {
            "resource_type": "compute_instance",
            "resource_id": "idle-vm-example-001",
            "project_id": os.getenv("GCP_PROJECT_ID", "your-project-id"),
            "zone": "us-central1-a",
            "estimated_monthly_cost": 156.48,
            "recommendation": "delete",
        },
    ]

    result = await delegate_action(
        resources=resources,
        justification=(
            "VM has <5% CPU utilization for 30 days, costing $156/month. "
            "No active connections or disk I/O detected."
        ),
        priority="medium",
    )
    print("Delegation result:", result)


if __name__ == "__main__":
    executor_resource = os.getenv("A2A_EXECUTOR_RESOURCE_NAME", "")
    enabled = os.getenv("A2A_EXECUTOR_ENABLED", "false").lower() == "true"

    if not enabled or not executor_resource:
        print(
            "Set A2A_EXECUTOR_ENABLED=true and A2A_EXECUTOR_RESOURCE_NAME "
            "to run this example against a live executor agent."
        )
        print("Running in dry-run mode (will show 'disabled' responses).")

    asyncio.run(example_check_capabilities())
    asyncio.run(example_delegate_cleanup())
