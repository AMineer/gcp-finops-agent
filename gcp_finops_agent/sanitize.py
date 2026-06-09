"""Sanitization helpers for untrusted GCP metadata before LLM consumption.

Defends against prompt injection via adversarial resource names, labels, project
names, and other user-controllable string fields that flow from GCP APIs into
the agent's context.

Approach:
- Strip control characters (anything below 0x20 except tab)
- Truncate to field-appropriate max lengths
- Fence HIGH RISK fields in prose contexts with delimiters
- Do NOT attempt pattern-based injection detection (unreliable)
"""

# Field-specific max lengths (chars)
# Based on GCP naming limits and practical readability constraints
MAX_LEN_RESOURCE_NAME = 200       # VM names, disk names, etc.
MAX_LEN_RESOURCE_GLOBAL_NAME = 500  # Full URIs can be long
MAX_LEN_PROJECT_NAME = 30         # GCP display name limit
MAX_LEN_BUCKET_NAME = 200         # GCS bucket names
MAX_LEN_DESCRIPTION = 500         # Recommendation descriptions
MAX_LEN_SERVICE = 200             # Service descriptions
MAX_LEN_SKU = 200                 # SKU descriptions
MAX_LEN_LABEL_KEY = 63            # GCP label key limit
MAX_LEN_LABEL_VALUE = 63          # GCP label value limit
MAX_LEN_DEFAULT = 100             # project_id, region, zone, etc.

# Delimiter for fencing HIGH RISK fields in prose contexts
# Using guillemets (« ») — extremely unlikely in legitimate resource metadata
FENCE_OPEN = "«"
FENCE_CLOSE = "»"


def sanitize_for_llm(value: str | None, max_len: int = MAX_LEN_DEFAULT) -> str:
    """Sanitize an untrusted string field before exposing it to the LLM.

    Args:
        value: Untrusted string from GCP API/BigQuery
        max_len: Maximum length before truncation

    Returns:
        Sanitized string safe for LLM context

    Transformations:
        - Returns "" for None
        - Strips control characters (0x00-0x1F except tab 0x09)
        - Truncates to max_len with "…[truncated]" marker if exceeded
    """
    if value is None:
        return ""

    # Strip control characters except tab
    sanitized = "".join(
        char for char in value
        if ord(char) >= 0x20 or char == "\t"
    )

    # Truncate if exceeds max length
    if len(sanitized) > max_len:
        truncate_at = max_len - len("…[truncated]")
        sanitized = sanitized[:truncate_at] + "…[truncated]"

    return sanitized


def sanitize_dict_labels(labels: dict[str, str] | None) -> dict[str, str]:
    """Sanitize a dict of labels (both keys and values).

    Args:
        labels: Dict of label key-value pairs from GCP

    Returns:
        Dict with sanitized keys and values
    """
    if labels is None:
        return {}

    return {
        sanitize_for_llm(key, MAX_LEN_LABEL_KEY): sanitize_for_llm(value, MAX_LEN_LABEL_VALUE)
        for key, value in labels.items()
    }


def fence_high_risk(value: str, field_name: str) -> str:
    """Fence a HIGH RISK field value with delimiters for prose contexts.

    Use this ONLY when embedding untrusted fields into prose/markdown where
    they're concatenated with instructions. Do NOT use for structured returns.

    Args:
        value: Already-sanitized field value
        field_name: Field name for the opening tag

    Returns:
        Fenced string like: <field_name>«value»</field_name>

    Example:
        fence_high_risk("my-vm-123", "resource_name")
        # Returns: "<resource_name>«my-vm-123»</resource_name>"
    """
    return f"<{field_name}>{FENCE_OPEN}{value}{FENCE_CLOSE}</{field_name}>"
