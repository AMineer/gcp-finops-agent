# gcp-finops-agent Agent Behavioral Evals

Regression test suite for the gcp-finops-agent GCP FinOps agent's behavioral correctness.

## Philosophy

These tests verify **prompt adherence and reasoning patterns**, not just code correctness. They use **real LLM calls** with a **mocked GCP layer** to ensure the agent:

- Picks the right tool for the question type
- Interprets dates correctly (MTD vs previous month)
- Chains tools appropriately (auto-investigation of unknown resources)
- Asks clarifying questions instead of guessing
- Formats responses per guidelines (tables, currency, follow-ups)
- Provides helpful onboarding for new users

**Property-based assertions** verify behavior, not exact output (e.g., "must call query_spend with April dates" not "must output this exact sentence").

## Structure

```
tests/evals/
├── README.md                   # This file
├── conftest.py                 # Pytest fixtures (runner, mock_gcp, freeze_time)
├── assertions.py               # Reusable assertion helpers
├── fixtures/
│   └── tool_responses.py       # Canned GCP response data
└── scenarios/
    ├── test_date_interpretation.py       # Priority 1
    ├── test_tool_selection.py            # Priority 2
    ├── test_unknown_resource_flow.py     # Priority 3
    ├── test_ambiguity_handling.py        # Priority 4
    ├── test_format_compliance.py         # Priority 5
    ├── test_onboarding.py                # Priority 6
    └── test_followups.py                 # Priority 7
```

## Running Evals

### Run All Evals

```bash
pytest tests/evals/ -v
```

**Note:** This makes real LLM calls and will take time + cost money. Budget ~30 seconds per test.

### Run Specific Scenario

```bash
pytest tests/evals/scenarios/test_date_interpretation.py -v
```

### Run Single Test

```bash
pytest tests/evals/scenarios/test_date_interpretation.py::test_last_month_unambiguous -v
```

### Skip Slow Tests (Evals)

```bash
pytest tests/ -v -m "not slow"
```

All eval tests are marked with `@pytest.mark.slow` to enable filtering in CI.

## CI Integration

Evals run in CI only when relevant files change:

```yaml
# .gitlab-ci.yml snippet
test:evals:
  rules:
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
      changes:
        - gcp_finops_agent/prompts.py
        - gcp_finops_agent/agent.py
        - gcp_finops_agent/tools.py
        - gcp_finops_agent/gcp.py
        - tests/evals/**/*
  script:
    - pytest tests/evals/ -v
  retry:
    max: 1  # LLM calls can be flaky - retry once
```

**Path-based filtering** ensures we only pay for LLM calls when behavior could have changed.

## Writing New Evals

### 1. Choose a Scenario

Focus on **behaviors that matter**:
- Tool selection correctness
- Multi-step reasoning (chaining)
- Prompt-specified formatting
- Ambiguity handling
- User experience flows

Avoid testing:
- Code logic (use unit tests)
- Data transformations (use unit tests)
- Exact output text (brittle, not valuable)

### 2. Use the Standard Pattern

```python
import pytest
from tests.evals.fixtures.tool_responses import APRIL_2026_SPEND
from tests.evals.assertions import assert_tool_called_with, assert_response_contains

@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.parametrize('mock_gcp', [
    {'query_spend': APRIL_2026_SPEND}
], indirect=True)
async def test_my_scenario(runner, mock_gcp, freeze_time):
    """Docstring explaining what behavior is tested and why."""
    freeze_time()  # May 7, 2026

    events = await runner.run_debug("User query here")

    # Assert on tool calls
    assert_tool_called_with(
        events,
        "query_spend",
        start_date="2026-04-01",
        end_date="2026-04-30",
    )

    # Assert on response content
    assert_response_contains(events, "April", "45,230")
```

### 3. Available Fixtures

#### `runner`
InMemoryRunner configured with the real `root_agent`. Makes actual LLM calls.

```python
async def test_something(runner):
    events = await runner.run_debug("What did we spend?")
    # events is a list of ADK Event objects
```

#### `mock_gcp`
Patches GCP layer functions with AsyncMock. Use indirect parametrization:

```python
@pytest.mark.parametrize('mock_gcp', [
    {
        'query_spend': APRIL_2026_SPEND,
        'forecast_spend': MAY_2026_FORECAST,
    }
], indirect=True)
async def test_foo(runner, mock_gcp):
    # mock_gcp['query_spend'] is the AsyncMock for call inspection
    assert mock_gcp['query_spend'].call_count == 1
```

**Supported functions:**
- `query_spend`
- `query_resources`
- `lookup_resource_details`
- `forecast_spend`
- `get_recommendations`
- `inspect_bucket`
- `generate_report`

#### `freeze_time`
Freezes `datetime.now()` to May 7, 2026 (default) for deterministic date handling.

```python
def test_dates(freeze_time):
    freeze_time()  # Now it's May 7, 2026
    # Tools will compute "last month" as April 2026
```

Pass a custom datetime:
```python
freeze_time(datetime(2026, 12, 15))
```

**Date constants** available from `conftest.py`:
- `APRIL_START = "2026-04-01"`
- `APRIL_END = "2026-04-30"`
- `MAY_START = "2026-05-01"`
- `MAY_MTD_END = "2026-05-07"`
- `MARCH_START = "2026-03-01"`
- `MARCH_END = "2026-03-31"`

