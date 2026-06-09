"""GCP connectors for BigQuery billing export and Recommender API."""

import asyncio
import logging
from datetime import datetime

import pandas as pd
from google.cloud import bigquery, recommender_v1
from google.cloud.bigquery import ScalarQueryParameter

from .config import get_config
from .models import (
    Forecast,
    ForecastItem,
    LineItem,
    Recommendation,
    ResourceLineItem,
    ResourceSpendSummary,
    SpendSummary,
)
from .sanitize import (
    MAX_LEN_DEFAULT,
    MAX_LEN_DESCRIPTION,
    MAX_LEN_PROJECT_NAME,
    MAX_LEN_RESOURCE_GLOBAL_NAME,
    MAX_LEN_RESOURCE_NAME,
    MAX_LEN_SERVICE,
    MAX_LEN_SKU,
    sanitize_dict_labels,
    sanitize_for_llm,
)
from .utils import format_usage_amount

logger = logging.getLogger(__name__)


# ─── Billing Export Tables ────────────────────────────────────────────────
#
# Billing export table identifiers are supplied via environment variables:
#   GCP_BILLING_DATASET         — standard export (service/SKU/cost aggregates)
#   GCP_DETAILED_BILLING_DATASET — detailed export (includes resource.name columns)
#
# Both must be fully-qualified BigQuery table identifiers:
#   <project>.<dataset>.<table>
#
# See: https://cloud.google.com/billing/docs/how-to/export-data-bigquery


def _validate_billing_table(table: str, table_name: str) -> str:
    """Validate billing table constant format.

    Args:
        table: Fully-qualified BigQuery table identifier.
        table_name: Human-readable name for error messages (e.g., "STANDARD", "DETAILED").

    Raises:
        RuntimeError: If table is empty, placeholder, or malformed.

    Returns:
        The validated table identifier.
    """
    if not table:
        raise RuntimeError(
            f"BILLING_EXPORT_TABLE_{table_name} is empty. "
            "Set GCP_BILLING_DATASET (standard) or GCP_DETAILED_BILLING_DATASET (detailed) "
            "to a fully-qualified BigQuery table: <project>.<dataset>.<table>."
        )

    # Detect placeholder values (contains angle brackets or uppercase DATASET/ID)
    if "<" in table or ">" in table or "DATASET" in table or "BILLING_ACCOUNT_ID" in table:
        raise RuntimeError(
            f"BILLING_EXPORT_TABLE_{table_name} contains placeholder text: '{table}'. "
            "Replace with actual dataset and billing account ID before deploying."
        )

    # Validate format: project.dataset.table (exactly 3 non-empty parts)
    parts = table.split(".")
    if len(parts) < 3 or any(not part for part in parts):
        raise RuntimeError(
            f"BILLING_EXPORT_TABLE_{table_name} has invalid format: '{table}'. "
            "Expected <project>.<dataset>.<table> pattern."
        )

    return table


# BigQuery spend query template (standard export)
SPEND_QUERY = """
SELECT
    service.description AS service,
    project.id AS project_id,
    COALESCE(location.region, location.location, 'global') AS region,
    sku.description AS sku,
    currency,
    SUM(cost) AS cost,
    SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)) AS row_credits,
    SUM(SUM(cost)) OVER () AS total_gross_cost,
    SUM(SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0))) OVER () AS total_credits,
    COUNT(*) OVER () AS total_groups
FROM `{billing_table}`
WHERE DATE(usage_start_time) >= @start_date
  AND DATE(usage_start_time) < @end_date
  AND (@project_id = '' OR project.id = @project_id)
  AND (@service = '' OR service.description = @service)
GROUP BY service, project_id, region, sku, currency
ORDER BY cost DESC
LIMIT @limit
"""

# BigQuery resource-level query template (detailed export)
RESOURCE_QUERY = """
SELECT
    service.description AS service,
    project.id AS project_id,
    COALESCE(location.region, location.location, 'global') AS region,
    sku.description AS sku,
    COALESCE(resource.name, resource.global_name, 'unattributed') AS resource_name,
    resource.global_name AS resource_global_name,
    currency,
    SUM(cost) AS cost,
    SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)) AS row_credits,
    SUM(SUM(cost)) OVER () AS total_gross_cost,
    SUM(SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0))) OVER () AS total_credits,
    COUNT(*) OVER () AS total_groups
FROM `{billing_table}`
WHERE DATE(usage_start_time) >= @start_date
  AND DATE(usage_start_time) < @end_date
  AND (@project_id = '' OR project.id = @project_id)
  AND (@service = '' OR service.description = @service)
GROUP BY service, project_id, region, sku, resource_name, resource_global_name, currency
ORDER BY cost DESC
LIMIT @limit
"""

