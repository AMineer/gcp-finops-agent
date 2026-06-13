"""GCS connector for bucket inspection and storage optimization."""

import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

from google.api_core.exceptions import GoogleAPIError, NotFound, PermissionDenied
from google.cloud import monitoring_v3, storage  # type: ignore[attr-defined]
from .sanitize import (
    sanitize_for_llm,
    sanitize_dict_labels,
    MAX_LEN_BUCKET_NAME,
    MAX_LEN_DEFAULT,
)


def _get_bucket_object_count(bucket_name: str, project_id: str = "") -> dict:
    """Query Cloud Monitoring API for bucket object count.

    Uses the storage.googleapis.com/storage/object_count metric which is
    automatically collected for all GCS buckets.

    Args:
        bucket_name: GCS bucket name
        project_id: GCP project ID (optional)

    Returns:
        Dict with 'count' (int) if successful, or 'error' (str) if failed
    """
    try:
        client = monitoring_v3.MetricServiceClient()

        # Determine project name
        if project_id:
            project_name = f"projects/{project_id}"
        else:
            # Use default project from ADC
            storage_client = storage.Client()
            project_name = f"projects/{storage_client.project}"

        # Query last 2 days (GCS metrics are sampled daily)
        now = datetime.utcnow()
        interval = monitoring_v3.TimeInterval(
            {
                "end_time": {"seconds": int(now.timestamp())},
                "start_time": {"seconds": int((now - timedelta(days=2)).timestamp())},
            }
        )

        # Build metric filter (matches working curl pattern)
        metric_filter = (
            f'metric.type="storage.googleapis.com/storage/object_count" '
            f'AND resource.labels.bucket_name="{bucket_name}"'
        )

        results = client.list_time_series(
            request={
                "name": project_name,
                "filter": metric_filter,
                "interval": interval,
            }
        )

        # Get most recent data point
        for result in results:
            if result.points:
                # Object count is an INT64 value
                return {"count": int(result.points[0].value.int64_value)}

        # No data found - bucket may be empty or very new
        return {"count": 0}

    except Exception:
        logger.exception("Cloud Monitoring object count query failed")
        return {"error": "Monitoring API error. Check logs for details."}


