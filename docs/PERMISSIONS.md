# gcp-finops-agent Agent - GCP IAM Permissions

This document outlines the required GCP IAM roles for the gcp-finops-agent Reasoning Engine service account to function properly.

## Service Account

The Reasoning Engine service account is automatically created when deploying to Agent Engine:

```
service-<PROJECT_NUMBER>@gcp-sa-aiplatform-re.iam.gserviceaccount.com
```

For `your-project-id`, this is the service account that requires the permissions below.

---

## Required Permissions by Tool

### 1. BigQuery Billing Export (Cross-Project)

**Tools:** `query_spend`, `forecast_spend`, `query_resources`, `lookup_resource`

**Purpose:** Query billing export tables to analyze GCP spend

**Resources:**
- Project: `your-billing-project`
- Tables:
  - `gcp_standard_billing_export.gcp_billing_export_v1_XXXXXX`
  - `gcp_detailed_billing_export.gcp_billing_export_resource_v1_XXXXXX`

**Required Roles:**
- `roles/bigquery.dataViewer` - Read table data
- `roles/bigquery.jobUser` - Create and run query jobs

**Terraform:**

```hcl
# Grant BigQuery access on billing export project
data "google_project" "finops_stage" {
  project_id = "your-project-id"
}

resource "google_project_iam_member" "reasoning_engine_bigquery_data_viewer" {
  project = "your-billing-project"
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:service-${data.google_project.finops_stage.number}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
}

resource "google_project_iam_member" "reasoning_engine_bigquery_job_user" {
  project = "your-billing-project"
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:service-${data.google_project.finops_stage.number}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
}
```

---

### 2. Recommender API

**Tool:** `get_recommendations`

**Purpose:** Fetch cost optimization recommendations across monitored projects

**Resources:**
- Queried recommenders:
  - Compute (VMs, disks, addresses, images)
  - Cloud SQL (idle, overprovisioned instances)
  - Cloud Billing (commitment recommendations)
  - BigQuery (capacity commitments)
  - IAM policies
  - Logging

**Required Role:**
- `roles/recommender.viewer` - Read recommendations

**Status:** Required — grant at the organization level or on each project in `GCP_PROJECT_SCOPE`.

If granted at the org level, no per-project configuration is needed.

---

### 3. Cloud Storage

**Tool:** `inspect_gcs_storage`

**Purpose:** List buckets and read bucket metadata (storage class, autoclass, lifecycle rules, object counts)

**Required Role:**
- `roles/storage.objectViewer` - List buckets and read bucket metadata

**Scope:** Each project where buckets should be inspected

**Terraform:**

```hcl
# Grant Storage access on monitored projects
locals {
  monitored_projects = [
    "your-project-id",
    "your-project-b",
    # Add additional projects from GCP_PROJECT_SCOPE here
  ]
}

resource "google_project_iam_member" "reasoning_engine_storage_viewer" {
  for_each = toset(local.monitored_projects)
  
  project = each.value
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:service-${data.google_project.finops_stage.number}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
}
```

---

### 4. Cloud Monitoring

**Tool:** `inspect_gcs_storage` (for bucket object counts)

**Purpose:** Read GCS object count metrics from Cloud Monitoring

**Required Role:**
- `roles/monitoring.viewer` - Read monitoring metrics

**Scope:** Each project where bucket metrics should be queried

**Terraform:**

```hcl
# Grant Monitoring access on monitored projects
resource "google_project_iam_member" "reasoning_engine_monitoring_viewer" {
  for_each = toset(local.monitored_projects)
  
  project = each.value
  role    = "roles/monitoring.viewer"
  member  = "serviceAccount:service-${data.google_project.finops_stage.number}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
}
```

---

## Complete Terraform Example

```hcl
# Complete IAM configuration for gcp-finops-agent Reasoning Engine

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# Fetch the Agent Engine service account project number
data "google_project" "finops_stage" {
  project_id = "your-project-id"
}

locals {
  # Service account created by Agent Engine
  reasoning_engine_sa = "serviceAccount:service-${data.google_project.finops_stage.number}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
  
  # Projects to monitor (should match GCP_PROJECT_SCOPE env var)
  monitored_projects = [
    "your-project-id",
    "your-project-b",
  ]
}

# ─── BigQuery Billing Export (your-billing-project) ────────────────────────────

resource "google_project_iam_member" "bigquery_data_viewer" {
  project = "your-billing-project"
  role    = "roles/bigquery.dataViewer"
  member  = local.reasoning_engine_sa
}

resource "google_project_iam_member" "bigquery_job_user" {
  project = "your-billing-project"
  role    = "roles/bigquery.jobUser"
  member  = local.reasoning_engine_sa
}

# ─── Cloud Storage (monitored projects) ─────────────────────────────────────

resource "google_project_iam_member" "storage_viewer" {
  for_each = toset(local.monitored_projects)
  
  project = each.value
  role    = "roles/storage.objectViewer"
  member  = local.reasoning_engine_sa
}

# ─── Cloud Monitoring (monitored projects) ──────────────────────────────────

resource "google_project_iam_member" "monitoring_viewer" {
  for_each = toset(local.monitored_projects)
  
  project = each.value
  role    = "roles/monitoring.viewer"
  member  = local.reasoning_engine_sa
}

# ─── Recommender API ────────────────────────────────────────────────────────
# Already granted at org level - no additional configuration needed
```