# Detailed resource lookup query
RESOURCE_DETAIL_QUERY = """
SELECT
    service.description AS service,
    project.id AS project_id,
    project.name AS project_name,
    location.region AS region,
    location.zone AS zone,
    sku.description AS sku,
    sku.id AS sku_id,
    resource.name AS resource_name,
    resource.global_name AS resource_global_name,
    usage.amount AS usage_amount,
    usage.unit AS usage_unit,
    SUM(cost) AS cost,
    currency,
    COUNT(DISTINCT DATE(usage_start_time)) AS days_with_usage
FROM `{billing_table}`
WHERE DATE(usage_start_time) >= @start_date
  AND DATE(usage_start_time) < @end_date
  AND (@project_id = '' OR project.id = @project_id)
  AND (
    LOWER(service.description) LIKE LOWER(@search_term)
    OR LOWER(sku.description) LIKE LOWER(@search_term)
    OR LOWER(COALESCE(resource.name, '')) LIKE LOWER(@search_term)
    OR LOWER(COALESCE(resource.global_name, '')) LIKE LOWER(@search_term)
  )
GROUP BY service, project_id, project_name, region, zone, sku, sku_id,
         resource_name, resource_global_name, usage_amount, usage_unit, currency
ORDER BY cost DESC
LIMIT 50
"""


async def query_spend(
    start_date: str,
    end_date: str,
    project_id: str = "",
    service: str = "",
    limit: int = 15
) -> SpendSummary:
    """Query spend from BigQuery standard billing export.

    Args:
        start_date: Period start in YYYY-MM-DD format.
        end_date: Period end in YYYY-MM-DD format (exclusive).
        project_id: Optional GCP project ID filter.
        service: Optional service name filter (e.g., "Compute Engine").
        limit: Max line items to return (default 15). Does not affect totals.

    Returns:
        SpendSummary with accurate totals computed over ALL filtered data,
        plus top N line items by cost.

    Note:
        - Date filtering uses DATE(usage_start_time). For exact parity with
          the GCP Billing console's monthly view (which uses invoice.month),
          use full calendar month ranges. Results may differ slightly for
          partial months due to late-arriving usage.
        - total_cost is gross cost (matches console "Filtered total").
        - total_net_cost is post-credits (matches console "Subtotal").
        - Totals are always accurate regardless of `limit` parameter.
    """

    def _run_query():
        client = bigquery.Client()
        table = _validate_billing_table(get_config().gcp_billing_dataset, "STANDARD")
        query = SPEND_QUERY.format(billing_table=table)

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter("start_date", "DATE", start_date),
                ScalarQueryParameter("end_date", "DATE", end_date),
                ScalarQueryParameter("project_id", "STRING", project_id),
                ScalarQueryParameter("service", "STRING", service),
                ScalarQueryParameter("limit", "INT64", limit),
            ]
        )

        query_job = client.query(query, job_config=job_config)
        return list(query_job.result())

    # Run synchronous BigQuery call in executor
    loop = asyncio.get_event_loop()
    rows = await loop.run_in_executor(None, _run_query)

    # Convert to DataFrame
    df = pd.DataFrame([dict(row) for row in rows])

    if df.empty:
        return SpendSummary(
            total_cost=0.0,
            total_net_cost=0.0,
            total_credits=0.0,
            currency="USD",
            period_start=start_date,
            period_end=end_date,
            line_items=[],
            total_groups=0,
            line_items_returned=0,
            line_items_truncated=False
        )

    # Extract totals from window functions (same across all rows)
    first_row = df.iloc[0]
    total_gross_cost = float(first_row["total_gross_cost"])
    total_credits = float(first_row["total_credits"])
    total_groups = int(first_row["total_groups"])
    total_net_cost = total_gross_cost + total_credits  # credits are negative
    currency = df["currency"].iloc[0]

    # Build line items (already ordered by cost DESC from query)
    line_items = [
        LineItem(
            service=sanitize_for_llm(row["service"] or "Unknown", MAX_LEN_SERVICE),
            project_id=sanitize_for_llm(row["project_id"] or "Unknown", MAX_LEN_DEFAULT),
            region=sanitize_for_llm(row["region"] or "global", MAX_LEN_DEFAULT),
            sku=sanitize_for_llm(row["sku"] or "Unknown", MAX_LEN_SKU),
            cost=float(row["cost"]),
            currency=row["currency"],
            credits=float(row["row_credits"])
        )
        for _, row in df.iterrows()
    ]

    return SpendSummary(
        total_cost=total_gross_cost,
        total_net_cost=total_net_cost,
        total_credits=total_credits,
        currency=currency,
        period_start=start_date,
        period_end=end_date,
        line_items=line_items,
        total_groups=total_groups,
        line_items_returned=len(line_items),
        line_items_truncated=(total_groups > len(line_items))
    )


