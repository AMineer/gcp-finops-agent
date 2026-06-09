"""Canned tool responses for eval scenarios.

These are realistic GCP billing export shapes that mocks return.
All data is fictional but structurally correct.
"""

from gcp_finops_agent.models import (
    SpendSummary,
    LineItem,
    Forecast,
    ForecastItem,
    ResourceSpendSummary,
    ResourceLineItem,
    Recommendation,
)


# === Date Interpretation Scenarios ===

APRIL_2026_SPEND = SpendSummary(
    total_cost=45230.12,
    currency="USD",
    period_start="2026-04-01",
    period_end="2026-04-30",
    line_items=[
        LineItem(
            service="Compute Engine",
            project_id="prod-app",
            region="us-central1",
            sku="N1 Predefined Instance Core running in Americas",
            cost=18000.50,
            currency="USD",
        ),
        LineItem(
            service="BigQuery",
            project_id="data-warehouse",
            region="US",
            sku="Analysis",
            cost=12450.30,
            currency="USD",
        ),
        LineItem(
            service="Cloud Storage",
            project_id="prod-app",
            region="us-central1",
            sku="Standard Storage US Multi-region",
            cost=8120.18,
            currency="USD",
        ),
        LineItem(
            service="Cloud SQL",
            project_id="prod-db",
            region="us-central1",
            sku="Database instance - db-n1-standard-4",
            cost=5500.58,
            currency="USD",
        ),
        LineItem(
            service="Cloud Logging",
            project_id="prod-app",
            region="global",
            sku="Log Volume",
            cost=1158.56,
            currency="USD",
        ),
    ],
)

MAY_2026_MTD_SPEND = SpendSummary(
    total_cost=12156.45,
    currency="USD",
    period_start="2026-05-01",
    period_end="2026-05-07",
    line_items=[
        LineItem(
            service="Compute Engine",
            project_id="prod-app",
            region="us-central1",
            sku="N1 Predefined Instance Core running in Americas",
            cost=4800.20,
            currency="USD",
        ),
        LineItem(
            service="BigQuery",
            project_id="data-warehouse",
            region="US",
            sku="Analysis",
            cost=3320.15,
            currency="USD",
        ),
        LineItem(
            service="Cloud Storage",
            project_id="prod-app",
            region="us-central1",
            sku="Standard Storage US Multi-region",
            cost=2180.10,
            currency="USD",
        ),
        LineItem(
            service="Cloud SQL",
            project_id="prod-db",
            region="us-central1",
            sku="Database instance - db-n1-standard-4",
            cost=1470.00,
            currency="USD",
        ),
        LineItem(
            service="Cloud Logging",
            project_id="prod-app",
            region="global",
            sku="Log Volume",
            cost=386.00,
            currency="USD",
        ),
    ],
)

MAY_2026_FORECAST = Forecast(
    month="2026-05",
    projected_cost=53800.00,
    confidence_pct=40.0,  # Only 7 days elapsed
    mtd_actual=12156.45,
    breakdown=[
        ForecastItem(service="Compute Engine", projected_cost=21200.00),
        ForecastItem(service="BigQuery", projected_cost=14680.00),
        ForecastItem(service="Cloud Storage", projected_cost=9640.00),
        ForecastItem(service="Cloud SQL", projected_cost=6500.00),
        ForecastItem(service="Cloud Logging", projected_cost=1780.00),
    ],
)


# === Resource-Level Data ===

APRIL_2026_RESOURCES = ResourceSpendSummary(
    total_cost=45230.12,
    currency="USD",
    period_start="2026-04-01",
    period_end="2026-04-30",
    resource_items=[
        ResourceLineItem(
            service="Compute Engine",
            project_id="prod-app",
            region="us-central1",
            sku="N1 Predefined Instance Core",
            resource_name="instance-worker-pool-1",
            resource_global_name="//compute.googleapis.com/projects/prod-app/zones/us-central1-a/instances/instance-worker-pool-1",
            cost=8500.00,
            currency="USD",
            labels={},
        ),
        ResourceLineItem(
            service="Compute Engine",
            project_id="prod-app",
            region="us-central1",
            sku="N1 Predefined Instance Core",
            resource_name="instance-worker-pool-2",
            resource_global_name="//compute.googleapis.com/projects/prod-app/zones/us-central1-b/instances/instance-worker-pool-2",
            cost=6200.00,
            currency="USD",
            labels={},
        ),
        ResourceLineItem(
            service="BigQuery",
            project_id="data-warehouse",
            region="US",
            sku="Analysis",
            resource_name="unattributed",
            resource_global_name="N/A",
            cost=12450.30,
            currency="USD",
            labels={},
        ),
        ResourceLineItem(
            service="Cloud Storage",
            project_id="prod-app",
            region="us-central1",
            sku="Standard Storage",
            resource_name="prod-app-logs-bucket",
            resource_global_name="//storage.googleapis.com/prod-app-logs-bucket",
            cost=4100.00,
            currency="USD",
            labels={},
        ),
        ResourceLineItem(
            service="Cloud Logging",
            project_id="prod-app",
            region="global",
            sku="Log Volume",
            resource_name="unattributed",
            resource_global_name="N/A",
            cost=1158.56,
            currency="USD",
            labels={},
        ),
    ],
)


