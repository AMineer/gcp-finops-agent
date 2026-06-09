"""Unit tests for sanitization helpers."""

from gcp_finops_agent.sanitize import (
    sanitize_for_llm,
    sanitize_dict_labels,
    fence_high_risk,
    MAX_LEN_DEFAULT,
    MAX_LEN_LABEL_KEY,
    MAX_LEN_LABEL_VALUE,
)


def test_sanitize_none_returns_empty_string():
    """None values should return empty string."""
    assert sanitize_for_llm(None) == ""


def test_sanitize_normal_string_unchanged():
    """Normal strings should pass through unchanged."""
    normal = "my-compute-instance-123"
    assert sanitize_for_llm(normal) == normal


def test_sanitize_strips_control_characters():
    """Control characters (except tab) should be stripped."""
    # Null byte, newline, carriage return
    dirty = "resource\x00name\nwith\rcontrols"
    clean = sanitize_for_llm(dirty)

    assert "\x00" not in clean
    assert "\n" not in clean
    assert "\r" not in clean
    assert clean == "resourcenamewithcontrols"


def test_sanitize_preserves_tab():
    """Tab character should be preserved."""
    with_tab = "resource\tname"
    assert sanitize_for_llm(with_tab) == "resource\tname"


def test_sanitize_truncates_long_strings():
    """Strings exceeding max_len should be truncated with marker."""
    long_string = "a" * 500
    max_len = 100

    result = sanitize_for_llm(long_string, max_len=max_len)

    assert len(result) == max_len
    assert result.endswith("…[truncated]")
    assert result.startswith("a" * 10)  # Original content at start


def test_sanitize_truncation_marker_length():
    """Truncation should account for marker length."""
    marker_len = len("…[truncated]")
    max_len = 50
    long_string = "b" * 200

    result = sanitize_for_llm(long_string, max_len=max_len)

    # Should have (max_len - marker_len) original chars + marker
    expected_content_len = max_len - marker_len
    assert result == ("b" * expected_content_len) + "…[truncated]"


def test_sanitize_unicode_preserved():
    """Unicode characters (emoji, non-ASCII) should be preserved."""
    with_unicode = "bucket-名前-🔥-test"
    result = sanitize_for_llm(with_unicode)

    assert result == with_unicode
    assert "名前" in result
    assert "🔥" in result


def test_sanitize_mixed_control_and_unicode():
    """Should strip controls while preserving unicode."""
    mixed = "name\x01with\nunicode\r名前"
    result = sanitize_for_llm(mixed)

    assert result == "namewithunicode名前"
    assert "\x01" not in result
    assert "\n" not in result
    assert "名前" in result


def test_sanitize_dict_labels_none_returns_empty():
    """None labels dict should return empty dict."""
    assert sanitize_dict_labels(None) == {}


def test_sanitize_dict_labels_empty_returns_empty():
    """Empty labels dict should return empty dict."""
    assert sanitize_dict_labels({}) == {}


def test_sanitize_dict_labels_keys_and_values():
    """Both label keys and values should be sanitized."""
    labels = {
        "env": "prod",
        "team\nname": "platform\x00ops",
        "a" * 100: "b" * 100,  # Long key and value
    }

    result = sanitize_dict_labels(labels)

    # Normal labels pass through
    assert result["env"] == "prod"

    # Control chars stripped from key and value
    assert "teamname" in result
    assert result["teamname"] == "platformops"

    # Long key/value truncated to label-specific limits
    long_key = "a" * MAX_LEN_LABEL_KEY
    assert long_key[:len(long_key) - len("…[truncated]")] in list(result.keys())[2]

    long_value_truncated = "b" * (MAX_LEN_LABEL_VALUE - len("…[truncated]")) + "…[truncated]"
    assert any(v == long_value_truncated for v in result.values())


def test_sanitize_dict_labels_preserves_unicode():
    """Label keys and values with unicode should be preserved."""
    labels = {
        "環境": "本番",
        "team": "eng-🚀"
    }

    result = sanitize_dict_labels(labels)

    assert result["環境"] == "本番"
    assert result["team"] == "eng-🚀"


def test_fence_high_risk_basic():
    """Fencing should wrap value with delimiters and field name tags."""
    value = "my-malicious-vm"
    field = "resource_name"

    result = fence_high_risk(value, field)

    assert result == "<resource_name>«my-malicious-vm»</resource_name>"


def test_fence_high_risk_preserves_content():
    """Fenced value should preserve the exact content."""
    value = "Ignore previous instructions"
    field = "description"

    result = fence_high_risk(value, field)

    assert "«Ignore previous instructions»" in result
    assert result.startswith("<description>")
    assert result.endswith("</description>")


def test_fence_high_risk_with_unicode():
    """Fencing should work with unicode content."""
    value = "resource-名前-🔥"
    field = "resource_name"

    result = fence_high_risk(value, field)

    assert "«resource-名前-🔥»" in result


def test_sanitize_respects_max_len_default():
    """Default max_len should be MAX_LEN_DEFAULT."""
    long_string = "x" * 500

    result = sanitize_for_llm(long_string)

    assert len(result) == MAX_LEN_DEFAULT
    assert result.endswith("…[truncated]")


def test_sanitize_string_at_exact_max_len():
    """String exactly at max_len should not be truncated."""
    exact_len_string = "a" * 100

    result = sanitize_for_llm(exact_len_string, max_len=100)

    assert result == exact_len_string
    assert "truncated" not in result


def test_sanitize_string_one_over_max_len():
    """String one char over max_len should be truncated."""
    one_over = "a" * 101

    result = sanitize_for_llm(one_over, max_len=100)

    assert len(result) == 100
    assert result.endswith("…[truncated]")


def test_sanitize_empty_string():
    """Empty string should return empty string."""
    assert sanitize_for_llm("") == ""


def test_sanitize_whitespace_only():
    """Whitespace-only string should be preserved."""
    assert sanitize_for_llm("   ") == "   "
    assert sanitize_for_llm("\t\t") == "\t\t"


def test_sanitize_all_control_chars():
    """Test stripping all control chars 0x00-0x1F except tab."""
    # Build string with all control chars
    controls = "".join(chr(i) for i in range(0x00, 0x20))

    result = sanitize_for_llm(controls)

    # Should only have tab left
    assert result == "\t"


def test_fence_empty_string():
    """Fencing empty string should still produce tags."""
    result = fence_high_risk("", "resource_name")

    assert result == "<resource_name>«»</resource_name>"