async def forecast_spend(month: str) -> Forecast:
    """Forecast end-of-month spend based on MTD actuals."""

    # Parse month (YYYY-MM format)
    year, month_num = month.split("-")
    month_start = f"{year}-{month_num}-01"

    # Get current date for MTD calculation
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")

    # Query MTD spend
    mtd = await query_spend(month_start, today)

    # Calculate days
    days_elapsed = now.day
    if month_num == "12":
        next_month = f"{int(year)+1}-01-01"
    else:
        next_month = f"{year}-{int(month_num)+1:02d}-01"

    total_days = (datetime.fromisoformat(next_month) - datetime.fromisoformat(month_start)).days
    days_remaining = total_days - days_elapsed

    if days_elapsed == 0:
        return Forecast(
            month=month,
            projected_cost=0.0,
            confidence_pct=0.0,
            mtd_actual=0.0,
            breakdown=[]
        )

    # Daily burn rate
    daily_rate = mtd.total_cost / days_elapsed
    projected_cost = (daily_rate * days_remaining) + mtd.total_cost

    # Confidence based on days elapsed
    if days_elapsed < 7:
        confidence = 40.0
    elif days_elapsed < 15:
        confidence = 65.0
    else:
        confidence = 85.0

    # Service breakdown
    service_totals: dict[str, float] = {}
    for item in mtd.line_items:
        service_totals[item.service] = service_totals.get(item.service, 0.0) + item.cost

    top_services = sorted(service_totals.items(), key=lambda x: x[1], reverse=True)[:5]
    breakdown = [
        ForecastItem(
            service=svc,
            projected_cost=(cost / mtd.total_cost) * projected_cost if mtd.total_cost > 0 else 0.0
        )
        for svc, cost in top_services
    ]

    return Forecast(
        month=month,
        projected_cost=projected_cost,
        confidence_pct=confidence,
        mtd_actual=mtd.total_cost,
        breakdown=breakdown
    )


