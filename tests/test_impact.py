"""Unit tests for the B5 impact evaluation model."""

import pytest

from models.impact import (
    percentage_reduction,
    simulate_inventory,
    simulate_expiry,
    forecast_error,
    calculate_impact,
)


def test_percentage_reduction():
    """Verify a standard percentage reduction."""
    assert percentage_reduction(100, 40) == 60.0


def test_zero_baseline():
    """Prevent division by zero."""
    assert percentage_reduction(0, 0) is None


def test_no_improvement():
    """Identical results should produce zero improvement."""
    assert percentage_reduction(50, 50) == 0.0


def test_negative_improvement():
    """Identify deterioration in KPI performance."""
    assert percentage_reduction(50, 75) == -50.0


def test_inventory_sufficient_stock():
    """No demand should be lost when stock is sufficient."""
    result = simulate_inventory(
        demand=[10, 10, 10],
        initial_stock=100,
        reorder_point=0,
        order_quantity=50,
        lead_time=3
    )

    assert result == 0


def test_inventory_insufficient_stock():
    """Calculate unfulfilled demand correctly."""
    result = simulate_inventory(
        demand=[10, 10, 10],
        initial_stock=15,
        reorder_point=0,
        order_quantity=50,
        lead_time=3
    )

    assert result == 15


def test_proactive_replenishment():
    """Compare reactive and proactive replenishment."""
    demand = [10] * 14

    before = simulate_inventory(
        demand, 30, 0, 50, 3
    )

    after = simulate_inventory(
        demand, 30, 40, 50, 3
    )

    assert after < before


def test_expiry_comparison():
    """Verify that FEFO reduces expiry in the scenario."""
    batches = [
        {"received": 1, "expiry": 20, "quantity": 50},
        {"received": 2, "expiry": 5, "quantity": 40}
    ]

    demand = [10] * 10

    fifo = simulate_expiry(batches, demand, "FIFO")
    fefo = simulate_expiry(batches, demand, "FEFO")

    assert fifo == 40
    assert fefo == 0


def test_original_batch_data_unchanged():
    """Ensure simulations do not modify the original data."""
    batches = [
        {"received": 1, "expiry": 10, "quantity": 50}
    ]

    simulate_expiry(batches, [10, 10], "FEFO")

    assert batches[0]["quantity"] == 50


def test_constant_demand_forecast():
    """Constant demand should produce zero forecast error."""
    demand = [20, 20, 20, 20, 20, 20]

    assert forecast_error(demand, "naive") == 0
    assert forecast_error(demand, "moving_average") == 0


def test_naive_forecast_error():
    """Verify MAE against a manually calculated result."""
    demand = [10, 20, 30, 40, 50, 60]

    assert forecast_error(demand, "naive") == 10.0


def test_moving_average_forecast_error():
    """Verify moving average MAE."""
    demand = [10, 20, 30, 40, 50, 60]

    assert forecast_error(
        demand, "moving_average"
    ) == 20.0


def test_impact_result_count():
    """The impact model should return three KPIs."""
    results = calculate_impact()

    assert len(results) == 3


def test_impact_result_structure():
    """Verify that all required display fields are present."""
    results = calculate_impact()

    required_fields = {
        "name",
        "unit",
        "before",
        "after",
        "improvement",
        "description"
    }

    for result in results:
        assert required_fields.issubset(result.keys())


def test_impact_calculations():
    """Verify consistency of calculated improvement values."""
    for result in calculate_impact():

        before = result["before"]
        after = result["after"]

        if before == 0:
            assert result["improvement"] is None
        else:
            expected = round(
                (before - after) / before * 100, 2
            )

            assert result["improvement"] == pytest.approx(
                expected
            )
            