"""Controlled KPI comparisons for evaluating potential application impact.

All scenarios use illustrative data and do not represent measured
performance at an actual pharmacy.
"""


def percentage_reduction(before, after):
    """Calculate the percentage reduction relative to the baseline."""
    if before == 0:
        return None

    return round((before - after) / before * 100, 2)


def simulate_inventory(demand, initial_stock, reorder_point,
                       order_quantity, lead_time):
    """Simulate inventory replenishment and calculate unfulfilled demand."""

    stock = initial_stock
    unfulfilled_demand = 0
    outstanding_orders = []

    for day, daily_demand in enumerate(demand):

        # Receive orders arriving on the current day.
        stock += sum(
            quantity for arrival, quantity in outstanding_orders
            if arrival == day
        )

        outstanding_orders = [
            (arrival, quantity)
            for arrival, quantity in outstanding_orders
            if arrival > day
        ]

        # Fulfil demand using the available inventory.
        fulfilled = min(stock, daily_demand)
        stock -= fulfilled
        unfulfilled_demand += daily_demand - fulfilled

        # Place a replenishment order when the threshold is reached.
        inventory_position = stock + sum(
            quantity for _, quantity in outstanding_orders
        )

        if inventory_position <= reorder_point:
            outstanding_orders.append(
                (day + lead_time, order_quantity)
            )

    return unfulfilled_demand


def simulate_expiry(batches, demand, method):
    """Compare expired stock under FIFO and FEFO dispensing."""

    batches = [batch.copy() for batch in batches]
    expired_units = 0

    for day, daily_demand in enumerate(demand, start=1):

        # Remove stock that has reached its expiry date.
        for batch in batches:
            if batch["expiry"] <= day:
                expired_units += batch["quantity"]
                batch["quantity"] = 0

        # Select the appropriate dispensing sequence.
        if method == "FEFO":
            batches.sort(key=lambda batch: batch["expiry"])
        else:
            batches.sort(key=lambda batch: batch["received"])

        # Dispense available stock.
        remaining_demand = daily_demand

        for batch in batches:
            quantity = min(
                batch["quantity"], remaining_demand
            )

            batch["quantity"] -= quantity
            remaining_demand -= quantity

            if remaining_demand == 0:
                break

    return expired_units


def forecast_error(demand, method, window=3):
    """Calculate mean absolute error over identical evaluation periods."""

    errors = []

    for index in range(window, len(demand)):

        if method == "naive":
            forecast = demand[index - 1]
        else:
            historical_demand = demand[index - window:index]
            forecast = sum(historical_demand) / window

        errors.append(abs(demand[index] - forecast))

    return round(sum(errors) / len(errors), 2)


def build_kpi(name, unit, before, after, description):
    """Create a consistently formatted KPI result."""

    return {
        "name": name,
        "unit": unit,
        "before": before,
        "after": after,
        "improvement": percentage_reduction(before, after),
        "description": description
    }


def calculate_impact():
    """Generate the before-and-after KPI comparison results."""

    # Scenario 1: Inventory replenishment.
    demand = [
        12, 15, 11, 14, 18, 13, 16,
        12, 20, 15, 14, 17, 13, 16
    ]

    before_stockouts = simulate_inventory(
        demand,
        initial_stock=50,
        reorder_point=0,
        order_quantity=60,
        lead_time=3
    )

    after_stockouts = simulate_inventory(
        demand,
        initial_stock=50,
        reorder_point=55,
        order_quantity=60,
        lead_time=3
    )

    # Scenario 2: Pharmaceutical expiry management.
    batches = [
        {"received": 1, "expiry": 20, "quantity": 50},
        {"received": 2, "expiry": 5, "quantity": 40}
    ]

    expiry_demand = [10] * 10

    before_expiry = simulate_expiry(
        batches, expiry_demand, "FIFO"
    )

    after_expiry = simulate_expiry(
        batches, expiry_demand, "FEFO"
    )

    # Scenario 3: Demand forecasting.
    historical_demand = [
        40, 55, 42, 58, 45, 60,
        48, 57, 44, 59, 47, 55
    ]

    before_error = forecast_error(
        historical_demand, "naive"
    )

    after_error = forecast_error(
        historical_demand, "moving_average"
    )

    return [
        build_kpi(
            "Unfulfilled demand",
            "units",
            before_stockouts,
            after_stockouts,
            "Reactive replenishment compared with proactive "
            "reorder point management."
        ),
        build_kpi(
            "Expired stock",
            "units",
            before_expiry,
            after_expiry,
            "FIFO dispensing compared with FEFO dispensing."
        ),
        build_kpi(
            "Forecast error (MAE)",
            "units",
            before_error,
            after_error,
            "Previous-period forecasting compared with a "
            "three-period moving average."
        )
    ]