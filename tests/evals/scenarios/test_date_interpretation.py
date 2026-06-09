"""Date interpretation behavioral evals.

Priority: 1 (highest)
Rationale: Most novel behavior, recently fixed bug, silent failure mode.

Tests the hybrid MTD/previous-month dual-query behavior that is core to the prompt.
"""

import pytest
from tests.evals.fixtures.tool_responses import (
    APRIL_2026_SPEND,
    MAY_2026_MTD_SPEND,
)
from tests.evals.assertions import (
    assert_tool_called_with,
    assert_dual_query,
    assert_response_contains,
)
from tests.evals.conftest import APRIL_START, APRIL_END, MAY_START, MAY_MTD_END


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.parametrize('mock_gcp', [
    {'query_spend': APRIL_2026_SPEND}
], indirect=True)
async def test_last_month_unambiguous(runner, mock_gcp, freeze_time):
    """When user says 'last month', should query only previous complete month.

    Regression test: Ensures we don't trigger dual-query for unambiguous requests.
    """
    freeze_time()  # May 7, 2026

    events = await runner.run_debug("What did we spend last month?")

    # Should call query_spend exactly once with April dates
    assert_tool_called_with(
        events,
        "query_spend",
        start_date=APRIL_START,
        end_date=APRIL_END,
    )

    # Should NOT make duplicate call
    assert mock_gcp['query_spend'].call_count == 1

    # Response should mention April and the cost
    assert_response_contains(events, "April", "45,230")


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.parametrize('mock_gcp', [
    {'query_spend': MAY_2026_MTD_SPEND}
], indirect=True)
async def test_this_month_unambiguous(runner, mock_gcp, freeze_time):
    """When user says 'this month', should query only current MTD.

    Regression test: This was broken before - used to return previous month.
    """
    freeze_time()  # May 7, 2026

    events = await runner.run_debug("What did we spend this month?")

    # Should call query_spend exactly once with May MTD dates
    assert_tool_called_with(
        events,
        "query_spend",
        start_date=MAY_START,
        end_date=MAY_MTD_END,
    )

    # Should NOT make duplicate call
    assert mock_gcp['query_spend'].call_count == 1

    # Response should mention May
    assert_response_contains(events, "May")


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.parametrize('mock_gcp', [
    {'query_spend': APRIL_2026_SPEND}  # Will be called twice
], indirect=True)
async def test_ambiguous_query_dual_query(runner, mock_gcp, freeze_time):
    """When user query is ambiguous, should return BOTH MTD and previous month.

    Core feature: This is the key hybrid behavior that justifies the prompt complexity.
    """
    freeze_time()  # May 7, 2026

    events = await runner.run_debug("What did we spend?")

    # Should call query_spend TWICE
    prev_call, curr_call = assert_dual_query(
        events,
        "query_spend",
        prev_month_dates=(APRIL_START, APRIL_END),
        current_mtd_dates=(MAY_START, MAY_MTD_END),
    )

    assert mock_gcp['query_spend'].call_count == 2

    # Response should mention BOTH periods
    assert_response_contains(events, "April", "May", "MTD")
