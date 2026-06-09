"""Deploy gcp-finops-agent ADK agent to Vertex AI Agent Engine.

Usage:
    python deploy/agent_engine_deploy.py --create
    python deploy/agent_engine_deploy.py --update --resource-name projects/.../reasoningEngines/...

Required environment variables:
    GCP_PROJECT_ID
    GCP_LOCATION (default: us-central1)
    AGENT_ENGINE_STAGING_BUCKET (gs://...)

Required Secret Manager secrets:
    GCP_PROJECT_SCOPE
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import vertexai
from google.cloud import secretmanager
from vertexai.preview import reasoning_engines

from gcp_finops_agent import root_agent
from gcp_finops_agent.config import get_config


def _fetch_secret(project_id: str, secret_name: str) -> str:
    """Fetch a secret value from Secret Manager.

    Args:
        project_id: GCP project ID containing the secret.
        secret_name: Name of the secret to fetch.

    Returns:
        The secret value as a string.
    """
    client = secretmanager.SecretManagerServiceClient()
    secret_path = f"projects/{project_id}/secrets/{secret_name}/versions/latest"

    try:
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch secret {secret_name}: {e}")


def _get_runtime_env_vars(project_id: str) -> dict[str, str]:
    """Fetch runtime environment variables from Secret Manager.

    Args:
        project_id: GCP project ID containing the secrets.

    Returns:
        Dictionary of environment variables for the Agent Engine runtime.
    """
    secrets = {
        "GCP_PROJECT_SCOPE": _fetch_secret(project_id, "GCP_PROJECT_SCOPE"),
    }

    # Add project ID and location (these are derived from deployment context)
    config = get_config()
    secrets["GCP_PROJECT_ID"] = project_id
    secrets["GCP_LOCATION"] = config.gcp_location
    secrets["GOOGLE_GENAI_USE_VERTEXAI"] = "true"

    return secrets


def _build_adk_app() -> reasoning_engines.AdkApp:
    """Create an ADK app wrapper for Agent Engine."""

    return reasoning_engines.AdkApp(
        agent=root_agent,
        enable_tracing=True,
    )


def _requirements() -> list[str]:
    """Pinned runtime requirements for Agent Engine execution."""

    return [
        "google-adk>=1.0.0",
        "google-cloud-aiplatform>=1.76.0",
        "google-cloud-bigquery>=3.25.0",
        "google-cloud-monitoring>=2.21.0",
        "google-cloud-recommender>=2.16.0",
        "google-cloud-storage>=2.18.0",
        "pandas>=2.2.0",
        "db-dtypes>=1.3.0",
        "pydantic>=2.8.0",
        "pydantic-settings>=2.4.0",
    ]


def create_engine(staging_bucket: str, project_id: str) -> str:
    """Create a new Reasoning Engine and return its resource name.

    Args:
        staging_bucket: GCS bucket for staging deployment artifacts.
        project_id: GCP project ID for fetching secrets.

    Returns:
        The resource name of the created Reasoning Engine.
    """
    env_vars = _get_runtime_env_vars(project_id)

    app = reasoning_engines.ReasoningEngine.create(
        _build_adk_app(),
        requirements=_requirements(),
        display_name="gcp-finops-agent",
        staging_bucket=staging_bucket,
        extra_packages=[str(Path(__file__).resolve().parents[1] / "gcp_finops_agent")],
        env_vars=env_vars,
    )
    return app.resource_name


def update_engine(resource_name: str, staging_bucket: str, project_id: str) -> str:
    """Update an existing Reasoning Engine and return its resource name.

    Args:
        resource_name: Existing Reasoning Engine resource name.
        staging_bucket: GCS bucket for staging deployment artifacts.
        project_id: GCP project ID for fetching secrets.

    Returns:
        The resource name of the updated Reasoning Engine.
    """
    env_vars = _get_runtime_env_vars(project_id)

    app = reasoning_engines.ReasoningEngine(resource_name)
    app.update(
        _build_adk_app(),
        requirements=_requirements(),
        staging_bucket=staging_bucket,
        extra_packages=[str(Path(__file__).resolve().parents[1] / "gcp_finops_agent")],
        env_vars=env_vars,
    )
    return resource_name


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy gcp-finops-agent to Vertex AI Agent Engine")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--create", action="store_true", help="Create a new Agent Engine deployment")
    mode.add_argument("--update", action="store_true", help="Update an existing Agent Engine deployment")
    parser.add_argument(
        "--resource-name",
        help="Required with --update, format: projects/.../locations/.../reasoningEngines/...",
    )
    args = parser.parse_args()

    config = get_config()
    project_id = config.gcp_project_id
    location = config.gcp_location
    staging_bucket = os.environ.get("AGENT_ENGINE_STAGING_BUCKET", "")

    if not staging_bucket:
        raise ValueError("AGENT_ENGINE_STAGING_BUCKET must be set (example: gs://my-agent-engine-staging)")

    if args.update and not args.resource_name:
        raise ValueError("--resource-name is required with --update")

    vertexai.init(project=project_id, location=location)

    if args.create:
        resource_name = create_engine(staging_bucket, project_id)
        print(f"Created Reasoning Engine: {resource_name}")
    else:
        resource_name = update_engine(args.resource_name, staging_bucket, project_id)
        print(f"Updated Reasoning Engine: {resource_name}")


if __name__ == "__main__":
    main()