async def query_resources(
    start_date: str,
    end_date: str,
    project_id: str = "",
    service: str = "",
    limit: int = 15
) -> ResourceSpendSummary:
    """Query resource-level spend from BigQuery detailed billing export.

    Args:
        start_date: Period start in YYYY-MM-DD format.
        end_date: Period end in YYYY-MM-DD format (exclusive).
        project_id: Optional GCP project ID filter.
        service: Optional service name filter (e.g., "Compute Engine").
        limit: Max resource items to return (default 15). Does not affect totals.

    Returns:
        ResourceSpendSummary with accurate totals computed over ALL filtered data,
        plus top N resource items by cost.

    Note:
        - total_cost is gross cost (matches console "Filtered total").
        - total_net_cost is post-credits (matches console "Subtotal").
        - Totals are always accurate regardless of `limit` parameter.
    """

    def _run_query():
        client = bigquery.Client()
        table = _validate_billing_table(get_config().gcp_detailed_billing_dataset, "DETAILED")
        query = RESOURCE_QUERY.format(billing_table=table)

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter("start_date", "DATE", start_date),
                ScalarQueryParameter("end_date", "DATE", end_date),
                ScalarQueryParameter("project_id", "STRING", project_id),
                ScalarQueryParameter("service", "STRING", service),
                ScalarQueryParameter("limit", "INT64", limit),
            ]
        )

        query_job = client.query(query, job_config=job_config)
        return list(query_job.result())

    # Run synchronous BigQuery call in executor
    loop = asyncio.get_event_loop()
    rows = await loop.run_in_executor(None, _run_query)

    # Convert to DataFrame
    df = pd.DataFrame([dict(row) for row in rows])

    if df.empty:
        return ResourceSpendSummary(
            total_cost=0.0,
            total_net_cost=0.0,
            total_credits=0.0,
            currency="USD",
            period_start=start_date,
            period_end=end_date,
            resource_items=[],
            total_groups=0,
            line_items_returned=0,
            line_items_truncated=False
        )

    # Extract totals from window functions (same across all rows)
    first_row = df.iloc[0]
    total_gross_cost = float(first_row["total_gross_cost"])
    total_credits = float(first_row["total_credits"])
    total_groups = int(first_row["total_groups"])
    total_net_cost = total_gross_cost + total_credits  # credits are negative
    currency = df["currency"].iloc[0] if "currency" in df.columns else "USD"

    # Build resource items (already ordered by cost DESC from query)
    resource_items = [
        ResourceLineItem(
            service=sanitize_for_llm(row["service"] or "unattributed", MAX_LEN_SERVICE),
            project_id=sanitize_for_llm(row["project_id"] or "unknown", MAX_LEN_DEFAULT),
            region=sanitize_for_llm(row["region"] or "global", MAX_LEN_DEFAULT),
            sku=sanitize_for_llm(row["sku"] or "unattributed", MAX_LEN_SKU),
            resource_name=sanitize_for_llm(
                row["resource_name"] if row["resource_name"] != "unattributed"
                else row["resource_global_name"] or "unattributed",
                MAX_LEN_RESOURCE_NAME
            ),
            resource_global_name=sanitize_for_llm(row["resource_global_name"] or "N/A", MAX_LEN_RESOURCE_GLOBAL_NAME),
            cost=float(row["cost"]),
            currency=row["currency"],
            credits=float(row["row_credits"]),
            labels=sanitize_dict_labels({})  # Labels disabled for performance but sanitized when re-enabled
        )
        for _, row in df.iterrows()
    ]

    return ResourceSpendSummary(
        total_cost=total_gross_cost,
        total_net_cost=total_net_cost,
        total_credits=total_credits,
        currency=currency,
        period_start=start_date,
        period_end=end_date,
        resource_items=resource_items,
        total_groups=total_groups,
        line_items_returned=len(resource_items),
        line_items_truncated=(total_groups > len(resource_items))
    )


async def _verify_aggregate(
    start_date: str,
    end_date: str,
    service: str = "",
    project_id: str = ""
) -> dict:
    """Verification helper: compute aggregate totals for manual cross-checks.

    Runs the same WHERE clause as query_spend and returns totals without
    grouping. Useful for reconciling against the GCP Billing console.

    Args:
        start_date: Period start in YYYY-MM-DD format.
        end_date: Period end in YYYY-MM-DD format (exclusive).
        service: Optional service name filter.
        project_id: Optional GCP project ID filter.

    Returns:
        Dict with gross_cost, credits, net_cost, total_groups, currency.
    """
    VERIFY_QUERY = """
    WITH grouped AS (
      SELECT
        service.description AS service,
        project.id AS project_id,
        COALESCE(location.region, location.location, 'global') AS region,
        sku.description AS sku,
        currency,
        SUM(cost) AS cost,
        SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)) AS row_credits
      FROM `{billing_table}`
      WHERE DATE(usage_start_time) >= @start_date
        AND DATE(usage_start_time) < @end_date
        AND (@project_id = '' OR project.id = @project_id)
        AND (@service = '' OR service.description = @service)
      GROUP BY service, project_id, region, sku, currency
    )
    SELECT
      SUM(cost) AS gross_cost,
      SUM(row_credits) AS credits,
      SUM(cost) + SUM(row_credits) AS net_cost,
      COUNT(*) AS total_groups,
      ANY_VALUE(currency) AS currency
    FROM grouped
    """

    def _run_query():
        client = bigquery.Client()
        table = _validate_billing_table(get_config().gcp_billing_dataset, "STANDARD")
        query = VERIFY_QUERY.format(billing_table=table)

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter("start_date", "DATE", start_date),
                ScalarQueryParameter("end_date", "DATE", end_date),
                ScalarQueryParameter("project_id", "STRING", project_id),
                ScalarQueryParameter("service", "STRING", service),
            ]
        )

        query_job = client.query(query, job_config=job_config)
        rows = list(query_job.result())
        return dict(rows[0]) if rows else {}

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _run_query)

    return {
        "gross_cost": float(result.get("gross_cost", 0.0)),
        "credits": float(result.get("credits", 0.0)),
        "net_cost": float(result.get("net_cost", 0.0)),
        "total_groups": int(result.get("total_groups", 0)),
        "currency": result.get("currency", "USD")
    }


