"""FinOps tools for spend analysis, forecasting, recommendations, and reporting."""

from datetime import datetime, timedelta
from . import gcp
from . import gcs
from .sanitize import fence_high_risk


async def query_spend(
    start_date: str = "",
    end_date: str = "",
    project_id: str = "",
    service: str = "",
    limit: int = 15
) -> dict:
    """Query GCP spend for a date range.

    Queries BigQuery billing export and returns total cost, currency, and top
    line items by cost. Totals are computed over ALL filtered data; the `limit`
    parameter only controls how many top line items are returned.

    Dates default to the previous complete month if not provided.

    Args:
        start_date: Period start in YYYY-MM-DD format.
        end_date: Period end in YYYY-MM-DD format.
        project_id: Optional GCP project ID to filter to single project.
        service: Optional service name filter (e.g., "Compute Engine").
        limit: Max line items to return (default 15). Does not affect totals.

    Returns:
        Dict with total_cost (gross), total_net_cost (post-credits), total_credits,
        currency, period_start, period_end, line_items, total_groups,
        line_items_returned, and line_items_truncated.
    """
    if not start_date or not end_date:
        now = datetime.now()
        # Default to previous complete month
        first_of_current_month = now.replace(day=1)
        last_day_prev_month = first_of_current_month - timedelta(days=1)
        first_day_prev_month = last_day_prev_month.replace(day=1)
        start_date = first_day_prev_month.strftime("%Y-%m-%d")
        end_date = last_day_prev_month.strftime("%Y-%m-%d")

    try:
        summary = await gcp.query_spend(start_date, end_date, project_id, service, limit)
        return summary.model_dump()
    except Exception as e:
        return {"error": f"Failed to query spend: {str(e)}"}


async def forecast_spend(month: str = "") -> dict:
    """Forecast end-of-month GCP spend.

    Projects total spend to end of month based on current daily burn rate.
    Confidence increases with days elapsed (under 7 days = 40%, 7-15 = 65%, 15+ = 85%).

    Args:
        month: Target month in YYYY-MM format. Defaults to current month.

    Returns:
        Dict with projected_cost, confidence_pct, mtd_actual, and service breakdown.
    """
    if not month:
        now = datetime.now()
        month = f"{now.year}-{now.month:02d}"

    try:
        forecast = await gcp.forecast_spend(month)
        return forecast.model_dump()
    except Exception as e:
        return {"error": f"Failed to forecast spend: {str(e)}"}


async def query_resources(
    start_date: str = "",
    end_date: str = "",
    project_id: str = "",
    service: str = "",
    limit: int = 15
) -> dict:
    """Query GCP spend at resource level with labels.

    Queries BigQuery detailed billing export and returns resource-level spend
    data including resource names, labels, and tags. Useful for identifying
    specific resources driving costs. Totals are computed over ALL filtered data;
    the `limit` parameter only controls how many top resource items are returned.

    Args:
        start_date: Period start in YYYY-MM-DD format.
        end_date: Period end in YYYY-MM-DD format.
        project_id: Optional GCP project ID to filter to single project.
        service: Optional service name filter (e.g., "Compute Engine").
        limit: Max resource items to return (default 15). Does not affect totals.

    Returns:
        Dict with total_cost (gross), total_net_cost (post-credits), total_credits,
        currency, period_start, period_end, resource_items, total_groups,
        line_items_returned, and line_items_truncated.
    """
    if not start_date or not end_date:
        now = datetime.now()
        # Default to previous complete month
        first_of_current_month = now.replace(day=1)
        last_day_prev_month = first_of_current_month - timedelta(days=1)
        first_day_prev_month = last_day_prev_month.replace(day=1)
        start_date = first_day_prev_month.strftime("%Y-%m-%d")
        end_date = last_day_prev_month.strftime("%Y-%m-%d")

    try:
        summary = await gcp.query_resources(start_date, end_date, project_id, service, limit)
        return summary.model_dump()
    except Exception as e:
        return {"error": f"Failed to query resources: {str(e)}"}