---

## Permission Levels Summary

| Resource | Role | Level | Status |
|----------|------|-------|--------|
| **BigQuery Billing** | `roles/bigquery.dataViewer` | Project (`your-billing-project`) | Required |
| **BigQuery Jobs** | `roles/bigquery.jobUser` | Project (`your-billing-project`) | Required |
| **Recommender** | `roles/recommender.viewer` | Organization or per-project | Required |
| **Cloud Storage** | `roles/storage.objectViewer` | Project (each monitored) | Required |
| **Cloud Monitoring** | `roles/monitoring.viewer` | Project (each monitored) | Required |

---

## Minimal Custom Roles (Alternative)

If you prefer tighter security with custom roles instead of predefined roles:

### Custom Role: Billing Export Reader

**On `your-billing-project`:**

```hcl
resource "google_project_iam_custom_role" "billing_export_reader" {
  project     = "your-billing-project"
  role_id     = "billingExportReader"
  title       = "Billing Export Reader"
  description = "Read-only access to billing export tables"
  
  permissions = [
    "bigquery.tables.getData",
    "bigquery.jobs.create",
    "bigquery.jobs.get",
  ]
}

resource "google_project_iam_member" "custom_billing_reader" {
  project = "your-billing-project"
  role    = google_project_iam_custom_role.billing_export_reader.id
  member  = local.reasoning_engine_sa
}
```

### Custom Role: FinOps Reader

**On monitored projects:**

```hcl
resource "google_project_iam_custom_role" "finops_reader" {
  for_each = toset(local.monitored_projects)
  
  project     = each.value
  role_id     = "finopsReader"
  title       = "FinOps Reader"
  description = "Read-only access for FinOps monitoring"
  
  permissions = [
    "storage.buckets.list",
    "storage.buckets.get",
    "monitoring.timeSeries.list",
  ]
}

resource "google_project_iam_member" "custom_finops_reader" {
  for_each = toset(local.monitored_projects)
  
  project = each.value
  role    = google_project_iam_custom_role.finops_reader[each.key].id
  member  = local.reasoning_engine_sa
}
```

---

## Deployment Checklist

Before deploying the gcp-finops-agent agent, ensure:

- [ ] Service account has `roles/bigquery.dataViewer` on `your-billing-project`
- [ ] Service account has `roles/bigquery.jobUser` on `your-billing-project`
- [ ] Service account has `roles/storage.objectViewer` on all monitored projects
- [ ] Service account has `roles/monitoring.viewer` on all monitored projects
- [ ] `roles/recommender.viewer` is confirmed at org level (already applied)
- [ ] `GCP_PROJECT_SCOPE` environment variable matches Terraform `monitored_projects` list

---

## Troubleshooting

### "Permission denied" errors on BigQuery queries

**Symptom:** Tool fails with `403 Forbidden` or `Access Denied` on billing tables

**Solution:** Verify the service account has both `bigquery.dataViewer` AND `bigquery.jobUser` on `your-billing-project`

### Recommendations returning empty

**Symptom:** `get_recommendations` returns no results

**Solution:** Confirm `roles/recommender.viewer` at org level is applied. Verify with:

```bash
gcloud organizations get-iam-policy <ORG_ID> \
  --flatten="bindings[].members" \
  --filter="bindings.members:service-<PROJECT_NUMBER>@gcp-sa-aiplatform-re.iam.gserviceaccount.com" \
  --format="table(bindings.role)"
```

### GCS bucket inspection fails

**Symptom:** `inspect_gcs_storage` returns permission errors

**Solution:** Grant `roles/storage.objectViewer` on the project containing the buckets

### Object counts missing or zero

**Symptom:** Bucket inspection succeeds but `object_count` field is missing or shows 0

**Solution:** Grant `roles/monitoring.viewer` on the project. Note that new/empty buckets may legitimately have no metrics yet.

---

## Security Notes

1. **Read-Only Access:** All roles are read-only. The agent cannot modify resources.
2. **Project Scope:** Permissions are scoped to specific projects, not org-wide (except Recommender).
3. **No Secrets:** Billing table identifiers are supplied via env vars (not embedded in code).
4. **Audit Logging:** BigQuery queries and API calls are logged in Cloud Audit Logs.

---

## References

- [Agent Engine Service Account](https://cloud.google.com/vertex-ai/docs/reasoning-engine/deploy#service-account)
- [BigQuery IAM Roles](https://cloud.google.com/bigquery/docs/access-control)
- [Recommender IAM Roles](https://cloud.google.com/recommender/docs/access-control)
- [Cloud Storage IAM Roles](https://cloud.google.com/storage/docs/access-control/iam-roles)
- [Cloud Monitoring IAM Roles](https://cloud.google.com/monitoring/access-control)