# === Unknown Resource Lookup Data ===

UNKNOWN_BIGQUERY_DETAILS = {
    "total_results": 3,
    "search_term": "BigQuery",
    "period_start": "2026-04-01",
    "period_end": "2026-04-30",
    "results": [
        {
            "service": "BigQuery",
            "project_id": "data-warehouse",
            "project_name": "Data Warehouse Production",
            "region": "US",
            "zone": "N/A",
            "sku": "Analysis",
            "sku_id": "BQ-123-456",
            "resource_name": "N/A",
            "resource_global_name": "N/A",
            "usage_amount": 45600.0,
            "usage_unit": "byte-seconds",
            "usage_formatted": "45.6 TB-seconds",
            "cost": 8200.15,
            "currency": "USD",
            "days_with_usage": 30,
        },
        {
            "service": "BigQuery",
            "project_id": "data-warehouse",
            "region": "US",
            "zone": "N/A",
            "sku": "Storage",
            "sku_id": "BQ-789-012",
            "resource_name": "N/A",
            "resource_global_name": "N/A",
            "usage_amount": 2400.0,
            "usage_unit": "gibibyte month",
            "usage_formatted": "2.4 TB-month",
            "cost": 4250.15,
            "currency": "USD",
            "days_with_usage": 30,
        },
    ],
}

UNKNOWN_LOGGING_DETAILS = {
    "total_results": 1,
    "search_term": "Cloud Logging",
    "period_start": "2026-04-01",
    "period_end": "2026-04-30",
    "results": [
        {
            "service": "Cloud Logging",
            "project_id": "prod-app",
            "project_name": "Production Application",
            "region": "global",
            "zone": "N/A",
            "sku": "Log Volume",
            "sku_id": "LOG-456-789",
            "resource_name": "N/A",
            "resource_global_name": "N/A",
            "usage_amount": 2300.0,
            "usage_unit": "gibibyte",
            "usage_formatted": "2.3 TB",
            "cost": 1158.56,
            "currency": "USD",
            "days_with_usage": 30,
        }
    ],
}


# === Recommendations ===

RECOMMENDATIONS_HIGH_SAVINGS = [
    Recommendation(
        resource_name="instance-worker-pool-1",
        description="This VM is idle 85% of the time. Consider stopping it during off-hours or downsizing.",
        estimated_monthly_savings=4250.00,
        currency="USD",
        priority="high",
        category="idle_resource",
    ),
    Recommendation(
        resource_name="instance-worker-pool-2",
        description="This VM is overprovisioned. Recommended machine type: n1-standard-2 (currently: n1-standard-8)",
        estimated_monthly_savings=2100.00,
        currency="USD",
        priority="high",
        category="rightsizing",
    ),
    Recommendation(
        resource_name="db-instance-prod",
        description="This Cloud SQL instance is idle 70% of the time. Consider downsizing.",
        estimated_monthly_savings=1850.00,
        currency="USD",
        priority="medium",
        category="idle_resource",
    ),
]

RECOMMENDATIONS_EMPTY = []


# === Multi-Currency Example ===

EURO_SPEND = SpendSummary(
    total_cost=38450.80,
    currency="EUR",
    period_start="2026-04-01",
    period_end="2026-04-30",
    line_items=[
        LineItem(
            service="Compute Engine",
            project_id="eu-prod",
            region="europe-west1",
            sku="N1 Predefined Instance",
            cost=22000.00,
            currency="EUR",
        ),
        LineItem(
            service="Cloud Storage",
            project_id="eu-prod",
            region="europe-west1",
            sku="Standard Storage",
            cost=16450.80,
            currency="EUR",
        ),
    ],
)


# === GCS Bucket Inspection ===

GCS_BUCKET_STANDARD_NO_AUTOCLASS = {
    "success": True,
    "bucket_name": "prod-app-logs-bucket",
    "storage_class": "STANDARD",
    "autoclass_enabled": False,
    "lifecycle_rules": [],
    "versioning_enabled": False,
    "location": "US-CENTRAL1",
    "labels": {"env": "prod", "team": "platform"},
}

GCS_BUCKET_WITH_LIFECYCLE = {
    "success": True,
    "bucket_name": "archive-bucket",
    "storage_class": "NEARLINE",
    "autoclass_enabled": False,
    "lifecycle_rules": [
        {
            "action": {"type": "Delete"},
            "condition": {"age": 365},
        }
    ],
    "versioning_enabled": True,
    "location": "US",
    "labels": {"retention": "1-year"},
}
