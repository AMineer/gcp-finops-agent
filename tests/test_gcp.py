"""Tests for GCP billing table validation."""

import pytest
from gcp_finops_agent.gcp import _validate_billing_table


def test_validate_billing_table_standard_valid():
    """Test that validation accepts valid standard billing table."""
    table = "your-billing-project.your_billing_dataset.gcp_billing_export_v1_XXXXXX"
    result = _validate_billing_table(table, "STANDARD")
    assert result == table


def test_validate_billing_table_detailed_valid():
    """Test that validation accepts valid detailed billing table."""
    table = "your-billing-project.your_billing_dataset.gcp_billing_export_resource_v1_XXXXXX"
    result = _validate_billing_table(table, "DETAILED")
    assert result == table


def test_validate_billing_table_empty_raises_error():
    """Test that validation raises error when table is empty."""
    with pytest.raises(RuntimeError, match="is empty"):
        _validate_billing_table("", "STANDARD")


def test_validate_billing_table_placeholder_angle_brackets_raises_error():
    """Test that validation raises error for placeholder with angle brackets."""
    table = "my-project.<DATASET>.gcp_billing_export_v1_<BILLING_ACCOUNT_ID>"
    with pytest.raises(RuntimeError, match="contains placeholder text"):
        _validate_billing_table(table, "STANDARD")


def test_validate_billing_table_placeholder_uppercase_dataset_raises_error():
    """Test that validation raises error for placeholder with DATASET."""
    table = "my-project.DATASET.gcp_billing_export_v1_ABC123"
    with pytest.raises(RuntimeError, match="contains placeholder text"):
        _validate_billing_table(table, "STANDARD")


def test_validate_billing_table_placeholder_billing_account_id_raises_error():
    """Test that validation raises error for placeholder with BILLING_ACCOUNT_ID."""
    table = "my-project.export.gcp_billing_export_v1_BILLING_ACCOUNT_ID"
    with pytest.raises(RuntimeError, match="contains placeholder text"):
        _validate_billing_table(table, "STANDARD")


def test_validate_billing_table_invalid_format_no_dots_raises_error():
    """Test that validation raises error for invalid format (no dots)."""
    with pytest.raises(RuntimeError, match="invalid format.*Expected"):
        _validate_billing_table("invalid-table-name", "STANDARD")


def test_validate_billing_table_invalid_format_one_dot_raises_error():
    """Test that validation raises error for invalid format (one dot)."""
    with pytest.raises(RuntimeError, match="invalid format.*Expected"):
        _validate_billing_table("project.dataset", "STANDARD")


def test_validate_billing_table_invalid_format_missing_table_raises_error():
    """Test that validation raises error when missing table part."""
    with pytest.raises(RuntimeError, match="invalid format.*Expected"):
        _validate_billing_table("project.dataset.", "STANDARD")