async def inspect_gcs_storage(bucket_name: str = "", project_id: str = "") -> dict:
    """Inspect GCS storage - list all buckets or inspect a specific bucket.

    If bucket_name is provided: Returns detailed inspection of that bucket.
    If bucket_name is empty: Returns list of all buckets in the project.

    Args:
        bucket_name: Optional bucket name. If empty, lists all buckets.
        project_id: Optional GCP project ID.

    Returns:
        If bucket_name provided: Dict with detailed bucket config (storage_class,
            autoclass, lifecycle rules, versioning, etc.)
        If bucket_name empty: Dict with list of buckets (bucket_name, location,
            storage_class, created, labels)
    """

    # If no bucket name, list all buckets
    if not bucket_name:
        return await list_buckets(project_id)

    # Otherwise, inspect the specific bucket
    def _get_bucket_info():
        try:
            client = storage.Client(project=project_id if project_id else None)
            bucket = client.get_bucket(bucket_name)

            # Basic bucket info (sanitize all string fields)
            info = {
                "bucket_name": sanitize_for_llm(bucket.name, MAX_LEN_BUCKET_NAME),
                "project_id": sanitize_for_llm(str(bucket.project_number) if bucket.project_number else "unknown", MAX_LEN_DEFAULT),
                "location": sanitize_for_llm(bucket.location, MAX_LEN_DEFAULT),
                "location_type": sanitize_for_llm(bucket.location_type, MAX_LEN_DEFAULT),
                "storage_class": sanitize_for_llm(bucket.storage_class or "STANDARD", MAX_LEN_DEFAULT),
                "created": bucket.time_created.isoformat() if bucket.time_created else None,
            }

            # Autoclass configuration
            autoclass_config = bucket.autoclass_enabled
            info["autoclass_enabled"] = autoclass_config if autoclass_config is not None else False

            if hasattr(bucket, 'autoclass_toggle_time') and bucket.autoclass_toggle_time:
                info["autoclass_toggle_time"] = bucket.autoclass_toggle_time.isoformat()

            # Lifecycle rules (sanitize action types and storage classes)
            lifecycle_rules = bucket.lifecycle_rules
            if lifecycle_rules:
                info["lifecycle_rules"] = []
                for rule in lifecycle_rules:
                    action_type = rule.get("action", {}).get("type")
                    rule_info = {
                        "action": sanitize_for_llm(action_type, MAX_LEN_DEFAULT),
                        "conditions": {}
                    }
                    conditions = rule.get("condition", {})
                    if "age" in conditions:
                        rule_info["conditions"]["age_days"] = conditions["age"]
                    if "matchesStorageClass" in conditions:
                        # Sanitize storage class names in the list
                        storage_classes = conditions["matchesStorageClass"]
                        if isinstance(storage_classes, list):
                            rule_info["conditions"]["storage_classes"] = [
                                sanitize_for_llm(sc, MAX_LEN_DEFAULT) for sc in storage_classes
                            ]
                        else:
                            rule_info["conditions"]["storage_classes"] = storage_classes
                    info["lifecycle_rules"].append(rule_info)
            else:
                info["lifecycle_rules"] = []

            # Versioning
            info["versioning_enabled"] = bucket.versioning_enabled or False

            # Public access prevention
            if hasattr(bucket, 'iam_configuration'):
                iam_config = bucket.iam_configuration
                if hasattr(iam_config, 'public_access_prevention'):
                    info["public_access_prevention"] = sanitize_for_llm(
                        iam_config.public_access_prevention,
                        MAX_LEN_DEFAULT
                    )

            # Labels (sanitize keys and values)
            info["labels"] = sanitize_dict_labels(bucket.labels or {})

            # Object count from Cloud Monitoring (automatically collected metric)
            object_count_result = _get_bucket_object_count(bucket_name, project_id)
            if "count" in object_count_result:
                info["object_count"] = object_count_result["count"]
            elif "error" in object_count_result:
                info["object_count_error"] = object_count_result["error"]

            return {"success": True, "bucket": info}

        except NotFound:
            return {
                "success": False,
                "error": f"Bucket '{bucket_name}' not found. It may not exist or you may lack permissions."
            }
        except PermissionDenied:
            return {
                "success": False,
                "error": f"Permission denied accessing bucket '{bucket_name}'. Ensure storage.buckets.get permission."
            }
        except GoogleAPIError:
            logger.exception("GCS API error inspecting bucket")
            return {"success": False, "error": "GCS API error. Check logs for details."}
        except Exception:
            logger.exception("Failed to inspect bucket")
            return {"success": False, "error": "Failed to inspect bucket. Check logs for details."}

    # Run synchronous GCS call in executor
    loop = asyncio.get_event_loop()
    result: dict = await loop.run_in_executor(None, _get_bucket_info)
    return result


async def list_buckets(project_id: str = "") -> dict:
    """List all GCS buckets in a project.

    Args:
        project_id: GCP project ID. If empty, uses the default project from
            Application Default Credentials.

    Returns:
        Dict with success status and list of buckets, each with:
        - bucket_name: str
        - location: str
        - storage_class: str
        - created: str (ISO timestamp)
        - labels: dict
    """

    def _list_buckets():
        try:
            client = storage.Client(project=project_id if project_id else None)

            buckets = []
            for bucket in client.list_buckets():
                bucket_info = {
                    "bucket_name": sanitize_for_llm(bucket.name, MAX_LEN_BUCKET_NAME),
                    "location": sanitize_for_llm(bucket.location or "unknown", MAX_LEN_DEFAULT),
                    "storage_class": sanitize_for_llm(bucket.storage_class or "STANDARD", MAX_LEN_DEFAULT),
                    "created": bucket.time_created.isoformat() if bucket.time_created else None,
                    "labels": sanitize_dict_labels(bucket.labels or {})
                }
                buckets.append(bucket_info)

            return {
                "success": True,
                "project_id": project_id if project_id else "default",
                "bucket_count": len(buckets),
                "buckets": buckets
            }

        except PermissionDenied:
            return {
                "success": False,
                "error": f"Permission denied listing buckets in project '{project_id}'. Ensure storage.buckets.list permission."
            }
        except GoogleAPIError:
            logger.exception("GCS API error listing buckets")
            return {"success": False, "error": "GCS API error. Check logs for details."}
        except Exception:
            logger.exception("Failed to list buckets")
            return {"success": False, "error": "Failed to list buckets. Check logs for details."}

    # Run synchronous GCS call in executor
    loop = asyncio.get_event_loop()
    result: dict = await loop.run_in_executor(None, _list_buckets)
    return result
