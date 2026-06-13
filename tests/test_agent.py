"""Tests for agent initialization and instruction generation."""

from datetime import date
from gcp_finops_agent.agent import root_agent
from gcp_finops_agent.prompts import build_instruction


def test_agent_imports():
    """Test that the agent can be imported successfully."""
    assert root_agent is not None
    assert root_agent.name == "gcp_finops_agent"
    assert callable(root_agent.instruction)


def test_instruction_builder_callable():
    """Test that build_instruction is callable and returns a string."""
    instruction = build_instruction()
    assert isinstance(instruction, str)
    assert len(instruction) > 1000  # Should be substantial


def test_instruction_has_current_date():
    """Test that the instruction includes today's date."""
    instruction = build_instruction()
    today = date.today().isoformat()
    assert f"Today's date is {today}" in instruction


def test_instruction_has_key_sections():
    """Test that all expected sections are present in the instruction."""
    instruction = build_instruction()

    # Updated to match refactored prompts structure (consolidated for token efficiency)
    key_sections = [
        "You are the GCP FinOps Agent",
        "Security: Untrusted Data Handling",
        "Date Interpretation",
        "Your 7 Tools",
        "Response Guidelines",
        "Error Handling",
        "Ambiguity",
        "Onboarding",
        "Follow-ups",
    ]

    for section in key_sections:
        assert section in instruction, f"Missing section: {section}"


def test_instruction_mentions_dual_query():
    """Test that the instruction mentions querying both periods for ambiguous requests."""
    instruction = build_instruction()
    assert "BOTH" in instruction
    assert "previous complete month" in instruction.lower()
    assert "MTD" in instruction or "month-to-date" in instruction.lower()
