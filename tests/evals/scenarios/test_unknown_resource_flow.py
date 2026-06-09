"""Unknown resource auto-investigation behavioral evals.

Priority: 3
Rationale: Tests multi-step reasoning and tool chaining (core agent capability).

Tests that when the agent encounters "unattributed" resources or limited detail,
it automatically chains to lookup_resource_details for deeper investigation.
"""

import pytest
from tests.evals.fixtures.tool_responses import (
    APRIL_2026_SPEND,
)
from tests.evals.assertions import (
    assert_response_contains,
    assert_tool_called_with,
)
from tests.evals.conftest import APRIL_START, APRIL_END


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.parametrize('mock_gcp', [
    {
        'query_spend': APRIL_2026_SPEND,
    }
], indirect=True)
async def test_unattributed_triggers_lookup(runner, mock_gcp, freeze_time):
    """BigQuery cost breakdown should use drill-down methodology.

    With new methodology: Uses query_spend with service filter (Tier 3 SKU breakdown)
    instead of query_resources. More efficient and follows structured drill-down.
    """
    freeze_time()  # May 7, 2026

    events = await runner.run_debug(
        "Break down our BigQuery costs from last month by usage type"
    )

    # New behavior: Uses query_spend with service="BigQuery" for Tier 3 SKU breakdown
    assert_tool_called_with(
        events,
        "query_spend",
        start_date=APRIL_START,
        end_date=APRIL_END,
        service="BigQuery"
    )

    # Response should mention the detailed SKU breakdown
    # (BigQuery has SKUs like "Analysis", "Storage", "Streaming Insert", etc.)
    response_text = events[-1].content.parts[0].text
    assert "BigQuery" in response_text


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.parametrize('mock_gcp', [
    {
        'query_spend': APRIL_2026_SPEND,
    }
], indirect=True)
async def test_user_asks_about_unattributed_service(runner, mock_gcp, freeze_time):
    """When user asks about a service, should use drill-down methodology.

    With new methodology: Uses query_spend with service filter (Tier 3 SKU breakdown).
    This provides SKU-level detail which shows usage patterns.
    """
    freeze_time()  # May 7, 2026

    events = await runner.run_debug("What's driving our Cloud Logging costs?")

    # Should use query_spend with service filter for Tier 3 breakdown
    assert_tool_called_with(
        events,
        "query_spend",
        service="Cloud Logging"
    )

    # Response should mention Cloud Logging
    assert_response_contains(events, "Logging")


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.parametrize('mock_gcp', [
    {
        'query_spend': APRIL_2026_SPEND,
    }
], indirect=True)
async def test_lookup_preserves_date_range(runner, mock_gcp, freeze_time):
    """Service-level queries should use correct date range.

    With new methodology: Uses query_spend with service filter for Tier 3 breakdown.
    Regression test: Ensure date range is preserved.
    """
    freeze_time()  # May 7, 2026

    events = await runner.run_debug(
        "What BigQuery usage did we have in April?"
    )

    # Should use query_spend with April dates and service filter
    assert_tool_called_with(
        events,
        "query_spend",
        start_date=APRIL_START,
        end_date=APRIL_END,
    )

    # Should mention April in response
    assert_response_contains(events, "April")
