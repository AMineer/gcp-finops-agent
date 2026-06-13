"""Unit tests for recommendation fetching logic."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gcp_finops_agent.gcp import (
    RECOMMENDER_IDS,
    RECOMMENDER_LOCATIONS,
    get_recommendations,
)


@pytest.mark.asyncio
async def test_get_recommendations_fan_out_coverage(monkeypatch):
    """Verify get_recommendations queries all (project, location, recommender_id) combinations.

    Regression test: Ensures we don't hardcode "global" or drop recommenders.
    """
    # Mock config with 2 test projects
    test_projects = ["project-1", "project-2"]

    mock_config = MagicMock()
    mock_config.gcp_project_scope = test_projects

    monkeypatch.setattr("gcp_finops_agent.gcp.get_config", lambda: mock_config)

    # Mock RecommenderAsyncClient
    mock_client = AsyncMock()

    # Track which (project, location, recommender_id) combinations were queried
    queried_combinations = []

    async def mock_list_recommendations(request):
        """Mock list_recommendations that tracks what was queried."""
        # Extract project, location, recommender_id from parent
        # Format: "projects/{project}/locations/{location}/recommenders/{recommender_id}"
        parts = request.parent.split("/")
        project_id = parts[1]
        location = parts[3]
        recommender_id = parts[5]

        queried_combinations.append((project_id, location, recommender_id))

        # Return empty async iterator
        async def empty_iter():
            if False:
                yield

        return empty_iter()

    mock_client.list_recommendations = mock_list_recommendations

    with patch("gcp_finops_agent.gcp.recommender_v1.RecommenderAsyncClient", return_value=mock_client):
        # Call get_recommendations
        await get_recommendations()

    # Verify all combinations were queried
    expected_combinations = [
        (project, location, recommender_id)
        for project in test_projects
        for location in RECOMMENDER_LOCATIONS
        for recommender_id in RECOMMENDER_IDS
    ]

    # Sort both lists for comparison
    queried_combinations.sort()
    expected_combinations.sort()

    assert queried_combinations == expected_combinations, (
        f"Fan-out coverage mismatch.\n"
        f"Expected {len(expected_combinations)} queries, got {len(queried_combinations)}.\n"
        f"Missing: {set(expected_combinations) - set(queried_combinations)}\n"
        f"Extra: {set(queried_combinations) - set(expected_combinations)}"
    )


@pytest.mark.asyncio
async def test_get_recommendations_semaphore_limits_concurrency(monkeypatch):
    """Verify semaphore caps concurrent requests to avoid overwhelming API."""
    # Mock config with 3 projects
    test_projects = ["p1", "p2", "p3"]

    mock_config = MagicMock()
    mock_config.gcp_project_scope = test_projects

    monkeypatch.setattr("gcp_finops_agent.gcp.get_config", lambda: mock_config)

    # Track max concurrent requests
    concurrent_count = 0
    max_concurrent = 0

    mock_client = AsyncMock()

    async def mock_list_recommendations(request):
        nonlocal concurrent_count, max_concurrent

        concurrent_count += 1
        max_concurrent = max(max_concurrent, concurrent_count)

        # Simulate some work
        import asyncio
        await asyncio.sleep(0.001)

        concurrent_count -= 1

        # Return empty async iterator
        async def empty_iter():
            if False:
                yield

        return empty_iter()

    mock_client.list_recommendations = mock_list_recommendations

    with patch("gcp_finops_agent.gcp.recommender_v1.RecommenderAsyncClient", return_value=mock_client):
        await get_recommendations()

    # With 3 projects × 3 locations × 11 recommenders = 99 total requests
    # Semaphore is set to 50, so max concurrent should be ≤ 50
    assert max_concurrent <= 50, (
        f"Semaphore failed to cap concurrency: {max_concurrent} concurrent requests"
    )

    # But should have been > 1 (i.e., actually concurrent, not serial)
    assert max_concurrent > 1, (
        f"No concurrency detected: max_concurrent={max_concurrent}"
    )


@pytest.mark.asyncio
async def test_get_recommendations_filters_by_min_savings(monkeypatch):
    """Verify min_savings filter works correctly."""
    mock_config = MagicMock()
    mock_config.gcp_project_scope = ["test-project"]

    monkeypatch.setattr("gcp_finops_agent.gcp.get_config", lambda: mock_config)

    # Mock client that returns 3 recommendations with different savings
    # Only return recommendations for one specific (location, recommender) combo to avoid duplicates
    mock_client = AsyncMock()

    mock_rec_1 = MagicMock()
    mock_rec_1.description = "Low savings rec"
    mock_rec_1.priority = MagicMock()
    mock_rec_1.primary_impact = MagicMock()
    mock_rec_1.primary_impact.cost_projection.cost.units = 10  # $10/month
    mock_rec_1.primary_impact.cost_projection.cost.nanos = 0
    mock_rec_1.primary_impact.cost_projection.cost.currency_code = "USD"

    mock_rec_2 = MagicMock()
    mock_rec_2.description = "Medium savings rec"
    mock_rec_2.priority = MagicMock()
    mock_rec_2.primary_impact = MagicMock()
    mock_rec_2.primary_impact.cost_projection.cost.units = 100  # $100/month
    mock_rec_2.primary_impact.cost_projection.cost.nanos = 0
    mock_rec_2.primary_impact.cost_projection.cost.currency_code = "USD"

    mock_rec_3 = MagicMock()
    mock_rec_3.description = "High savings rec"
    mock_rec_3.priority = MagicMock()
    mock_rec_3.primary_impact = MagicMock()
    mock_rec_3.primary_impact.cost_projection.cost.units = 1000  # $1000/month
    mock_rec_3.primary_impact.cost_projection.cost.nanos = 0
    mock_rec_3.primary_impact.cost_projection.cost.currency_code = "USD"

    async def mock_list_recommendations(request):
        # Only return recommendations for a specific location/recommender combo
        # to avoid getting duplicates from the (project × location × recommender) fan-out
        if "us-central1" in request.parent and "MachineTypeRecommender" in request.parent:
            async def iter_recs():
                yield mock_rec_1
                yield mock_rec_2
                yield mock_rec_3
            return iter_recs()
        else:
            # Return empty for all other combinations
            async def empty_iter():
                if False:
                    yield
            return empty_iter()

    mock_client.list_recommendations = mock_list_recommendations

    with patch("gcp_finops_agent.gcp.recommender_v1.RecommenderAsyncClient", return_value=mock_client):
        # Query with min_savings=50 should filter out the $10 rec
        result = await get_recommendations(min_savings=50.0)

    # Should have 2 recommendations (100 and 1000, not 10)
    assert len(result) == 2, f"Expected 2 recs with savings ≥ $50, got {len(result)}"

    # Verify they're sorted by savings (highest first)
    assert result[0].estimated_monthly_savings == 1000.0
    assert result[1].estimated_monthly_savings == 100.0


@pytest.mark.asyncio
async def test_cloudsql_recommender_id_format(monkeypatch):
    """Regression test: Ensure Cloud SQL recommender IDs use correct format.

    The correct format is 'google.cloudsql' (one word), not 'google.cloud.sql'.
    """
    # Check that RECOMMENDER_IDS has the correct Cloud SQL format
    cloudsql_recommenders = [
        rid for rid in RECOMMENDER_IDS
        if "cloudsql" in rid.lower() or "cloud.sql" in rid.lower()
    ]

    # Should have Cloud SQL recommenders
    assert len(cloudsql_recommenders) > 0, "No Cloud SQL recommenders found"

    # All should use 'cloudsql' (one word), not 'cloud.sql'
    for recommender_id in cloudsql_recommenders:
        assert "google.cloudsql" in recommender_id, (
            f"Cloud SQL recommender uses wrong format: {recommender_id}\n"
            f"Should be 'google.cloudsql', not 'google.cloud.sql'"
        )
        assert "google.cloud.sql" not in recommender_id, (
            f"Cloud SQL recommender has typo (extra dots): {recommender_id}"
        )


def test_recommender_locations_includes_global():
    """Ensure RECOMMENDER_LOCATIONS includes 'global' for global recommenders."""
    assert "global" in RECOMMENDER_LOCATIONS, (
        "RECOMMENDER_LOCATIONS must include 'global' for IAM, CUD, and BigQuery recommenders"
    )


def test_recommender_ids_includes_high_value():
    """Verify high-value recommenders are in the list."""
    high_value_recommenders = [
        "google.cloudbilling.commitment.SpendBasedCommitmentRecommender",  # CUDs
        "google.bigquery.capacityCommitments.Recommender",
        "google.iam.policy.Recommender",
    ]

    for recommender in high_value_recommenders:
        assert recommender in RECOMMENDER_IDS, (
            f"Missing high-value recommender: {recommender}"
        )
