"""Tests for configuration loading."""

from gcp_finops_agent.config import Config


def test_config_defaults(monkeypatch):
    """Test that Config can be instantiated with defaults."""
    # Clear env vars to test actual defaults
    monkeypatch.delenv("GCP_PROJECT_SCOPE", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    config = Config()
    assert config.gcp_location == "us-central1"
    # Default model is gemini-2.5-flash (set in config.py)
    assert config.gemini_model in ["gemini-2.5-flash", "gemini-2.5-flash-lite"]


def test_config_project_scope_parsing(monkeypatch):
    """Test that project scope parsing handles comma-separated values."""
    monkeypatch.setenv("GCP_PROJECT_SCOPE", "proj-a,proj-b,proj-c")
    config = Config()
    assert config.gcp_project_scope == ["proj-a", "proj-b", "proj-c"]


def test_config_project_scope_empty(monkeypatch):
    """Test that empty project scope returns empty list."""
    monkeypatch.setenv("GCP_PROJECT_SCOPE", "")
    config = Config()
    assert config.gcp_project_scope == []


def test_config_project_scope_whitespace(monkeypatch):
    """Test that project scope handles whitespace correctly."""
    monkeypatch.setenv("GCP_PROJECT_SCOPE", "proj-a, proj-b , proj-c")
    config = Config()
    assert config.gcp_project_scope == ["proj-a", "proj-b", "proj-c"]
