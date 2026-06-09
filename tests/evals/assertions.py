"""Reusable assertion helpers for behavioral evals.

These functions inspect ADK Event streams and assert properties of:
- Tool calls made (which tools, with what arguments)
- Response content (text, formatting, presence of key information)
- Behavioral patterns (dual queries, auto-chaining, etc.)
"""

from typing import List, Optional, Tuple
from google.adk.events import Event


def get_all_tool_calls(events: List[Event]) -> List[Tuple[str, dict]]:
    """Extract all tool calls from event stream.

    Returns:
        List of (tool_name, args_dict) tuples in order called.
    """
    calls = []
    for event in events:
        for call in event.get_function_calls():
            calls.append((call.name, dict(call.args)))
    return calls


def get_final_response_text(events: List[Event]) -> str:
    """Extract the final text response from events.

    Returns the last text part found, or empty string if none.
    """
    for event in reversed(events):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, 'text') and part.text:
                    return part.text
    return ""


def assert_tool_called(
    events: List[Event],
    tool_name: str,
    min_calls: int = 1,
    max_calls: Optional[int] = None,
) -> List[dict]:
    """Assert a specific tool was called the expected number of times.

    Args:
        events: Event stream from runner
        tool_name: Name of tool (e.g., "query_spend")
        min_calls: Minimum number of calls expected (default: 1)
        max_calls: Maximum number of calls expected (default: no limit)

    Returns:
        List of argument dicts for all matching calls

    Raises:
        AssertionError if call count doesn't match expectations
    """
    calls = [args for name, args in get_all_tool_calls(events) if name == tool_name]

    assert len(calls) >= min_calls, (
        f"Expected at least {min_calls} call(s) to {tool_name}, got {len(calls)}"
    )

    if max_calls is not None:
        assert len(calls) <= max_calls, (
            f"Expected at most {max_calls} call(s) to {tool_name}, got {len(calls)}"
        )

    return calls


def assert_tool_called_with(
    events: List[Event],
    tool_name: str,
    **expected_args
) -> dict:
    """Assert a tool was called with specific arguments.

    Args:
        events: Event stream
        tool_name: Tool name
        **expected_args: Key-value pairs that must match in at least one call

    Returns:
        The first matching call's full arguments

    Raises:
        AssertionError if no matching call found
    """
    calls = [args for name, args in get_all_tool_calls(events) if name == tool_name]

    assert len(calls) > 0, f"Tool {tool_name} was never called"

    matching = [
        c for c in calls
        if all(c.get(k) == v for k, v in expected_args.items())
    ]

    assert len(matching) > 0, (
        f"Tool {tool_name} not called with {expected_args}.\n"
        f"Actual calls: {calls}"
    )

    return matching[0]


def assert_dual_query(
    events: List[Event],
    tool_name: str,
    prev_month_dates: Tuple[str, str],
    current_mtd_dates: Tuple[str, str],
) -> Tuple[dict, dict]:
    """Assert tool was called twice for ambiguous query (MTD + previous month).

    Args:
        events: Event stream
        tool_name: Tool that should be called twice
        prev_month_dates: (start_date, end_date) for previous complete month
        current_mtd_dates: (start_date, end_date) for current MTD

    Returns:
        (prev_month_call_args, current_mtd_call_args)

    Raises:
        AssertionError if dual query pattern not followed
    """
    calls = assert_tool_called(events, tool_name, min_calls=2, max_calls=2)

    prev_start, prev_end = prev_month_dates
    curr_start, curr_end = current_mtd_dates

    # Find which call matches which period
    prev_call = None
    curr_call = None

    for call_args in calls:
        if call_args.get("start_date") == prev_start and call_args.get("end_date") == prev_end:
            prev_call = call_args
        elif call_args.get("start_date") == curr_start and call_args.get("end_date") == curr_end:
            curr_call = call_args

    assert prev_call is not None, (
        f"Missing previous month query with dates {prev_start} to {prev_end}.\n"
        f"Actual calls: {calls}"
    )

    assert curr_call is not None, (
        f"Missing current MTD query with dates {curr_start} to {curr_end}.\n"
        f"Actual calls: {calls}"
    )

    return prev_call, curr_call


def assert_response_contains(events: List[Event], *phrases: str, case_sensitive: bool = False):
    """Assert final response contains all given phrases.

    Args:
        events: Event stream
        *phrases: Phrases that must appear in response
        case_sensitive: Whether to do case-sensitive matching (default: False)

    Raises:
        AssertionError if any phrase is missing
    """
    text = get_final_response_text(events)

    if not case_sensitive:
        text_lower = text.lower()
        phrases = [p.lower() for p in phrases]
    else:
        text_lower = text

    for phrase in phrases:
        assert phrase in text_lower, (
            f"Response missing phrase: '{phrase}'\n"
            f"Response text: {text[:200]}..."
        )


