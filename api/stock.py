"""Stock in and out.

POST /api/stock/receive    goods received: creates a batch + 'receipt' movement
POST /api/stock/dispense   sale/dispensing: takes stock First-Expiry-First-Out

Both update the product's reorder alert straight away, so the dashboard,
the alerts list and the KPIs change as soon as stock moves.
"""
import logging

from api import api_bp, current_user_id, ok
from api.errors import ApiError
from api.validators import Checker, get_json_body
from models import inventory
from services import products as product_service

log = logging.getLogger(__name__)


@api_bp.post("/stock/receive")
def receive_stock():
    """Required: product_id, supplier_id, batch_number, expiry_date (YYYY-MM-DD,
    in the future), quantity, unit_cost. Optional: po_id.
    Returns 201 with the new batch_id and the product's new stock position.
    The same batch_number twice for one product returns 409."""
    c = Checker(get_json_body(), allowed=(
        "product_id", "supplier_id", "batch_number", "expiry_date", "quantity", "unit_cost", "po_id"))
    product_id = c.integer("product_id", required=True, minimum=1)
    supplier_id = c.integer("supplier_id", required=True, minimum=1)
    batch_number = c.string("batch_number", required=True, max_length=40)
    expiry_date = c.iso_date("expiry_date", required=True, future_only=True)
    quantity = c.integer("quantity", required=True, minimum=1, maximum=1_000_000)
    unit_cost = c.money("unit_cost", required=True)
    po_id = c.integer("po_id", minimum=1)
    c.done()

    if not product_service.product_exists(product_id):
        raise ApiError(404, f"Product {product_id} not found")

    batch_id = inventory.receive_stock(product_id, supplier_id, batch_number, expiry_date,
                                       quantity, unit_cost, current_user_id(), po_id)
    log.info("Received %s units of product %s as batch %s", quantity, product_id, batch_id)
    return ok({"batch_id": batch_id, "product": inventory.get_product(product_id)}, 201)


@api_bp.post("/stock/dispense")
def dispense_stock():
    """Required: product_id, quantity. Optional: reference (script number).
    Stock is taken from the batch that expires first. Returns 200 with the
    batches used and the product's new stock and reorder status, or 409 if
    there is not enough unexpired stock (nothing is changed in that case)."""
    c = Checker(get_json_body(), allowed=("product_id", "quantity", "reference"))
    product_id = c.integer("product_id", required=True, minimum=1)
    quantity = c.integer("quantity", required=True, minimum=1, maximum=1_000_000)
    reference = c.string("reference", max_length=60)
    c.done()

    if not product_service.product_exists(product_id):
        raise ApiError(404, f"Product {product_id} not found")

    try:
        allocations = inventory.dispense(product_id, quantity, current_user_id(), reference)
    except ValueError as exc:            # not enough stock: transaction was rolled back
        raise ApiError(409, str(exc))

    product = inventory.get_product(product_id)
    log.info("Dispensed %s units of product %s, status now %s",
             quantity, product_id, product["reorder_status"])
    return ok({"dispensed_quantity": quantity, "allocations": allocations, "product": product})
