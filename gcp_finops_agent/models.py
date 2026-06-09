"""Pydantic models for GCP billing data."""

from pydantic import BaseModel


class LineItem(BaseModel):
    """Individual spend line item."""
    service: str
    project_id: str
    region: str
    sku: str
    cost: float
    currency: str
    credits: float = 0.0


class SpendSummary(BaseModel):
    """Aggregated spend summary."""
    total_cost: float
    currency: str
    period_start: str
    period_end: str
    line_items: list[LineItem]
    total_net_cost: float = 0.0
    total_credits: float = 0.0
    total_groups: int = 0
    line_items_returned: int = 0
    line_items_truncated: bool = False


class ForecastItem(BaseModel):
    """Forecasted spend for a service."""
    service: str
    projected_cost: float


class Forecast(BaseModel):
    """End-of-month forecast."""
    month: str
    projected_cost: float
    confidence_pct: float
    mtd_actual: float
    breakdown: list[ForecastItem]


class ResourceLineItem(BaseModel):
    """Resource-level spend line item with labels."""
    service: str
    project_id: str
    region: str
    sku: str
    resource_name: str
    resource_global_name: str
    cost: float
    currency: str
    labels: dict[str, str] = {}
    credits: float = 0.0


class ResourceSpendSummary(BaseModel):
    """Resource-level spend summary."""
    total_cost: float
    currency: str
    period_start: str
    period_end: str
    resource_items: list[ResourceLineItem]
    total_net_cost: float = 0.0
    total_credits: float = 0.0
    total_groups: int = 0
    line_items_returned: int = 0
    line_items_truncated: bool = False


class Recommendation(BaseModel):
    """Cost optimization recommendation."""
    resource_name: str
    description: str
    estimated_monthly_savings: float
    currency: str
    priority: str
    category: str
