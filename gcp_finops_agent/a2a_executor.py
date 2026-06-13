"""Optional A2A executor integration for gcp-finops-agent.

Enables gcp-finops-agent to delegate cleanup or action requests to a configured
downstream executor agent via Vertex AI Reasoning Engine A2A.

Configure via environment variables:
    A2A_EXECUTOR_ENABLED=true
    A2A_EXECUTOR_RESOURCE_NAME=projects/.../reasoningEngines/...

When disabled (the default), both tools return a clear message explaining
that no executor is configured. No remote call is ever attempted.
See docs/A2A_SETUP.md for setup instructions.
"""

import logging
from typing import Any

from vertexai.preview import reasoning_engines

from .config import get_config

logger = logging.getLogger(__name__)

_NOT_CONFIGURED: dict[str, Any] = {
    "status": "disabled",
    "message": (
        "No executor agent is configured. To enable A2A action delegation, set "
        "A2A_EXECUTOR_ENABLED=true and A2A_EXECUTOR_RESOURCE_NAME to your "
        "executor agent's Reasoning Engine resource name. "
        "See docs/A2A_SETUP.md for setup instructions."
    ),
}


async def delegate_action(
    resources: list[dict[str, Any]],
    justification: str,
    priority: str = "medium"
) -> dict[str, Any]:
    """Delegate a list of resources to the configured executor agent for action.

    Passes a structured list of resources and a FinOps justification to a
    downstream executor agent. The executor is responsible for deciding how
    to act on each resource (delete, stop, rightsize, etc.) and reporting
    back.

    Args:
        resources: List of resources to act on. Each resource should contain:
                  - resource_type: Type (e.g., "compute_instance", "storage_bucket")
                  - resource_id: Resource identifier
                  - project_id: GCP project ID
                  - region or zone: Location (if applicable)
                  - estimated_monthly_cost: Cost in USD
                  - recommendation: Suggested action (e.g., "delete", "downgrade")
        justification: FinOps analysis explaining why action is recommended.
        priority: Action priority — "low", "medium", or "high".

    Returns:
        Dictionary containing:
        - status: "success", "error", or "disabled"
        - resources_processed: Number of resources sent to executor
        - executor_response: Text response from the executor agent
        - error: Error message if status is "error"
    """
    config = get_config()
    if not config.a2a_executor_enabled or not config.a2a_executor_resource_name:
        return _NOT_CONFIGURED

    if not resources:
        return {
            "status": "error",
            "error": "No resources provided for action",
            "resources_processed": 0,
        }

    try:
        executor = reasoning_engines.ReasoningEngine(config.a2a_executor_resource_name)

        resource_lines = []
        for i, res in enumerate(resources, 1):
            res_type = res.get("resource_type", "unknown")
            res_id = res.get("resource_id", "unknown")
            cost = res.get("estimated_monthly_cost", 0)
            action = res.get("recommendation", "review")
            project = res.get("project_id", "unknown")
            location = res.get("zone") or res.get("region", "unknown")
            resource_lines.append(
                f"{i}. {res_type}: {res_id}\n"
                f"   Project: {project}\n"
                f"   Location: {location}\n"
                f"   Cost: ${cost:.2f}/month\n"
                f"   Action: {action}"
            )

        request_text = (
            f"FinOps Action Request\n\n"
            f"Priority: {priority.upper()}\n\n"
            f"Resources:\n{chr(10).join(resource_lines)}\n\n"
            f"Justification:\n{justification}\n\n"
            f"Instructions:\n"
            f"1. Review each resource and confirm it is safe to act on\n"
            f"2. Execute the recommended action for each resource\n"
            f"3. Report back: what was done, what was skipped, and why\n"
            f"4. If an action fails, continue with remaining resources\n"
        )

        response = await executor.query(input=request_text)
        executor_response = response.get("output", str(response)) if isinstance(response, dict) else str(response)

        return {
            "status": "success",
            "resources_processed": len(resources),
            "executor_response": executor_response,
            "priority": priority,
        }

    except Exception:
        logger.exception("delegate_action failed")
        return {
            "status": "error",
            "error": "Executor call failed. Check logs for details.",
            "resources_processed": 0,
            "executor_response": None,
        }


async def check_executor_capabilities(resource_types: list[str]) -> dict[str, Any]:
    """Query the executor agent for its supported resource types and actions.

    Use this before delegating to verify the executor can handle the resource
    types gcp-finops-agent has identified.

    Args:
        resource_types: List of resource types to check
                        (e.g., ["compute_instance", "storage_bucket"]).

    Returns:
        Dictionary containing:
        - status: "success", "error", or "disabled"
        - resource_types_queried: Input list
        - capabilities: Text describing what the executor supports
        - error: Error message if status is "error"
    """
    config = get_config()
    if not config.a2a_executor_enabled or not config.a2a_executor_resource_name:
        return _NOT_CONFIGURED

    try:
        executor = reasoning_engines.ReasoningEngine(config.a2a_executor_resource_name)

        type_list = "\n".join(f"- {rt}" for rt in resource_types)
        query = (
            f"What are your capabilities for the following GCP resource types?\n\n"
            f"{type_list}\n\n"
            f"For each type: can you act on it, what actions do you support, "
            f"and what safety checks do you perform? Be concise."
        )

        response = await executor.query(input=query)
        capabilities = response.get("output", str(response)) if isinstance(response, dict) else str(response)

        return {
            "status": "success",
            "resource_types_queried": resource_types,
            "capabilities": capabilities,
        }

    except Exception:
        logger.exception("check_executor_capabilities failed")
        return {
            "status": "error",
            "error": "Executor call failed. Check logs for details.",
            "capabilities": None,
        }