async def lookup_resource(
    search_term: str,
    start_date: str = "",
    end_date: str = "",
    project_id: str = ""
) -> dict:
    """Lookup detailed information about specific resources.

    Search for resources by name, service, SKU, or any keyword. Returns detailed
    usage and cost data including project name, zone, usage amounts, and number
    of days with usage.

    Useful for investigating "Unknown" resources or getting details about specific
    resources identified in other queries.

    Args:
        search_term: Keyword to search for (e.g., "Cloud Logging", "Unknown", VM name).
        start_date: Period start in YYYY-MM-DD format (defaults to previous complete month).
        end_date: Period end in YYYY-MM-DD format (defaults to previous complete month).
        project_id: Optional GCP project ID to filter.

    Returns:
        Dict with total_results, search_term, period, and detailed results array
        (each with service, project, zone, SKU, resource names, usage, cost).
    """
    if not start_date or not end_date:
        now = datetime.now()
        # Default to previous complete month
        first_of_current_month = now.replace(day=1)
        last_day_prev_month = first_of_current_month - timedelta(days=1)
        first_day_prev_month = last_day_prev_month.replace(day=1)
        start_date = first_day_prev_month.strftime("%Y-%m-%d")
        end_date = last_day_prev_month.strftime("%Y-%m-%d")

    try:
        details = await gcp.lookup_resource_details(search_term, start_date, end_date, project_id)
        return details
    except Exception as e:
        return {"error": f"Failed to lookup resource: {str(e)}"}


async def get_recommendations(
    min_monthly_savings: float = 0.0,
    priority: str = "all"
) -> dict:
    """Get GCP cost optimization recommendations.

    Queries GCP Recommender API across all configured projects. Returns active
    recommendations ranked by estimated monthly savings.

    Args:
        min_monthly_savings: Only return recommendations saving at least this
            amount per month (USD). Defaults to 0 (all recommendations).
        priority: Filter by priority. Options: 'high', 'medium', 'low', 'all'.

    Returns:
        Dict with total_recommendations, total_potential_savings, and recommendations list.
    """
    try:
        recs = await gcp.get_recommendations(min_monthly_savings, priority)
        total_savings = sum(r.estimated_monthly_savings for r in recs)

        return {
            "total_recommendations": len(recs),
            "total_potential_savings": total_savings,
            "currency": "USD",
            "recommendations": [r.model_dump() for r in recs]
        }

    except Exception as e:
        return {"error": f"Failed to get recommendations: {str(e)}"}


