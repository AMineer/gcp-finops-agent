"""Response format compliance behavioral evals.

Priority: 5
Rationale: Tests adherence to response formatting guidelines in prompt.

Tests that responses follow formatting requirements:
- Markdown tables for structured data
- Currency mentions
- Appropriate response length
- Follow-up suggestions for conversational flow
"""

import pytest
from tests.evals.fixtures.tool_responses import (
    APRIL_2026_SPEND,
    APRIL_2026_RESOURCES,
    MAY_2026_FORECAST,
    RECOMMENDATIONS_HIGH_SAVINGS,
)
from tests.evals.assertions import (
    assert_uses_markdown_table,
    assert_mentions_currency,
    assert_suggests_followup,
    assert_response_contains,
    assert_response_length,
)


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.parametrize('mock_gcp', [
    {'query_spend': APRIL_2026_SPEND}
], indirect=True)
async def test_spend_breakdown_uses_table(runner, mock_gcp, freeze_time):
    """Service breakdown should be presented in markdown table format.

    Tables make structured data easier to scan than prose.
    """
    freeze_time()  # May 7, 2026

    events = await runner.run_debug(
        "Show me a breakdown of last month's spending by service"
    )

    # Should use markdown table
    assert_uses_markdown_table(events)

    # Should mention services from the data
    assert_response_contains(events, "Compute Engine", "BigQuery", "Cloud Storage")


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.parametrize('mock_gcp', [
    {'query_resources': APRIL_2026_RESOURCES}
], indirect=True)
async def test_resource_list_uses_table(runner, mock_gcp, freeze_time):
    """Resource listings should be in table format for easy comparison.

    Multiple resources with costs are tabular data.
    """
    freeze_time()  # May 7, 2026

    events = await runner.run_debug(
        "List our Compute Engine instances and their costs from last month"
    )

    # Should use markdown table
    assert_uses_markdown_table(events)

    # Should show instance names and costs
    assert_response_contains(events, "instance-worker-pool")


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.parametrize('mock_gcp', [
    {'query_spend': APRIL_2026_SPEND}
], indirect=True)
async def test_cost_response_mentions_currency(runner, mock_gcp, freeze_time):
    """Cost figures should include currency information.

    Avoids ambiguity about which currency costs are in.
    """
    freeze_time()  # May 7, 2026

    events = await runner.run_debug("What was our total spend last month?")

    # Should mention USD (our test data currency)
    assert_mentions_currency(events, "USD")


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.parametrize('mock_gcp', [
    {'get_recommendations': RECOMMENDATIONS_HIGH_SAVINGS}
], indirect=True)
async def test_recommendations_use_table(runner, mock_gcp, freeze_time):
    """Recommendations should be in table format for easy review.

    Each recommendation has multiple attributes (resource, savings, priority).
    """
    freeze_time()  # May 7, 2026

    events = await runner.run_debug("What are our cost optimization opportunities?")

    # Should use markdown table for recommendations
    assert_uses_markdown_table(events)

    # Should mention savings amounts
    assert_response_contains(events, "4,250", "2,100")


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.parametrize('mock_gcp', [
    {'forecast_spend': MAY_2026_FORECAST}
], indirect=True)
async def test_simple_query_is_concise(runner, mock_gcp, freeze_time):
    """Simple queries should follow structured format but remain reasonable.

    With new methodology: Responses follow OUTPUT_FORMAT (headline, tables,
    observations, optimization angles), which is longer but more valuable.
    """
    freeze_time()  # May 7, 2026

    events = await runner.run_debug("What's our May forecast?")

    # With structured format, allow up to 1200 chars for:
    # - Headline net total
    # - Service breakdown table (if applicable)
    # - Observations
    # - Optimization angles
    # But still flag if it becomes a novel (>1500 chars)
    assert_response_length(events, max_length=1500)

    # Should mention the forecast amount
    assert_response_contains(events, "53,800")


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.parametrize('mock_gcp', [
    {'query_spend': APRIL_2026_SPEND}
], indirect=True)
async def test_conversational_response_suggests_followup(runner, mock_gcp, freeze_time):
    """Conversational responses should suggest relevant follow-ups.

    Helps guide users through multi-step investigations.
    """
    freeze_time()  # May 7, 2026

    events = await runner.run_debug("What did we spend last month?")

    # Should suggest a logical next step
    assert_suggests_followup(events)
