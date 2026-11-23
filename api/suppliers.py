"""Suppliers.

GET    /api/suppliers          list (page, size, search, active)
GET    /api/suppliers/<id>     one supplier with the products it supplies
POST   /api/suppliers          create a supplier
PATCH  /api/suppliers/<id>     update a supplier
"""
import logging
import re

from flask import request, url_for

from api import api_bp, ok, paged
from api.errors import ApiError
from api.validators import Checker, get_json_body, pagination, query_choice
from services import suppliers as supplier_service

log = logging.getLogger(__name__)

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _check_email(c):
    email = c.string("email", max_length=120)
    if email and not EMAIL_PATTERN.match(email):
        c.errors["email"] = "must be a valid e-mail address"
    return email


@api_bp.get("/suppliers")
def list_suppliers():
    """Query parameters (optional): page, size, search (name or contact),
    active (true | false)."""
    page, size, offset = pagination()
    active = query_choice("active", ("true", "false"))
    rows, total = supplier_service.list_suppliers(
        search=request.args.get("search") or None,
        active=None if active is None else active == "true",
        limit=size, offset=offset,
    )
    return paged(rows, total, page, size)


@api_bp.get("/suppliers/<int:supplier_id>")
def get_supplier(supplier_id):
    supplier = supplier_service.get_supplier(supplier_id)
    if supplier is None:
        raise ApiError(404, f"Supplier {supplier_id} not found")
    return ok(supplier)


@api_bp.post("/suppliers")
def create_supplier():
    """Required: name. Optional: contact_name, phone, email.
    Returns 201, or 409 if a supplier with the same name exists."""
    c = Checker(get_json_body(), allowed=("name", "contact_name", "phone", "email"))
    name = c.string("name", required=True, max_length=120)
    contact_name = c.string("contact_name", max_length=100)
    phone = c.string("phone", max_length=30)
    email = _check_email(c)
    c.done()

    supplier_id = supplier_service.create_supplier(name, contact_name, phone, email)
    log.info("Created supplier %s (%s)", supplier_id, name)
    location = url_for("api.get_supplier", supplier_id=supplier_id)
    return ok(supplier_service.get_supplier(supplier_id), 201, {"Location": location})


@api_bp.patch("/suppliers/<int:supplier_id>")
def update_supplier(supplier_id):
    """Send only the fields to change: name, contact_name, phone, email, is_active."""
    c = Checker(get_json_body(), allowed=supplier_service.EDITABLE)
    changes = {}
    if c.has("name"):
        changes["name"] = c.string("name", required=True, max_length=120)
    if c.has("contact_name"):
        changes["contact_name"] = c.string("contact_name", max_length=100)
    if c.has("phone"):
        changes["phone"] = c.string("phone", max_length=30)
    if c.has("email"):
        changes["email"] = _check_email(c)
    if c.has("is_active"):
        changes["is_active"] = c.boolean("is_active", required=True)
    if not c.data:
        c.errors["body"] = "send at least one field to change"
    c.done()

    if not supplier_service.update_supplier(supplier_id, changes):
        raise ApiError(404, f"Supplier {supplier_id} not found")
    log.info("Updated supplier %s: %s", supplier_id, sorted(changes))
    return ok(supplier_service.get_supplier(supplier_id))
