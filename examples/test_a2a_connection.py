#!/usr/bin/env python3
"""
Test script to verify A2A connectivity between gcp-finops-agent and a downstream executor agent.

This script requires a separately deployed executor agent (Reasoning Engine)
that is NOT part of this repository.

Prerequisites:
- gcp-finops-agent deployed to Vertex AI Agent Engine
- Executor agent deployed separately with A2A permissions configured
  (see deploy/setup-a2a-permissions.sh and docs/A2A_SETUP.md)
- A2A_EXECUTOR_RESOURCE_NAME environment variable set
- Authenticated with appropriate GCP credentials

Usage:
    export A2A_EXECUTOR_RESOURCE_NAME="projects/your-project-id/locations/us-central1/reasoningEngines/YOUR_ENGINE_ID"
    python examples/test_a2a_connection.py
"""

import asyncio
import os
import sys
from datetime import datetime

from vertexai.preview import reasoning_engines


def print_header(text: str) -> None:
    """Print a formatted header"""
    print("\n" + "=" * 70)
    print(f" {text}")
    print("=" * 70)


def print_step(step_num: int, text: str) -> None:
    """Print a test step"""
    print(f"\n[{step_num}] {text}")


def print_success(text: str) -> None:
    """Print success message"""
    print(f"✓ {text}")


def print_error(text: str) -> None:
    """Print error message"""
    print(f"✗ {text}", file=sys.stderr)


async def test_basic_connectivity(executor_resource_name: str) -> bool:
    """Test basic connectivity to the executor agent."""
    print_step(1, "Testing basic connectivity to executor agent...")

    try:
        reasoning_engines.ReasoningEngine(executor_resource_name)
        print_success("Executor Reasoning Engine initialized")
        return True
    except Exception as e:
        print_error(f"Failed to initialize executor agent: {e}")
        return False


async def test_simple_query(executor_resource_name: str) -> bool:
    """Test a simple query to the executor agent."""
    print_step(2, "Sending simple test query to executor agent...")

    try:
        executor = reasoning_engines.ReasoningEngine(executor_resource_name)

        query = "What types of GCP resources can you act on?"
        print(f"   Query: '{query}'")

        response = await executor.query(input=query)

        if isinstance(response, dict):
            response_text = response.get("output", str(response))
        else:
            response_text = str(response)

        print(f"   Response preview: {response_text[:200]}...")

        action_keywords = ["resource", "delete", "clean", "compute", "storage", "action"]
        found = any(kw in response_text.lower() for kw in action_keywords)

        if found:
            print_success("Executor agent responded to capability query")
            return True
        else:
            print_error("Executor agent response did not mention expected keywords")
            print(f"   Full response: {response_text}")
            return False

    except Exception as e:
        print_error(f"Failed to query executor agent: {e}")
        return False


async def test_action_request(executor_resource_name: str) -> bool:
    """Test a delegation request to the executor agent."""
    print_step(3, "Testing action delegation request...")

    try:
        executor = reasoning_engines.ReasoningEngine(executor_resource_name)

        query = """FinOps Action Request

Priority: MEDIUM

Resources:
1. compute_instance: test-vm-idle-123
   Project: test-project
   Location: us-central1-a
   Cost: $156.00/month
   Action: delete

Justification:
This VM has <5% CPU utilization for 30 days and costs $156/month.
Zero active connections and no recent disk I/O detected.

Instructions:
This is a TEST request. Acknowledge receipt and describe the safety
checks you would perform before deletion. DO NOT delete anything.
"""
        print("   Query: Test action delegation request")

        response = await executor.query(input=query)

        if isinstance(response, dict):
            response_text = response.get("output", str(response))
        else:
            response_text = str(response)

        print(f"   Response length: {len(response_text)} characters")
        print(f"   Response preview: {response_text[:300]}...")

        ack_keywords = ["cleanup", "safety", "check", "delete", "test", "acknowledge"]
        found_keywords = [kw for kw in ack_keywords if kw.lower() in response_text.lower()]

        if found_keywords:
            print_success(f"Executor acknowledged request (keywords: {', '.join(found_keywords)})")
            return True
        else:
            print_error("Executor response did not acknowledge the request")
            print(f"   Full response: {response_text}")
            return False

    except Exception as e:
        print_error(f"Failed action request: {e}")
        return False


async def test_error_handling() -> bool:
    """Test error handling with invalid resource name."""
    print_step(4, "Testing error handling with invalid resource name...")

    try:
        invalid_resource = "projects/invalid/locations/invalid/reasoningEngines/99999"
        agent = reasoning_engines.ReasoningEngine(invalid_resource)
        await agent.query(input="test")
        print_error("Expected an error but query succeeded - this is unexpected")
        return False

    except Exception as e:
        print_success(f"Error handling works correctly: {type(e).__name__}")
        return True


async def main():
    """Run all A2A connectivity tests."""
    print_header("gcp-finops-agent A2A Executor Connection Test")

    executor_resource_name = os.getenv("A2A_EXECUTOR_RESOURCE_NAME")

    if not executor_resource_name or "YOUR_ENGINE_ID" in executor_resource_name:
        print_error("A2A_EXECUTOR_RESOURCE_NAME environment variable not set correctly")
        print("\nSet it to your executor agent's Reasoning Engine resource name:")
        print("  export A2A_EXECUTOR_RESOURCE_NAME='projects/your-project-id/locations/us-central1/reasoningEngines/YOUR_ENGINE_ID'")
        print("\nTo list deployed Reasoning Engines, run:")
        print("  gcloud ai reasoning-engines list --project=your-project-id --region=us-central1")
        sys.exit(1)

    print(f"\nExecutor Resource Name: {executor_resource_name}")
    print(f"Test Time: {datetime.now().isoformat()}")

    results = []

    results.append(("Basic Connectivity", await test_basic_connectivity(executor_resource_name)))

    if results[-1][1]:
        results.append(("Simple Query", await test_simple_query(executor_resource_name)))
        results.append(("Action Request", await test_action_request(executor_resource_name)))

    results.append(("Error Handling", await test_error_handling()))

    print_header("Test Summary")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} | {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\nAll tests passed! A2A communication is working correctly.")
        print("\nNext steps:")
        print("  1. Set A2A_EXECUTOR_ENABLED=true and A2A_EXECUTOR_RESOURCE_NAME in gcp-finops-agent's environment")
        print("  2. Monitor A2A invocations in Cloud Logging")
        return 0
    else:
        print("\nSome tests failed. Review the errors above.")
        print("\nCommon issues:")
        print("  - IAM permissions not configured (run deploy/setup-a2a-permissions.sh)")
        print("  - Executor agent resource name incorrect")
        print("  - Executor agent not deployed or not responding")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
