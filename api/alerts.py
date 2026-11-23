"""Alerts and KPIs.

GET    /api/alerts          list (page, size, status, type)
PATCH  /api/alerts/<id>     acknowledge or resolve an alert
GET    /api/kpis            headline numbers for the dashboard
"""
import logging

from api import api_bp, current_user_id, ok, paged
from api.errors import ApiError
from api.validators import Checker, get_json_body, pagination, query_choice
from models import inventory
from services import alerts as alert_service

log = logging.getLogger(__name__)


@api_bp.get("/alerts")
def list_alerts():
    """Query parameters (optional): page, size,
    status (open | acknowledged | resolved), type (low_stock | reorder | expiry_risk | expired)."""
    page, size, offset = pagination()
    status = query_choice("status", alert_service.ALERT_STATUSES)
    alert_type = query_choice("type", alert_service.ALERT_TYPES)
    rows, total = alert_service.list_alerts(status, alert_type, limit=size, offset=offset)
    return paged(rows, total, page, size)


@api_bp.patch("/alerts/<int:alert_id>")
def update_alert(alert_id):
    """Body: {"status": "acknowledged"} or {"status": "resolved"} (or "open")."""
    c = Checker(get_json_body(), allowed=("status",))
    status = c.string("status", required=True, choices=alert_service.ALERT_STATUSES)
    c.done()

    if alert_service.get_alert(alert_id) is None:
        raise ApiError(404, f"Alert {alert_id} not found")
    alert_service.set_alert_status(alert_id, status, current_user_id())
    log.info("Alert %s set to %s", alert_id, status)
    return ok(alert_service.get_alert(alert_id))


@api_bp.get("/kpis")
def kpis():
    """Live KPIs: products per reorder status, stock value, units expiring in
    30 days, units dispensed in 30 days, open alerts."""
    return ok(inventory.dashboard_kpis())