async def lookup_resource_details(
    search_term: str,
    start_date: str,
    end_date: str,
    project_id: str = ""
) -> dict:
    """Lookup detailed information about specific resources by search term."""

    def _run_query():
        client = bigquery.Client()
        table = _validate_billing_table(get_config().gcp_detailed_billing_dataset, "DETAILED")
        query = RESOURCE_DETAIL_QUERY.format(billing_table=table)

        # Add wildcards for LIKE search
        search_pattern = f"%{search_term}%"

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                ScalarQueryParameter("start_date", "DATE", start_date),
                ScalarQueryParameter("end_date", "DATE", end_date),
                ScalarQueryParameter("project_id", "STRING", project_id),
                ScalarQueryParameter("search_term", "STRING", search_pattern),
            ]
        )

        query_job = client.query(query, job_config=job_config)
        return list(query_job.result())

    # Run synchronous BigQuery call in executor
    loop = asyncio.get_event_loop()
    rows = await loop.run_in_executor(None, _run_query)

    # Convert to list of dicts with formatted usage (sanitize all string fields)
    results = []
    for row in rows:
        row_dict = dict(row)

        # Sanitize all string fields
        row_dict["service"] = sanitize_for_llm(row_dict.get("service"), MAX_LEN_SERVICE)
        row_dict["project_id"] = sanitize_for_llm(row_dict.get("project_id"), MAX_LEN_DEFAULT)
        row_dict["project_name"] = sanitize_for_llm(row_dict.get("project_name"), MAX_LEN_PROJECT_NAME)
        row_dict["region"] = sanitize_for_llm(row_dict.get("region"), MAX_LEN_DEFAULT)
        row_dict["zone"] = sanitize_for_llm(row_dict.get("zone"), MAX_LEN_DEFAULT)
        row_dict["sku"] = sanitize_for_llm(row_dict.get("sku"), MAX_LEN_SKU)
        row_dict["sku_id"] = sanitize_for_llm(row_dict.get("sku_id"), MAX_LEN_DEFAULT)
        row_dict["resource_name"] = sanitize_for_llm(row_dict.get("resource_name"), MAX_LEN_RESOURCE_NAME)
        row_dict["resource_global_name"] = sanitize_for_llm(row_dict.get("resource_global_name"), MAX_LEN_RESOURCE_GLOBAL_NAME)
        row_dict["usage_unit"] = sanitize_for_llm(row_dict.get("usage_unit"), MAX_LEN_DEFAULT)

        # Format usage amount if present
        if row_dict.get("usage_amount") and row_dict.get("usage_unit"):
            try:
                amount = float(row_dict["usage_amount"])
                unit = str(row_dict["usage_unit"])
                row_dict["usage_formatted"] = format_usage_amount(amount, unit)
            except (ValueError, TypeError):
                row_dict["usage_formatted"] = f"{row_dict['usage_amount']} {row_dict['usage_unit']}"

        results.append(row_dict)

    return {
        "total_results": len(results),
        "search_term": search_term,
        "period_start": start_date,
        "period_end": end_date,
        "results": results
    }


# Recommender API configuration
RECOMMENDER_IDS = [
    # Compute recommenders (regional)
    "google.compute.instance.MachineTypeRecommender",
    "google.compute.instance.IdleResourceRecommender",
    "google.compute.disk.IdleResourceRecommender",
    "google.compute.address.IdleResourceRecommender",
    "google.compute.image.IdleResourceRecommender",
    # Cloud SQL recommenders (regional)
    "google.cloudsql.instance.IdleRecommender",  # Fixed typo: was google.cloud.sql
    "google.cloudsql.instance.OverprovisionedRecommender",
    # Global recommenders
    "google.cloudbilling.commitment.SpendBasedCommitmentRecommender",  # CUDs - high value
    "google.bigquery.capacityCommitments.Recommender",
    "google.iam.policy.Recommender",
    "google.logging.productSuggestion.ContainerRecommender",
]

