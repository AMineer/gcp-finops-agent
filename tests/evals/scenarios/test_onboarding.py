"""Onboarding behavioral evals.

Priority: 6
Rationale: First impression matters - new users should get helpful orientation.

Tests that when users send greetings or help requests, the agent provides
a clear, actionable overview of its capabilities with concrete examples.
"""

import pytest
from tests.evals.assertions import (
    assert_response_contains,
    assert_tool_not_called,
    assert_response_length,
)


@pytest.mark.asyncio
@pytest.mark.slow
async def test_greeting_triggers_onboarding(runner, freeze_time):
    """Simple greeting should trigger friendly onboarding with examples.

    New users saying 'hi' should learn what the agent can do.
    """
    freeze_time()  # May 7, 2026

    events = await runner.run_debug("Hi there!")

    # Should NOT call any tools (no data needed for onboarding)
    assert_tool_not_called(events, "query_spend")
    assert_tool_not_called(events, "query_resources")
    assert_tool_not_called(events, "forecast_spend")

    # Should mention key capabilities
    assert_response_contains(events, "spend", "cost", "forecast")

    # Should provide examples of questions
    # (Look for question marks indicating example queries)
    response_text = events[-1].content.parts[0].text
    assert response_text.count("?") >= 2, (
        "Onboarding should include example questions (expected at least 2 '?')"
    )


@pytest.mark.asyncio
@pytest.mark.slow
async def test_help_request_shows_capabilities(runner, freeze_time):
    """Explicit help request should list capabilities with examples.

    User asking 'what can you do' should get concrete, actionable guidance.
    """
    freeze_time()  # May 7, 2026

    events = await runner.run_debug("What can you help me with?")

    # Should NOT call tools
    assert_tool_not_called(events, "query_spend")

    # Should mention main capabilities
    # Based on CAPABILITIES section in prompts.py
    capabilities = [
        "spend",  # Spend analysis
        "forecast",  # Forecasting
        "recommend",  # Cost recommendations
        "resource",  # Resource-level analysis
    ]

    response_text = events[-1].content.parts[0].text.lower()
    mentioned = sum(cap in response_text for cap in capabilities)

    assert mentioned >= 3, (
        f"Onboarding should mention at least 3 core capabilities. "
        f"Found {mentioned}: {capabilities}"
    )


@pytest.mark.asyncio
@pytest.mark.slow
async def test_onboarding_is_conversational(runner, freeze_time):
    """Onboarding should be friendly and conversational, not a manual dump.

    Should sound helpful, not robotic or overwhelming.
    """
    freeze_time()  # May 7, 2026

    events = await runner.run_debug("Hello!")

    response_text = events[-1].content.parts[0].text

    # Should be conversational (not too long)
    assert_response_length(events, max_length=800)

    # Should have friendly tone indicators
    friendly_patterns = ["help", "can", "!", "?"]
    found = sum(pattern in response_text for pattern in friendly_patterns)

    assert found >= 2, (
        "Onboarding should be conversational with friendly tone"
    )


@pytest.mark.asyncio
@pytest.mark.slow
async def test_vague_first_message_gets_guidance(runner, freeze_time):
    """Vague initial messages should prompt for specifics with examples.

    User saying 'I want to check costs' needs direction on what specifically.
    """
    freeze_time()  # May 7, 2026

    events = await runner.run_debug("I want to check costs")

    # Response should guide toward specific questions
    # Look for clarifying language or example queries
    response_text = events[-1].content.parts[0].text.lower()

    guiding_phrases = [
        "which",
        "would you like",
        "do you want",
        "for example",
        "such as",
    ]

    has_guidance = any(phrase in response_text for phrase in guiding_phrases)

    assert has_guidance, (
        "Vague request should prompt for specifics or offer examples"
    )
