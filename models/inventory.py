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


def list_products(category=None, status=None, search=None, limit=20, offset=0):
    """Dashboard rows with stock, nearest expiry and model-calculated status.
    Filters by category / search in SQL and by status after the model runs.
    Returns (rows, total_count)."""
    if status and status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    where, params = [], []
    if category:
        where.append("category = %s")
        params.append(category)
    if search:
        where.append("(name LIKE %s OR sku LIKE %s)")
        params += [f"%{search}%", f"%{search}%"]
    clause = ("WHERE " + " AND ".join(where)) if where else ""

    rows = _positions(query(f"SELECT * FROM v_product_stock {clause}", params))
    if status:
        rows = [r for r in rows if r["reorder_status"] == status]
    rows.sort(key=lambda r: (STATUSES.index(r["reorder_status"]), r["name"]))
    return rows[int(offset):int(offset) + int(limit)], len(rows)


def get_product(product_id):
    """One product with its stock position and model results, or None."""
    row = query_one("SELECT * FROM v_product_stock WHERE product_id = %s", (product_id,))
    return _positions([row])[0] if row else None


def get_product_batches(product_id, include_empty=False):
    """Batch-level detail for the drill-down view, nearest expiry first, with
    each batch classified by models/expiry.py (expired / expiring_soon / fresh)."""
    rows = query(
        f"""SELECT b.batch_id, b.batch_number, b.quantity_on_hand, b.quantity_received,
                   b.expiry_date, DATEDIFF(b.expiry_date, CURDATE()) AS days_to_expiry,
                   b.received_at, s.name AS supplier
            FROM batches b
            JOIN suppliers s ON s.supplier_id = b.supplier_id
            WHERE b.product_id = %s {'' if include_empty else 'AND b.quantity_on_hand > 0'}
            ORDER BY b.expiry_date""",
        (product_id,),
    )
    for r in rows:
        r["expiry_class"] = expiry.classify_batch(r["expiry_date"])
    return rows


def get_preferred_supplier(product_id):
    """Preferred supplier and lead time for a product (used by the reorder prompt)."""
    return query_one(
        """SELECT s.supplier_id, s.name, ps.lead_time_days, ps.supplier_cost
           FROM product_suppliers ps
           JOIN suppliers s ON s.supplier_id = ps.supplier_id
           WHERE ps.product_id = %s
           ORDER BY ps.is_preferred DESC, ps.lead_time_days
           LIMIT 1""",
        (product_id,),
    )