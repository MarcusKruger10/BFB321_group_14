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