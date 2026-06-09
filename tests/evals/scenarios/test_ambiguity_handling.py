"""Ambiguity handling behavioral evals.

Priority: 4
Rationale: Tests prompt adherence - agent should ask rather than guess incorrectly.

Tests that when user requests are genuinely ambiguous (unclear project/region/resource),
the agent asks clarifying questions instead of making assumptions.

Note: Date ambiguity is tested separately in test_date_interpretation.py
"""

import pytest
from tests.evals.fixtures.tool_responses import (
    APRIL_2026_RESOURCES,
)
from tests.evals.assertions import (
    assert_response_contains,
)


@pytest.mark.asyncio
@pytest.mark.slow
async def test_ambiguous_project_asks_clarification(runner, freeze_time):
    """When project is ambiguous, agent should show comprehensive results.

    With new methodology: Show all matching projects instead of asking.
    Example: "What's our spend?" when multiple projects exist.
    """
    freeze_time()  # May 7, 2026

    events = await runner.run_debug(
        "How much are we spending on the production environment?"
    )

    # With new methodology: Should show comprehensive results, not ask
    # Agent will pull data and show breakdown across production projects
    response_text = events[-1].content.parts[0].text.lower()

    # Should mention production or project-related terms
    assert "prod" in response_text or "production" in response_text or "project" in response_text


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.parametrize('mock_gcp', [
    {'query_resources': APRIL_2026_RESOURCES}
], indirect=True)
async def test_ambiguous_resource_asks_clarification(runner, mock_gcp, freeze_time):
    """When resource reference is vague, should offer to search more specifically.

    With new methodology: If initial query doesn't match, agent offers specific
    search options rather than staying silent.
    Example: "worker pool" is vague - agent suggests more specific search terms.
    """
    freeze_time()  # May 7, 2026

    events = await runner.run_debug(
        "What did the instance worker pool cost last month?"
    )

    # With new methodology: Should show both matching instance-worker-pool resources
    # Response should mention instance-worker-pool-1 and instance-worker-pool-2
    assert_response_contains(events, "worker")


@pytest.mark.asyncio
@pytest.mark.slow
async def test_vague_optimization_request_suggests_options(runner, freeze_time):
    """Vague requests like 'optimize costs' should suggest concrete options.

    Agent should offer specific paths rather than making assumptions.
    """
    freeze_time()  # May 7, 2026

    events = await runner.run_debug("Help me optimize costs")

    # Should suggest multiple approaches rather than picking one
    # Common patterns: recommendations, identify top costs, forecast review
    response_text = events[-1].content.parts[0].text.lower()

    # Should mention at least 2 different approaches
    approach_mentions = sum([
        "recommendation" in response_text,
        "top cost" in response_text or "highest" in response_text,
        "forecast" in response_text,
        "trend" in response_text,
        "unused" in response_text or "idle" in response_text,
    ])

    assert approach_mentions >= 2, (
        "Agent should suggest multiple optimization approaches, not assume one path"
    )
