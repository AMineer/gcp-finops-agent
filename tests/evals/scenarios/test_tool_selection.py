"""Tool selection behavioral evals.

Priority: 2
Rationale: Foundational behavior - picking the wrong tool breaks everything downstream.

Tests that the agent correctly chooses between query_spend, query_resources,
lookup_resource, forecast_spend, and get_recommendations based on question type.
"""

import pytest
from tests.evals.fixtures.tool_responses import (
    APRIL_2026_SPEND,
    APRIL_2026_RESOURCES,
    MAY_2026_FORECAST,
    RECOMMENDATIONS_HIGH_SAVINGS,
)
from tests.evals.assertions import (
    assert_tool_called,
    assert_tool_not_called,
    assert_response_contains,
)


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.parametrize('mock_gcp', [
    {'query_spend': APRIL_2026_SPEND}
], indirect=True)
async def test_summary_question_uses_query_spend(runner, mock_gcp, freeze_time):
    """Summary cost questions should use query_spend, NOT query_resources.

    Regression test: query_resources is more expensive and unnecessary for totals.
    """
    freeze_time()  # May 7, 2026

    events = await runner.run_debug("What was our total spend last month?")

    # Should use query_spend for summary
    assert_tool_called(events, "query_spend", min_calls=1)

    # Should NOT use the more expensive query_resources
    assert_tool_not_called(events, "query_resources")

    # Response should mention the total
    assert_response_contains(events, "45,230")


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.parametrize('mock_gcp', [
    {'query_resources': APRIL_2026_RESOURCES}
], indirect=True)
async def test_resource_question_uses_query_resources(runner, mock_gcp, freeze_time):
    """Resource-specific questions should use query_resources for granular data.

    When user asks about individual resources, we need resource-level detail.
    """
    freeze_time()  # May 7, 2026

    events = await runner.run_debug("What are our top compute instances by cost last month?")

    # Should use query_resources for resource breakdown
    assert_tool_called(events, "query_resources", min_calls=1)

    # Response should mention specific instance names
    assert_response_contains(events, "instance-worker-pool")


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.parametrize('mock_gcp', [
    {
        'query_spend': APRIL_2026_SPEND,
    }
], indirect=True)
async def test_investigation_uses_lookup_resource(runner, mock_gcp, freeze_time):
    """Service-level investigation uses drill-down methodology.

    With new methodology: Uses query_spend with service filter (Tier 3 SKU breakdown)
    for service-level investigations. More efficient than lookup_resource.
    """
    freeze_time()  # May 7, 2026

    events = await runner.run_debug("Tell me more about our BigQuery costs last month")

    # Should use query_spend with service filter for Tier 3 breakdown
    assert_tool_called(events, "query_spend", min_calls=1)

    # Response should mention BigQuery
    assert_response_contains(events, "BigQuery")


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.parametrize('mock_gcp', [
    {'forecast_spend': MAY_2026_FORECAST}
], indirect=True)
async def test_forecast_question_uses_forecast_spend(runner, mock_gcp, freeze_time):
    """Forecast questions should use forecast_spend, not query_spend.

    When user asks about projections/forecasts, use the dedicated forecast tool.
    """
    freeze_time()  # May 7, 2026

    events = await runner.run_debug("What's our projected spend for this month?")

    # Should use forecast_spend for projections
    assert_tool_called(events, "forecast_spend", min_calls=1)

    # Should NOT use query_spend (that's historical data)
    assert_tool_not_called(events, "query_spend")

    # Response should mention forecast/projected
    assert_response_contains(events, "53,800", "forecast")


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.parametrize('mock_gcp', [
    {'get_recommendations': RECOMMENDATIONS_HIGH_SAVINGS}
], indirect=True)
async def test_savings_question_uses_recommendations(runner, mock_gcp, freeze_time):
    """Savings optimization questions should use get_recommendations.

    When user asks about cost savings or optimization, use the recommendations tool.
    """
    freeze_time()  # May 7, 2026

    events = await runner.run_debug("How can we reduce costs?")

    # Should use get_recommendations for optimization
    assert_tool_called(events, "get_recommendations", min_calls=1)

    # Response should mention savings opportunities
    assert_response_contains(events, "idle", "savings")