# Locations to query for recommenders
# - "global" required for IAM, CUD, and BigQuery commitment recommenders
# - Regional locations (us-central1, us-east4) for compute, disk, SQL, etc.
RECOMMENDER_LOCATIONS = ["global", "us-central1", "us-east4"]

PRIORITY_MAP = {
    recommender_v1.Recommendation.Priority.P1: "high",
    recommender_v1.Recommendation.Priority.P2: "high",
    recommender_v1.Recommendation.Priority.P3: "medium",
    recommender_v1.Recommendation.Priority.P4: "low",
    recommender_v1.Recommendation.Priority.PRIORITY_UNSPECIFIED: "medium",
}

CATEGORY_MAP = {
    "MachineType": "rightsizing",
    "Idle": "idle_resource",
    "Overprovisioned": "rightsizing",
}


async def get_recommendations(
    min_savings: float = 0.0,
    priority: str = "all"
) -> list[Recommendation]:
    """Get cost optimization recommendations from GCP Recommender API."""

    config = get_config()

    client = recommender_v1.RecommenderAsyncClient()

    # Fan out across all projects, locations, and recommender types
    # Cap concurrency to avoid overwhelming the API
    semaphore = asyncio.Semaphore(50)

    tasks = []
    for project_id in config.gcp_project_scope:
        for location in RECOMMENDER_LOCATIONS:
            for recommender_id in RECOMMENDER_IDS:
                tasks.append(_fetch_recommendations(client, project_id, location, recommender_id, semaphore))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Flatten results
    all_recommendations = []
    for result in results:
        if isinstance(result, list):
            all_recommendations.extend(result)

    # Filter and sort
    filtered = [
        rec for rec in all_recommendations
        if rec.estimated_monthly_savings >= min_savings
        and (priority == "all" or rec.priority == priority)
    ]

    filtered.sort(key=lambda r: r.estimated_monthly_savings, reverse=True)
    return filtered[:20]  # Top 20


async def _fetch_recommendations(
    client: recommender_v1.RecommenderAsyncClient,
    project_id: str,
    location: str,
    recommender_id: str,
    semaphore: asyncio.Semaphore
) -> list[Recommendation]:
    """Fetch recommendations for a single project, location, and recommender type."""

    async with semaphore:
        try:
            parent = f"projects/{project_id}/locations/{location}/recommenders/{recommender_id}"
            request = recommender_v1.ListRecommendationsRequest(
                parent=parent,
                filter='stateInfo.state="ACTIVE"'
            )

            recommendations = []
            async for rec in await client.list_recommendations(request=request):
                mapped = _map_recommendation(rec, recommender_id)
                if mapped:
                    recommendations.append(mapped)

            return recommendations

        except Exception as e:
            logger.warning(
                "Recommender fetch failed: project=%s location=%s recommender=%s error=%s",
                project_id, location, recommender_id, e
            )
            return []


def _map_recommendation(
    rec: recommender_v1.Recommendation,
    recommender_id: str
) -> Recommendation | None:
    """Map GCP recommendation to our model."""

    try:
        # Extract cost savings
        savings = 0.0
        currency = "USD"

        if rec.primary_impact and rec.primary_impact.cost_projection:
            cost_proj = rec.primary_impact.cost_projection
            if cost_proj.cost:
                savings = abs(cost_proj.cost.units)
                if hasattr(cost_proj.cost, "nanos"):
                    savings += abs(cost_proj.cost.nanos / 1e9)
                currency = cost_proj.cost.currency_code or "USD"

        # Map priority
        priority = PRIORITY_MAP.get(rec.priority, "medium")

        # Map category
        category = "other"
        for key, cat in CATEGORY_MAP.items():
            if key in recommender_id:
                category = cat
                break

        return Recommendation(
            resource_name=sanitize_for_llm(rec.description or recommender_id, MAX_LEN_RESOURCE_NAME),
            description=sanitize_for_llm(rec.description or "No description", MAX_LEN_DESCRIPTION),
            estimated_monthly_savings=savings,
            currency=currency,
            priority=priority,
            category=category
        )

    except Exception:
        return None
