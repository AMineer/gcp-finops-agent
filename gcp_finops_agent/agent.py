"""ADK agent definition for gcp-finops-agent."""

import os
from google.adk.agents import Agent

from .tools import (
    query_spend,
    forecast_spend,
    query_resources,
    lookup_resource,
    get_recommendations,
    generate_report,
    inspect_gcs_storage,
)
from .config import get_config
from .prompts import build_instruction


# ADK discovers this `root_agent` variable automatically
config = get_config()

# Ensure ADK + google-genai use Vertex AI with ADC credentials by default.
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
if config.gcp_project_id:
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", config.gcp_project_id)
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", config.gcp_location)

_tools = [
    query_spend,
    forecast_spend,
    query_resources,
    lookup_resource,
    get_recommendations,
    generate_report,
    inspect_gcs_storage,
]

# A2A executor tools are optional — only registered when explicitly enabled.
if config.a2a_executor_enabled:
    from .a2a_executor import delegate_action, check_executor_capabilities
    _tools.extend([delegate_action, check_executor_capabilities])

root_agent = Agent(
    name="gcp-finops-agent",
    model=config.gemini_model,
    description="GCP FinOps agent for spend analysis, cost optimization, and savings recommendations",
    instruction=build_instruction,  # Callable - evaluates date per-request
    tools=_tools,
)