async def generate_report(
    period: str = "current_month",
    start_date: str = "",
    end_date: str = "",
    include_recommendations: bool = True
) -> dict:
    """Generate a structured GCP spend report in markdown.

    Assembles a full report covering: Executive Summary, Spend Overview, Top
    Services, Top Projects, EOM Forecast, and Recommendations.

    Args:
        period: Report period. Options: 'current_month', 'last_month', 'custom'.
        start_date: Required if period='custom'. Format: YYYY-MM-DD.
        end_date: Required if period='custom'. Format: YYYY-MM-DD.
        include_recommendations: Whether to include recommendations section.

    Returns:
        Dict with format='markdown' and content (full report string).
    """
    now = datetime.now()

    # Determine date range
    if period == "current_month":
        start_date = f"{now.year}-{now.month:02d}-01"
        end_date = now.strftime("%Y-%m-%d")
        period_label = "Current Month"

    elif period == "last_month":
        first_of_month = now.replace(day=1)
        last_month_end = first_of_month - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        start_date = last_month_start.strftime("%Y-%m-%d")
        end_date = last_month_end.strftime("%Y-%m-%d")
        period_label = "Last Month"

    elif period == "custom":
        if not start_date or not end_date:
            return {"error": "start_date and end_date required for custom period"}
        period_label = f"{start_date} to {end_date}"

    else:
        return {"error": f"Invalid period: {period}"}

    # Fetch data
    spend_data = await query_spend(start_date, end_date)
    if "error" in spend_data:
        return spend_data

    forecast_data = await forecast_spend()

    recs_data = None
    if include_recommendations:
        recs_data = await get_recommendations()

    # Build report
    lines = []
    lines.append("# GCP Spend Report")
    lines.append(f"\n**Period:** {period_label}")
    lines.append(f"**Generated:** {now.strftime('%Y-%m-%d %H:%M UTC')}\n")

    # Executive Summary
    lines.append("## Executive Summary\n")
    total_cost = spend_data.get("total_cost", 0.0)
    currency = spend_data.get("currency", "USD")
    lines.append(f"- **Total Spend:** {currency} {total_cost:,.2f}")

    if forecast_data and "error" not in forecast_data:
        projected = forecast_data.get("projected_cost", 0.0)
        confidence = forecast_data.get("confidence_pct", 0.0)
        lines.append(f"- **Projected EOM:** {currency} {projected:,.2f} ({confidence:.0f}% confidence)")

    if recs_data and "error" not in recs_data:
        total_savings = recs_data.get("total_potential_savings", 0.0)
        rec_count = recs_data.get("total_recommendations", 0)
        lines.append(f"- **Potential Savings:** {currency} {total_savings:,.2f}/month ({rec_count} recommendations)")

    # Spend Overview
    lines.append("\n## Spend Overview\n")

    # Only show service rollup if we have complete data (not truncated)
    # Otherwise, totals would be misleading
    if not spend_data.get("line_items_truncated", False):
        line_items = spend_data.get("line_items", [])
        if line_items:
            # Top services from line items (accurate only when not truncated)
            service_totals: dict[str, float] = {}
            for item in line_items:
                svc = item.get("service", "Unknown")
                service_totals[svc] = service_totals.get(svc, 0.0) + item.get("cost", 0.0)

            top_services = sorted(service_totals.items(), key=lambda x: x[1], reverse=True)[:10]

            lines.append("### Top Services\n")
            for svc, cost in top_services:
                pct = (cost / total_cost * 100) if total_cost > 0 else 0
                lines.append(f"- **{svc}**: {currency} {cost:,.2f} ({pct:.1f}%)")
    else:
        # Truncated data - note the limitation
        lines.append("### Top Services\n")
        lines.append(
            f"_Service breakdown unavailable: line items truncated "
            f"({spend_data.get('line_items_returned', 0)} of "
            f"{spend_data.get('total_groups', 0)} groups shown). "
            "Use `query_spend` with service filter for accurate service totals._\n"
        )

    # Recommendations (fence HIGH RISK fields: resource_name, description)
    if recs_data and "error" not in recs_data:
        lines.append("\n## Cost Optimization Recommendations\n")
        recs = recs_data.get("recommendations", [])

        for i, rec in enumerate(recs[:10], 1):
            resource = rec.get("resource_name", "Unknown")
            description = rec.get("description", "")
            savings = rec.get("estimated_monthly_savings", 0.0)
            priority = rec.get("priority", "medium")

            # Fence HIGH RISK fields in prose context
            fenced_resource = fence_high_risk(resource, "resource_name")
            fenced_description = fence_high_risk(description, "description")

            lines.append(f"### {i}. {fenced_resource} ({priority.upper()})\n")
            lines.append(f"- **Savings:** {currency} {savings:,.2f}/month")
            lines.append(f"- **Description:** {fenced_description}\n")

    report_content = "\n".join(lines)

    return {
        "format": "markdown",
        "content": report_content,
        "generated_at": now.isoformat()
    }


async def inspect_gcs_storage(bucket_name: str = "", project_id: str = "") -> dict:
    """Inspect Cloud Storage - list all buckets or get details for a specific bucket.

    This is a flexible tool for GCS investigation. When you don't know which buckets
    exist, call without bucket_name to list all buckets. When you know the bucket
    name and need detailed configuration (storage class, autoclass, lifecycle rules),
    call with the bucket_name to get full details.

    Use cases:
    - "What buckets do we have?" → Call with no bucket_name to list all
    - "Is autoclass enabled on bucket-x?" → Call with bucket_name="bucket-x"
    - "Show me buckets with STANDARD storage class" → List all, then filter in response

    Args:
        bucket_name: Optional bucket name. If empty, lists all buckets in the project.
            If provided, returns detailed configuration for that specific bucket.
        project_id: Optional GCP project ID. If empty, uses default project.

    Returns:
        If bucket_name empty: Dict with bucket_count and buckets list (basic info).
        If bucket_name provided: Dict with detailed bucket configuration including
            storage_class, autoclass_enabled, lifecycle_rules, versioning_enabled,
            object_count (from Cloud Monitoring metric).
    """
    try:
        result = await gcs.inspect_gcs_storage(bucket_name, project_id)
        return result
    except Exception as e:
        return {"success": False, "error": f"Failed to inspect GCS storage: {str(e)}"}
