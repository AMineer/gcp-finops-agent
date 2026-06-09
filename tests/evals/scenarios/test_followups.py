"""Follow-up suggestion behavioral evals.

Priority: 7
Rationale: Tests conversational flow - good follow-ups guide multi-step investigations.

Tests that after answering questions, the agent suggests relevant, contextual
follow-up questions that help users continue their investigation.
"""

import pytest
from tests.evals.fixtures.tool_responses import (
    APRIL_2026_SPEND,
    APRIL_2026_RESOURCES,
    MAY_2026_FORECAST,
    RECOMMENDATIONS_HIGH_SAVINGS,
)
from tests.evals.assertions import (
    assert_suggests_followup,
)


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.parametrize('mock_gcp', [
    {'query_spend': APRIL_2026_SPEND}
], indirect=True)
async def test_spend_answer_suggests_drill_down(runner, mock_gcp, freeze_time):
    """After showing spend summary, should suggest drilling into details.

    Natural follow-up: breakdown by service, project, or resource.
    """
    freeze_time()  # May 7, 2026

    events = await runner.run_debug("What was our spend last month?")

    # Should suggest a follow-up
    assert_suggests_followup(events)

    # Follow-up should relate to drilling down
    # Common patterns: "breakdown", "which service", "top", "details"
    response_text = events[-1].content.parts[0].text.lower()

    drill_down_patterns = [
        "breakdown",
        "which",
        "top",
        "service",
        "project",
        "resource",
    ]

    has_drill_down = any(pattern in response_text for pattern in drill_down_patterns)

    assert has_drill_down, (
        "Follow-up should suggest drilling into spend details"
    )


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.parametrize('mock_gcp', [
    {'query_resources': APRIL_2026_RESOURCES}
], indirect=True)
async def test_high_cost_resource_suggests_optimization(runner, mock_gcp, freeze_time):
    """After showing high-cost resources, should suggest optimization check.

    Natural follow-up: check for recommendations or investigate usage.
    """
    freeze_time()  # May 7, 2026

    events = await runner.run_debug("Show me our top Compute Engine costs")

    # Should suggest a follow-up
    assert_suggests_followup(events)

    # Follow-up should relate to optimization or investigation
    response_text = events[-1].content.parts[0].text.lower()

    optimization_patterns = [
        "recommendation",
        "optimize",
        "reduce",
        "save",
        "usage",
        "detail",
    ]

    has_optimization = any(pattern in response_text for pattern in optimization_patterns)

    assert has_optimization, (
        "Follow-up after high costs should suggest optimization or investigation"
    )


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.parametrize('mock_gcp', [
    {'forecast_spend': MAY_2026_FORECAST}
], indirect=True)
async def test_forecast_suggests_comparison(runner, mock_gcp, freeze_time):
    """After showing forecast, should suggest relevant follow-up action.

    With new methodology: May suggest drilling into top services, comparing to
    actuals, or investigating cost drivers.
    """
    freeze_time()  # May 7, 2026

    events = await runner.run_debug("What's our May forecast?")

    # Should suggest a follow-up
    assert_suggests_followup(events)

    # Follow-up should relate to comparison, investigation, or drill-down
    response_text = events[-1].content.parts[0].text.lower()

    comparison_patterns = [
        "compare",
        "last month",
        "april",
        "trend",
        "driving",
        "breakdown",
        "drill",  # New methodology uses "drill into" for tier-based analysis
        "spend",  # "drill into X spend"
        "optimize",  # "identify optimizations"
    ]

    has_comparison = any(pattern in response_text for pattern in comparison_patterns)

    assert has_comparison, (
        "Follow-up after forecast should suggest comparison, breakdown, or drill-down"
    )


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.parametrize('mock_gcp', [
    {'get_recommendations': RECOMMENDATIONS_HIGH_SAVINGS}
], indirect=True)
async def test_recommendations_suggest_implementation(runner, mock_gcp, freeze_time):
    """After showing recommendations, should suggest next steps for acting on them.

    Natural follow-up: get details on a specific recommendation or estimate impact.
    """
    freeze_time()  # May 7, 2026

    events = await runner.run_debug("What cost optimization opportunities do we have?")

    # Should suggest a follow-up
    assert_suggests_followup(events)

    # Follow-up should relate to taking action or getting details
    response_text = events[-1].content.parts[0].text.lower()

    action_patterns = [
        "which",
        "detail",
        "more about",
        "implement",
        "prioritize",
        "focus",
    ]

    has_action = any(pattern in response_text for pattern in action_patterns)

    assert has_action, (
        "Follow-up after recommendations should suggest next steps or details"
    )


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.parametrize('mock_gcp', [
    {'query_spend': APRIL_2026_SPEND}
], indirect=True)
async def test_followup_is_contextual_not_generic(runner, mock_gcp, freeze_time):
    """Follow-up suggestions should be specific to the data, not generic.

    Should reference actual services/projects from the response, not just 'want more?'
    """
    freeze_time()  # May 7, 2026

    events = await runner.run_debug("Break down last month's costs by service")

    response_text = events[-1].content.parts[0].text

    # Should mention at least one service from the actual data
    services_in_data = ["Compute Engine", "BigQuery", "Cloud Storage", "Cloud SQL"]
    mentions_actual_service = any(svc in response_text for svc in services_in_data)

    assert mentions_actual_service, (
        "Follow-up should reference actual data (services, projects) not be generic"
    )

    # Should suggest a follow-up
    assert_suggests_followup(events)
