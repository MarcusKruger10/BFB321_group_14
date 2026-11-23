"""Database access for products, batches, stock movements and alerts.

This module is the bridge between MySQL and the group's supply chain models:
  * models/replenishment.py decides safety stock, reorder point, status and
    the recommended order quantity (EOQ) from the demand history stored here;
  * models/expiry.py allocates stock First-Expiry-First-Out when dispensing;
  * models/demand.py turns dispensing history into a forecast.

Table and column names match database/schema.sql and the ERD. Every query is
parameterised (%s). Routes and API endpoints call these functions instead of
writing SQL themselves.
"""
import math
from datetime import date, timedelta

from db import query, query_one, transaction
from models import demand, expiry, replenishment

HISTORY_DAYS = 90        # days of dispensing history used for demand statistics
LOW_WARNING_DAYS = 3     # "Low" = stock reaches the reorder point within this many days
STATUSES = (replenishment.STATUS_REORDER, replenishment.STATUS_LOW, replenishment.STATUS_SUFFICIENT)


def demand_history(product_ids, days=HISTORY_DAYS):
    """Units dispensed per day for each product over the last `days` complete
    days (oldest first, days with no dispensing filled with 0).

    Returns {product_id: [units_day1, ..., units_dayN]}."""
    product_ids = list(product_ids)
    if not product_ids:
        return {}
    placeholders = ", ".join(["%s"] * len(product_ids))
    rows = query(
        f"""SELECT b.product_id, DATE(sm.moved_at) AS day, SUM(sm.quantity) AS units
            FROM stock_movements sm
            JOIN batches b ON b.batch_id = sm.batch_id
            WHERE sm.movement_type = 'dispense'
              AND b.product_id IN ({placeholders})
              AND sm.moved_at >= CURDATE() - INTERVAL %s DAY
              AND sm.moved_at <  CURDATE()
            GROUP BY b.product_id, DATE(sm.moved_at)""",
        product_ids + [int(days)],
    )
    start = date.today() - timedelta(days=days)
    history = {pid: [0] * days for pid in product_ids}
    for r in rows:
        index = (r["day"] - start).days
        if 0 <= index < days:
            history[r["product_id"]][index] = int(r["units"])  # MySQL SUM returns Decimal
    return history


def _position(row, history):
    """Add the replenishment model's results to one v_product_stock row."""
    avg = demand.average_daily_demand(history)
    std = demand.demand_standard_deviation(history)
    lead_time = row["lead_time_days"] or 0
    stock = int(row["stock_on_hand"])

    ss = replenishment.safety_stock(std, lead_time, float(row["service_level"]))
    calculated_rop = replenishment.reorder_point(avg, lead_time, ss)
    rop = replenishment.effective_threshold(calculated_rop, row["reorder_point_override"])
    status = replenishment.reorder_status(stock, rop, avg, warning_days=LOW_WARNING_DAYS)
    order = replenishment.recommended_order_quantity(
        avg, stock,
        order_cost=float(row["ordering_cost"]),
        holding_cost=float(row["holding_cost_rate"]) * float(row["unit_cost"]),
        shelf_life_days=row["shelf_life_days"],
        pack_size=row["pack_size"],
    )
    days_left = replenishment.days_of_stock(stock, avg)

    result = dict(row)
    result.update(
        stock_on_hand=stock,
        stock_value=float(row["stock_value"]),
        avg_daily_demand=round(avg, 2),
        safety_stock=math.ceil(ss),
        calculated_reorder_point=math.ceil(calculated_rop),
        reorder_point=math.ceil(rop),
        override_active=row["reorder_point_override"] is not None,
        reorder_status=status,
        days_of_stock=None if math.isinf(days_left) else round(days_left, 1),
        days_to_reorder_point=round((stock - rop) / avg, 1) if avg > 0 else None,
        recommended_order_qty=order["order_quantity"],
        eoq=round(order["eoq"], 1),
    )
    return result


def _positions(rows):
    history = demand_history(r["product_id"] for r in rows)
    return [_position(r, history[r["product_id"]]) for r in rows]