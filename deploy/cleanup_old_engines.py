#!/usr/bin/env python3
"""Clean up Reasoning Engine deployments older than specified hours.

This script is run automatically in the CI/CD pipeline before deployment.

Usage:
    python deploy/cleanup_old_engines.py --project PROJECT_ID --region REGION [--max-age-hours 24]
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone

from google.cloud import aiplatform


def cleanup_old_engines(project: str, region: str, max_age_hours: int = 24):
    """Delete Reasoning Engines older than max_age_hours."""
    print(f"🔍 Scanning Reasoning Engines in {project}/{region}...")
    print(f"   Threshold: {max_age_hours} hours")
    print()

    aiplatform.init(project=project, location=region)

    # List all Reasoning Engines
    parent = f"projects/{project}/locations/{region}"
    client = aiplatform.gapic.ReasoningEngineServiceClient(
        client_options={"api_endpoint": f"{region}-aiplatform.googleapis.com"}
    )

    try:
        request = aiplatform.gapic.ListReasoningEnginesRequest(parent=parent)
        engines = list(client.list_reasoning_engines(request=request))
    except Exception as e:
        print(f"❌ Failed to list Reasoning Engines: {e}")
        sys.exit(1)

    if not engines:
        print("✅ No existing Reasoning Engines found. Nothing to clean up.")
        return

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    deleted_count = 0
    kept_count = 0
    error_count = 0

    for engine in engines:
        display_name = engine.display_name or "unnamed"
        resource_name = engine.name

        # Get most recent timestamp
        create_time = engine.create_time
        update_time = engine.update_time
        most_recent = max(create_time, update_time) if update_time else create_time

        # Make timezone-aware if needed
        if most_recent.tzinfo is None:
            most_recent = most_recent.replace(tzinfo=timezone.utc)

        age_hours = (datetime.now(timezone.utc) - most_recent).total_seconds() / 3600

        if most_recent <= cutoff:
            # Old deployment - delete it
            print(f"🗑️  Deleting: {display_name} (age: {age_hours:.1f}h)")
            print(f"   Resource: {resource_name}")

            try:
                delete_request = aiplatform.gapic.DeleteReasoningEngineRequest(
                    name=resource_name,
                    force=True,  # Force delete child resources (sessions)
                )
                operation = client.delete_reasoning_engine(request=delete_request)
                operation.result(timeout=120)  # Wait up to 2 minutes
                print("   ✅ Deleted successfully")
                deleted_count += 1
            except Exception as e:
                print(f"   ❌ Error: {e}")
                error_count += 1
        else:
            # Recent deployment - keep it
            print(f"✅ Keeping: {display_name} (age: {age_hours:.1f}h)")
            kept_count += 1

    print()
    print("=" * 60)
    print("CLEANUP SUMMARY")
    print("=" * 60)
    print(f"Total engines: {len(engines)}")
    print(f"Kept (recent): {kept_count}")
    print(f"Deleted (old): {deleted_count}")
    if error_count > 0:
        print(f"Errors: {error_count}")

    if error_count > 0:
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Clean up old Reasoning Engine deployments"
    )
    parser.add_argument("--project", required=True, help="GCP project ID")
    parser.add_argument("--region", required=True, help="GCP region")
    parser.add_argument(
        "--max-age-hours",
        type=int,
        default=24,
        help="Maximum age in hours (default: 24)",
    )
    args = parser.parse_args()

    cleanup_old_engines(
        project=args.project,
        region=args.region,
        max_age_hours=args.max_age_hours,
    )


if __name__ == "__main__":
    main()
