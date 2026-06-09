"""Pytest fixtures for behavioral evals.

Provides:
- runner: Configured InMemoryRunner with real agent
- mock_gcp: Factory for mocking GCP layer functions
- Common date fixtures for deterministic testing
- Auto-marking hook: all tests under tests/evals/ get @pytest.mark.eval
"""

import pytest
from datetime import datetime
from unittest.mock import patch, AsyncMock
from google.adk.runners import InMemoryRunner
from gcp_finops_agent.agent import root_agent


def pytest_collection_modifyitems(config, items):
    """Auto-mark every test under tests/evals/ as eval.

    This means `pytest -m "not eval"` excludes them by default and
    `pytest -m eval` runs them. Individual scenario files don't need
    to remember to add @pytest.mark.eval.
    """
    for item in items:
        if "tests/evals" in str(item.fspath):
            item.add_marker(pytest.mark.eval)


@pytest.fixture
async def runner():
    """Configured ADK runner with real agent.

    Yields an InMemoryRunner that makes real LLM calls but
    allows mocking of the GCP layer.

    Usage:
        async def test_foo(runner):
            events = await runner.run_debug("What did we spend?")
    """
    r = InMemoryRunner(agent=root_agent)
    yield r
    await r.close()


@pytest.fixture
def mock_gcp(request):
    """Factory for mocking GCP layer functions.

    Accepts a dict mapping function names to return values via indirect parametrization.
    All mocks are AsyncMock to match the async tool signatures.

    Usage:
        @pytest.mark.parametrize('mock_gcp', [
            {
                'query_spend': APRIL_2026_SPEND,
                'forecast_spend': MAY_2026_FORECAST,
            }
        ], indirect=True)
        async def test_foo(runner, mock_gcp):
            events = await runner.run_debug("What's our forecast?")
            assert mock_gcp['forecast_spend'].called

    The mock objects are available in the returned dict for call inspection.
    """
    mocks = {}
    patchers = []

    # Get the mock configuration from test parameter
    mock_config = getattr(request, 'param', {})

    for func_name, return_value in mock_config.items():
        mock = AsyncMock(return_value=return_value)
        mocks[func_name] = mock

        # Patch at the GCP layer (where tools call)
        if func_name in ['query_spend', 'forecast_spend', 'query_resources', 'lookup_resource_details', 'get_recommendations']:
            patcher = patch(f'gcp_finops_agent.gcp.{func_name}', new=mock)
        elif func_name == 'inspect_bucket':
            patcher = patch(f'gcp_finops_agent.gcs.{func_name}', new=mock)
        else:
            # Direct tool patch (for generate_report)
            patcher = patch(f'gcp_finops_agent.tools.{func_name}', new=mock)

        patcher.start()
        patchers.append(patcher)

    yield mocks

    # Cleanup
    for patcher in patchers:
        patcher.stop()


@pytest.fixture
def freeze_time(monkeypatch):
    """Freeze datetime.now() to a specific point for deterministic testing.

    Returns a function that freezes time to May 7, 2026 by default,
    or a custom datetime if provided.

    Usage:
        def test_date_handling(freeze_time):
            freeze_time()  # Freezes to 2026-05-07
            # ... test code that uses datetime.now()

        def test_custom_date(freeze_time):
            freeze_time(datetime(2026, 12, 15))
    """
    def _freeze(frozen_datetime=None):
        if frozen_datetime is None:
            frozen_datetime = datetime(2026, 5, 7, 10, 30, 0)  # May 7, 2026, 10:30 AM

        class FrozenDatetime:
            @classmethod
            def now(cls):
                return frozen_datetime

            def __getattr__(self, name):
                # Delegate other datetime methods to the real class
                return getattr(datetime, name)

        monkeypatch.setattr('gcp_finops_agent.tools.datetime', FrozenDatetime())

    return _freeze


# === Common Date Constants ===
# Useful for test assertions - these match the system current date

APRIL_START = "2026-04-01"
APRIL_END = "2026-04-30"

MAY_START = "2026-05-01"
MAY_MTD_END = "2026-05-15"  # Matches system currentDate context

MARCH_START = "2026-03-01"
MARCH_END = "2026-03-31"
