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


def create_product(sku, name, category_id, unit_cost, unit_price, strength=None,
                   dosage_form="tablet", pack_size=1, service_level=0.95,
                   reorder_point_override=None, shelf_life_days=730):
    """Insert a product and return its new product_id.
    A duplicate SKU raises pymysql.err.IntegrityError (API should return 409)."""
    with transaction() as cur:
        cur.execute(
            """INSERT INTO products (sku, name, strength, dosage_form, pack_size, category_id,
                                     unit_cost, unit_price, service_level,
                                     reorder_point_override, shelf_life_days)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (sku, name, strength, dosage_form, pack_size, category_id, unit_cost,
             unit_price, service_level, reorder_point_override, shelf_life_days),
        )
        return cur.lastrowid


def update_reorder_settings(product_id, reorder_point_override=None, service_level=None):
    """Pharmacist changes a product's threshold (Objective 2).

    reorder_point_override: whole units, or None to go back to the
    calculated reorder point. service_level: optional, between 0 and 1.
    Returns the product's new position, or None if it doesn't exist."""
    if reorder_point_override is not None and (
            not isinstance(reorder_point_override, int) or reorder_point_override < 0):
        raise ValueError("reorder_point_override must be a whole number >= 0, or None")
    if service_level is not None:
        replenishment.z_score(service_level)          # raises ValueError if not 0 < x < 1
    with transaction() as cur:
        cur.execute(
            """UPDATE products
               SET reorder_point_override = %s,
                   service_level = COALESCE(%s, service_level)
               WHERE product_id = %s""",
            (reorder_point_override, service_level, product_id),
        )
    product = get_product(product_id)
    if product:
        refresh_stock_alert(product_id, product)
    return product


def receive_stock(product_id, supplier_id, batch_number, expiry_date, quantity,
                  unit_cost, user_id, po_id=None):
    """Goods receiving: create a batch and log a 'receipt' movement in one
    transaction. Returns the new batch_id."""
    with transaction() as cur:
        cur.execute(
            """INSERT INTO batches (product_id, supplier_id, po_id, batch_number, expiry_date,
                                    quantity_received, quantity_on_hand, unit_cost)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (product_id, supplier_id, po_id, batch_number, expiry_date, quantity, quantity, unit_cost),
        )
        batch_id = cur.lastrowid
        cur.execute(
            """INSERT INTO stock_movements (batch_id, movement_type, quantity, reference, user_id)
               VALUES (%s, 'receipt', %s, %s, %s)""",
            (batch_id, quantity, f"PO-{po_id}" if po_id else "Direct receipt", user_id),
        )
    refresh_stock_alert(product_id)
    return batch_id


def dispense(product_id, quantity, user_id, reference=None):
    """Dispense stock First-Expiry-First-Out using models/expiry.allocate_fefo.

    The product's batches are locked (SELECT ... FOR UPDATE) so two staff
    members cannot dispense the same units at once. Raises ValueError if
    there is not enough unexpired stock; nothing changes in that case.
    Returns the allocation list from allocate_fefo."""
    if not isinstance(quantity, int) or quantity <= 0:
        raise ValueError("quantity must be a whole number greater than 0")
    with transaction() as cur:
        cur.execute(
            """SELECT batch_id, expiry_date, quantity_on_hand
               FROM batches
               WHERE product_id = %s AND quantity_on_hand > 0
               ORDER BY expiry_date
               FOR UPDATE""",
            (product_id,),
        )
        batches = [{"batch_id": b["batch_id"], "expiry_date": b["expiry_date"],
                    "quantity": b["quantity_on_hand"]} for b in cur.fetchall()]
        plan = expiry.allocate_fefo(batches, quantity)
        if plan["unfulfilled_quantity"] > 0:
            raise ValueError(f"Only {plan['allocated_quantity']} unexpired units available")

        for a in plan["allocations"]:
            cur.execute(
                "UPDATE batches SET quantity_on_hand = quantity_on_hand - %s WHERE batch_id = %s",
                (a["allocated_quantity"], a["batch_id"]),
            )
            cur.execute(
                """INSERT INTO stock_movements (batch_id, movement_type, quantity, reference, user_id)
                   VALUES (%s, 'dispense', %s, %s, %s)""",
                (a["batch_id"], a["allocated_quantity"], reference, user_id),
            )
    refresh_stock_alert(product_id)
    return plan["allocations"]