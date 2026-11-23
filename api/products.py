"""Products and categories.

GET    /api/products                  list (page, size, category, status, search)
GET    /api/products/<id>             one product with stock position and model results
POST   /api/products                  create a product
PATCH  /api/products/<id>             update details and/or the reorder threshold
GET    /api/products/<id>/batches     batches of a product, nearest expiry first
GET    /api/products/<id>/forecast    demand forecast from models/demand.py
GET    /api/categories                all categories
"""
import logging

from flask import request, url_for

from api import api_bp, ok, paged
from api.errors import ApiError
from api.validators import Checker, get_json_body, pagination, query_choice, query_int
from models import inventory
from services import products as product_service

log = logging.getLogger(__name__)


def _product_or_404(product_id):
    product = inventory.get_product(product_id)
    if product is None:
        raise ApiError(404, f"Product {product_id} not found")
    return product


@api_bp.get("/products")
def list_products():
    """List products with stock on hand, nearest expiry and reorder status.

    Query parameters (all optional):
        page, size  - pagination (default page 1, size 20, max 100)
        category    - category name, e.g. Analgesics
        status      - Sufficient | Low | Reorder Needed
        search      - part of the product name or SKU
    """
    page, size, offset = pagination()
    status = query_choice("status", inventory.STATUSES)
    category = request.args.get("category") or None
    search = request.args.get("search") or None
    rows, total = inventory.list_products(category=category, status=status, search=search,
                                          limit=size, offset=offset)
    return paged(rows, total, page, size)


@api_bp.get("/products/<int:product_id>")
def get_product(product_id):
    """One product, including the replenishment model's reorder point,
    safety stock, status and recommended order quantity."""
    return ok(_product_or_404(product_id))


@api_bp.post("/products")
def create_product():
    """Create a product. Required: sku, name, category_id, unit_cost, unit_price.
    Returns 201 with the new product, or 409 if the SKU already exists."""
    c = Checker(get_json_body(), allowed=(
        "sku", "name", "category_id", "unit_cost", "unit_price", "strength", "dosage_form",
        "pack_size", "service_level", "reorder_point_override", "shelf_life_days"))
    fields = {
        "sku": c.string("sku", required=True, max_length=30),
        "name": c.string("name", required=True, max_length=120),
        "category_id": c.integer("category_id", required=True, minimum=1),
        "unit_cost": c.money("unit_cost", required=True),
        "unit_price": c.money("unit_price", required=True),
        "strength": c.string("strength", max_length=40),
        "dosage_form": c.string("dosage_form", choices=product_service.DOSAGE_FORMS) or "tablet",
        "pack_size": c.integer("pack_size", minimum=1) or 1,
        "service_level": c.fraction("service_level") or 0.95,
        "reorder_point_override": c.integer("reorder_point_override", minimum=0),
        "shelf_life_days": c.integer("shelf_life_days", minimum=1, maximum=3650) or 730,
    }
    c.done()

    product_id = inventory.create_product(**fields)
    log.info("Created product %s (%s)", product_id, fields["sku"])
    location = url_for("api.get_product", product_id=product_id)
    return ok(inventory.get_product(product_id), 201, {"Location": location})


@api_bp.patch("/products/<int:product_id>")
def update_product(product_id):
    """Update any of the product's details, and/or its reorder threshold.

    Send only the fields you want to change, e.g. {"reorder_point_override": 150}.
    Set "reorder_point_override": null to go back to the calculated reorder point.
    """
    if not product_service.product_exists(product_id):
        raise ApiError(404, f"Product {product_id} not found")

    c = Checker(get_json_body(), allowed=product_service.EDITABLE + (
        "reorder_point_override", "service_level"))
    changes = {}
    if c.has("name"):
        changes["name"] = c.string("name", required=True, max_length=120)
    if c.has("strength"):
        changes["strength"] = c.string("strength", max_length=40)
    if c.has("dosage_form"):
        changes["dosage_form"] = c.string("dosage_form", required=True,
                                          choices=product_service.DOSAGE_FORMS)
    if c.has("pack_size"):
        changes["pack_size"] = c.integer("pack_size", required=True, minimum=1)
    if c.has("category_id"):
        changes["category_id"] = c.integer("category_id", required=True, minimum=1)
    for money_field in ("unit_cost", "unit_price", "ordering_cost"):
        if c.has(money_field):
            changes[money_field] = c.money(money_field, required=True)
    if c.has("shelf_life_days"):
        changes["shelf_life_days"] = c.integer("shelf_life_days", required=True,
                                               minimum=1, maximum=3650)
    if c.has("is_active"):
        changes["is_active"] = c.boolean("is_active", required=True)
    override = c.integer("reorder_point_override", minimum=0)   # None is allowed (= clear)
    service_level = c.fraction("service_level")
    if not c.data:
        c.errors["body"] = "send at least one field to change"
    c.done()

    product_service.update_product_details(product_id, changes)

    if c.has("reorder_point_override") or c.has("service_level"):
        # keep the current override if the client only changed the service level
        if not c.has("reorder_point_override"):
            override = product_service.get_reorder_override(product_id)
        inventory.update_reorder_settings(product_id, override, service_level)
    elif changes:
        inventory.refresh_stock_alert(product_id)     # e.g. pack size changes the order quantity

    log.info("Updated product %s: %s", product_id, sorted(c.data))
    product = inventory.get_product(product_id)
    if product is None:                                # it was just deactivated
        return ok({"product_id": product_id, "is_active": False})
    return ok(product)


@api_bp.get("/products/<int:product_id>/batches")
def product_batches(product_id):
    """Batches of one product, nearest expiry first. ?include_empty=true also
    returns batches that have been fully used."""
    _product_or_404(product_id)
    include_empty = request.args.get("include_empty", "false").lower() == "true"
    return ok(inventory.get_product_batches(product_id, include_empty=include_empty))


@api_bp.get("/products/<int:product_id>/forecast")
def product_forecast(product_id):
    """Demand forecast for one product from models/demand.py.
    Optional: ?window=7 (moving-average days, 1-60) and ?alpha=0.3 (0-1)."""
    product = _product_or_404(product_id)
    window = query_int("window", 7, 1, 60)
    try:
        alpha = float(request.args.get("alpha", 0.3))
    except ValueError:
        alpha = -1
    if not 0 < alpha <= 1:
        raise ApiError(400, "Invalid input", {"alpha": "must be a number above 0 and at most 1"})

    forecast = inventory.demand_forecast(product_id, window=window, alpha=alpha)
    forecast.update(product_id=product_id, sku=product["sku"], name=product["name"],
                    window=window, alpha=alpha)
    return ok(forecast)


@api_bp.get("/categories")
def list_categories():
    return ok(product_service.list_categories())
