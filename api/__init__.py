"""JSON REST API for the Pharmaceutical Stock Level Tracker (rubric B2).

Every endpoint lives under /api and returns JSON in the same shape:

    one record:   {"data": {...}}
    a list:       {"data": [...], "page": 1, "size": 20, "total": 12, "pages": 1}
    an error:     {"error": {"code": 400, "message": "...", "details": {...}}}

The endpoints are split by resource:
    api/products.py   /api/products, /api/categories
    api/suppliers.py  /api/suppliers
    api/stock.py      /api/stock/receive, /api/stock/dispense
    api/alerts.py     /api/alerts, /api/kpis
"""
import logging
import math
from datetime import date, datetime
from decimal import Decimal

from flask import Blueprint, jsonify, request, session

log = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__, url_prefix="/api")

# Until login is built, stock movements are recorded against the seeded
# admin user (users.user_id = 1). Once login stores the user's id in the
# session, current_user_id() picks it up automatically.
DEMO_USER_ID = 1


def current_user_id():
    return session.get("user_id", DEMO_USER_ID)


def to_json(value):
    """Make database values JSON-friendly: Decimal -> number,
    date -> "2026-11-23", datetime -> "2026-11-23T10:15:00"."""
    if isinstance(value, dict):
        return {k: to_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json(v) for v in value]
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def ok(data, status=200, headers=None):
    """A successful response with one record (or any object)."""
    return jsonify({"data": to_json(data)}), status, headers or {}


def paged(rows, total, page, size):
    """A successful response with one page of a list."""
    return jsonify({
        "data": to_json(rows),
        "page": page,
        "size": size,
        "total": total,
        "pages": math.ceil(total / size) if total else 0,
    })


@api_bp.after_request
def log_request(response):
    """Write one log line per API call, e.g. 'POST /api/stock/dispense -> 200'."""
    log.info("%s %s -> %s", request.method, request.full_path.rstrip("?"), response.status_code)
    return response


# The route modules import api_bp from this file, so they are imported last.
from api import alerts, products, stock, suppliers  # noqa: E402,F401
