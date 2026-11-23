"""Alerts: filtered, paged list and status changes (table `alerts`)."""
from db import query, query_one, transaction

ALERT_STATUSES = ("open", "acknowledged", "resolved")
ALERT_TYPES = ("low_stock", "reorder", "expiry_risk", "expired")


def list_alerts(status=None, alert_type=None, limit=20, offset=0):
    """Return (rows, total) for one page of alerts, most urgent first."""
    where, params = [], []
    if status:
        where.append("a.status = %s")
        params.append(status)
    if alert_type:
        where.append("a.alert_type = %s")
        params.append(alert_type)
    clause = ("WHERE " + " AND ".join(where)) if where else ""

    total = query_one(f"SELECT COUNT(*) AS n FROM alerts a {clause}", params)["n"]
    rows = query(
        f"""SELECT a.alert_id, a.alert_type, a.status, a.message, a.batch_id,
                   a.acknowledged_by, a.resolved_at, a.created_at, a.updated_at,
                   p.product_id, p.sku, p.name AS product_name
            FROM alerts a
            JOIN products p ON p.product_id = a.product_id
            {clause}
            ORDER BY FIELD(a.alert_type, 'reorder', 'expired', 'expiry_risk', 'low_stock'),
                     a.created_at DESC
            LIMIT %s OFFSET %s""",
        params + [limit, offset],
    )
    return rows, total


def get_alert(alert_id):
    return query_one(
        """SELECT a.alert_id, a.alert_type, a.status, a.message, a.batch_id,
                  a.acknowledged_by, a.resolved_at, a.created_at, a.updated_at,
                  p.product_id, p.sku, p.name AS product_name
           FROM alerts a JOIN products p ON p.product_id = a.product_id
           WHERE a.alert_id = %s""",
        (alert_id,),
    )


def set_alert_status(alert_id, status, user_id):
    """Acknowledge or resolve an alert (or re-open it)."""
    with transaction() as cur:
        cur.execute(
            """UPDATE alerts
               SET status = %s,
                   acknowledged_by = CASE WHEN %s = 'open' THEN NULL
                                          ELSE COALESCE(acknowledged_by, %s) END,
                   resolved_at = CASE WHEN %s = 'resolved' THEN NOW() ELSE NULL END
               WHERE alert_id = %s""",
            (status, status, user_id, status, alert_id),
        )