def assert_response_does_not_contain(events: List[Event], *phrases: str):
    """Assert final response does NOT contain given phrases.

    Useful for checking that agent doesn't mention things it shouldn't.
    """
    text = get_final_response_text(events)
    text_lower = text.lower()

    for phrase in phrases:
        assert phrase.lower() not in text_lower, (
            f"Response should not contain: '{phrase}'\n"
            f"Response text: {text[:200]}..."
        )


def assert_chained_lookup(
    events: List[Event],
    initial_tool: str,
    lookup_tool: str = "lookup_resource",
    search_term: Optional[str] = None,
) -> Tuple[List[dict], List[dict]]:
    """Assert agent chained initial query to lookup_resource (unknown resource flow).

    Args:
        events: Event stream
        initial_tool: First tool called (e.g., "query_resources")
        lookup_tool: Lookup tool that should follow (default: "lookup_resource")
        search_term: If provided, assert lookup was called with this search term

    Returns:
        (initial_calls, lookup_calls)

    Raises:
        AssertionError if chaining didn't happen
    """
    initial_calls = assert_tool_called(events, initial_tool, min_calls=1)
    lookup_calls = assert_tool_called(events, lookup_tool, min_calls=1)

    if search_term:
        # Check that at least one lookup call has the expected search term
        matching = [c for c in lookup_calls if search_term.lower() in c.get("search_term", "").lower()]
        assert len(matching) > 0, (
            f"Expected lookup with search term containing '{search_term}'.\n"
            f"Actual lookup calls: {lookup_calls}"
        )

    return initial_calls, lookup_calls


def assert_uses_markdown_table(events: List[Event]):
    """Assert response contains a markdown table (for structured data).

    Checks for presence of markdown table syntax (pipes and dashes).
    """
    text = get_final_response_text(events)

    # Markdown tables have | and typically have header separator (---)
    has_pipes = "|" in text
    has_separator = "---" in text or "━━━" in text

    assert has_pipes and has_separator, (
        "Response should contain a markdown table (expected | and --- separators).\n"
        f"Response: {text[:300]}..."
    )


def assert_mentions_currency(events: List[Event], expected_currency: str = "USD"):
    """Assert response mentions the expected currency code.

    Args:
        events: Event stream
        expected_currency: Currency code to look for (default: "USD")
    """
    text = get_final_response_text(events)
    assert expected_currency in text, (
        f"Response should mention currency '{expected_currency}'.\n"
        f"Response: {text[:200]}..."
    )


def assert_suggests_followup(events: List[Event]):
    """Assert response includes a follow-up question suggestion.

    Looks for question marks that indicate a suggested next action.
    """
    text = get_final_response_text(events)

    # Response should end with a question or contain "Want to" pattern
    has_question = "?" in text
    has_want_to = "want to" in text.lower() or "would you like" in text.lower()

    assert has_question or has_want_to, (
        "Response should include a follow-up suggestion (ending with ? or 'Want to...').\n"
        f"Response: {text[-200:]}"
    )


def assert_asks_clarifying_question(events: List[Event]):
    """Assert response asks a clarifying question instead of guessing.

    Looks for question marks and uncertainty phrases.
    """
    text = get_final_response_text(events)

    # Should contain a question
    assert "?" in text, (
        "Response should ask a clarifying question (expected ?).\n"
        f"Response: {text[:300]}..."
    )

    # Should have clarifying language
    clarifying_phrases = ["did you mean", "do you want", "which", "would you like"]
    has_clarifying = any(phrase in text.lower() for phrase in clarifying_phrases)

    assert has_clarifying, (
        "Response should use clarifying language (did you mean, which, etc.).\n"
        f"Response: {text[:300]}..."
    )


def assert_tool_not_called(events: List[Event], tool_name: str):
    """Assert a specific tool was NOT called.

    Useful for negative tests (e.g., shouldn't call expensive tool for simple query).
    """
    calls = [name for name, _ in get_all_tool_calls(events) if name == tool_name]
    assert len(calls) == 0, f"Tool {tool_name} should not have been called, but was called {len(calls)} time(s)"


def assert_response_length(events: List[Event], min_length: Optional[int] = None, max_length: Optional[int] = None):
    """Assert response length is appropriate.

    Args:
        events: Event stream
        min_length: Minimum character count (optional)
        max_length: Maximum character count (optional)
    """
    text = get_final_response_text(events)
    length = len(text)

    if min_length is not None:
        assert length >= min_length, (
            f"Response too short: {length} chars (expected >= {min_length})"
        )

    if max_length is not None:
        assert length <= max_length, (
            f"Response too long: {length} chars (expected <= {max_length})"
        )