### 4. Assertion Helpers

See [assertions.py](assertions.py) for full list. Common ones:

#### Tool Call Assertions
```python
# Assert tool was called at least once
assert_tool_called(events, "query_spend", min_calls=1)

# Assert tool was called with specific args
assert_tool_called_with(
    events,
    "query_spend",
    start_date="2026-04-01",
    end_date="2026-04-30",
)

# Assert tool was NOT called
assert_tool_not_called(events, "query_resources")

# Assert dual-query pattern (MTD + previous month)
prev_call, curr_call = assert_dual_query(
    events,
    "query_spend",
    prev_month_dates=("2026-04-01", "2026-04-30"),
    current_mtd_dates=("2026-05-01", "2026-05-07"),
)

# Assert chained lookup (unknown resource flow)
initial_calls, lookup_calls = assert_chained_lookup(
    events,
    initial_tool="query_resources",
    lookup_tool="lookup_resource_details",
    search_term="BigQuery",
)
```

#### Response Assertions
```python
# Assert response contains specific phrases
assert_response_contains(events, "April", "45,230")

# Assert response does NOT contain phrases
assert_response_does_not_contain(events, "error", "failed")

# Assert response uses markdown table
assert_uses_markdown_table(events)

# Assert response mentions currency
assert_mentions_currency(events, "USD")

# Assert response suggests a follow-up
assert_suggests_followup(events)

# Assert response asks clarifying question
assert_asks_clarifying_question(events)

# Assert response length
assert_response_length(events, min_length=50, max_length=500)
```

### 5. Adding Test Data

Add canned responses to [fixtures/tool_responses.py](fixtures/tool_responses.py):

```python
MY_NEW_SCENARIO_DATA = SpendSummary(
    total_cost=12345.67,
    currency="USD",
    period_start="2026-06-01",
    period_end="2026-06-30",
    line_items=[...],
)
```

Use **real Pydantic models** (SpendSummary, Forecast, etc.) for type safety.

## Maintenance

### When to Update Evals

**Update tests** when:
- Changing prompt behavior intentionally (verify new behavior works)
- Adding new tools (verify agent uses them correctly)
- Fixing bugs (add regression test)

**Don't update** for:
- Backend implementation changes (as long as behavior is the same)
- Response text tweaks (unless format requirements changed)
- Performance improvements (not behavioral changes)

### If Tests Fail

1. **Is the failure expected?**
   - If you changed prompt behavior, update the test expectations
   - If you fixed a bug, the test might now pass (good!)

2. **Is the failure a regression?**
   - Investigate why behavior changed
   - Fix the prompt/code or update test if new behavior is correct

3. **Is the test flaky?**
   - LLM behavior can vary slightly - use property assertions, not exact text matching
   - If flaky due to LLM variance, consider making assertion more permissive
   - If flaky due to API issues, CI has `retry: max: 1`

### Updating Fixtures

When GCP response schema changes:
1. Update the Pydantic models in `gcp_finops_agent/models.py`
2. Update fixture data in `fixtures/tool_responses.py` to match
3. Run evals to verify still passing

## Cost Considerations

Each eval test makes 1-2 LLM calls (depending on complexity). With ~20 tests, expect:
- **Time:** ~10 minutes for full suite
- **Cost:** ~$0.20-0.50 per run (using Gemini 2.5 Flash)

**CI runs evals only when relevant files change** to avoid unnecessary costs.

For local development:
- Run specific scenarios while working (`pytest tests/evals/scenarios/test_date_interpretation.py`)
- Use `-k` to filter tests (`pytest tests/evals/ -k "unambiguous"`)
- Skip evals during rapid iteration (`pytest tests/ -m "not slow"`)

## Debugging Eval Failures

### Inspect Event Stream

```python
@pytest.mark.asyncio
async def test_debug_example(runner, freeze_time):
    freeze_time()
    events = await runner.run_debug("What did we spend?")
    
    # Print all events
    for i, event in enumerate(events):
        print(f"\nEvent {i}: {event}")
    
    # Print tool calls
    from tests.evals.assertions import get_all_tool_calls
    print("\nTool calls:", get_all_tool_calls(events))
    
    # Print final response
    from tests.evals.assertions import get_final_response_text
    print("\nFinal response:", get_final_response_text(events))
```

### Check Mock Calls

```python
async def test_debug_mocks(runner, mock_gcp):
    events = await runner.run_debug("...")
    
    # Check what was called
    print("query_spend called:", mock_gcp['query_spend'].called)
    print("Call count:", mock_gcp['query_spend'].call_count)
    print("Call args:", mock_gcp['query_spend'].call_args_list)
```

### Run with Verbose Pytest

```bash
pytest tests/evals/scenarios/test_date_interpretation.py -vv -s
```

The `-s` flag shows print statements, `-vv` shows detailed assertion failures.

## Philosophy: Why These Evals Matter

The gcp-finops-agent agent's value is **behavioral correctness**:
- Does it understand ambiguous date references?
- Does it pick the right tool for the job?
- Does it investigate unknown resources automatically?
- Does it ask clarifying questions instead of guessing?

These behaviors are **prompt-emergent** and can regress with seemingly harmless changes. Unit tests can't catch these regressions because they test code, not LLM reasoning.

Behavioral evals ensure the **agent does what users expect**, even as the underlying implementation evolves.
