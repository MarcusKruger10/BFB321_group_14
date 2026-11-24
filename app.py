"""Pharmaceutical Stock Level Tracker - Flask application.

Run:  flask --app app run        (after: pip install -r requirements.txt,
                                  copy .env.example to .env, python init_db.py)
"""
import logging
from datetime import date

from models.impact import calculate_impact

from flask import Flask, abort, flash, redirect, render_template, request, url_for

import db
from api import api_bp
from api.errors import register_error_handlers
from config import get_config
from models import inventory

app = Flask(__name__)
app.config.from_object(get_config())   # settings from .env via config.py
db.init_app(app)                       # closes the MySQL connection after every request
app.register_blueprint(api_bp)         # B2: JSON API under /api
register_error_handlers(app)           # B2: central error handling

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@app.route("/")
def dashboard():
    """Objective 1: one table of every product's stock, reorder status and
    nearest expiry, read live from MySQL; status from models/replenishment.py."""
    status = request.args.get("status") or None          # optional filter, e.g. /?status=Low
    category = request.args.get("category") or None
    try:
        products, total = inventory.list_products(status=status, category=category, limit=100)
    except ValueError:
        abort(400)                                       # unknown status value
    return render_template("dashboard.html", products=products, total=total,
                           kpis=inventory.dashboard_kpis(), status=status)


@app.route("/product/<int:product_id>", methods=["GET", "POST"])
def product_detail(product_id):
    """B3 Flow 3: model-driven reorder recommendation + pharmacist override."""
    product = inventory.get_product(product_id)
    if product is None:
        abort(404)

    if request.method == "POST":
        try:
            if request.form.get("action") == "reset":
                override = None                     # go back to the model's reorder point
            else:
                override = int(request.form["reorder_point"])
                if override < 0:
                    raise ValueError("reorder point cannot be negative")
            product = inventory.update_reorder_settings(product_id, reorder_point_override=override)
            if override is None:
                flash(f"Reorder point reset to the model's value ({product['reorder_point']} units). "
                      f"Status: {product['reorder_status']}.", "success")
            else:
                flash(f"Reorder point set to {override} units. Status: {product['reorder_status']}.", "success")
        except (ValueError, KeyError) as exc:
            flash(f"Could not update reorder point: {exc}", "danger")
        return redirect(url_for("product_detail", product_id=product_id))

    return render_template("product_detail.html", product=product,
                           batches=inventory.get_product_batches(product_id),
                           forecast=inventory.demand_forecast(product_id),
                           supplier=inventory.get_preferred_supplier(product_id))


@app.route("/receive", methods=["GET", "POST"])
def receive():
    """B3 Flow 1: receive a new batch, save to MySQL, show the new stock level."""
    if request.method == "POST":
        try:
            product_id = int(request.form["product_id"])
            supplier_id = int(request.form["supplier_id"])
            batch_number = request.form["batch_number"].strip()
            quantity = int(request.form["quantity"])
            expiry_date = date.fromisoformat(request.form["expiry_date"])
            product = inventory.get_product(product_id)
            if product is None:
                raise ValueError("unknown product")
            if not batch_number:
                raise ValueError("batch number is required")
            if quantity <= 0:
                raise ValueError("quantity must be greater than 0")
            if expiry_date <= date.today():
                raise ValueError("expiry date must be in the future")
            # Unit cost from the form, or the product's normal cost if left blank
            unit_cost = float(request.form.get("unit_cost") or product["unit_cost"])

            inventory.receive_stock(product_id, supplier_id, batch_number, expiry_date,
                                    quantity, unit_cost, user_id=1)
            product = inventory.get_product(product_id)   # reload to get the new stock level
            flash(f"Received {quantity} units of {product['name']} (batch {batch_number}, "
                  f"expires {expiry_date}). Stock now {product['stock_on_hand']} - "
                  f"status: {product['reorder_status']}.", "success")
        except ValueError as exc:
            flash(f"Could not receive stock: {exc}", "danger")
        except Exception as exc:
            # e.g. the same batch number already exists for this product
            if "Duplicate" in str(exc):
                flash("Could not receive stock: that batch number already exists for this product.", "danger")
            else:
                app.logger.exception("Receive failed")
                flash("Could not receive stock: unexpected error, please try again.", "danger")
        return redirect(url_for("receive"))

    products, _ = inventory.list_products(limit=100)
    return render_template("receive.html", products=products,
                           suppliers=inventory.list_suppliers(),
                           recent=inventory.recent_receipts())


@app.route("/dispense", methods=["GET", "POST"])
def dispense():
    """B3 Flow 2: dispense stock FEFO, save to MySQL, show the result."""
    if request.method == "POST":
        try:
            product_id = int(request.form["product_id"])
            quantity = int(request.form["quantity"])
            reference = request.form.get("reference") or None
            # user_id=1 until login works (first user in seed.sql)
            used = inventory.dispense(product_id, quantity, user_id=1, reference=reference)
            batches = ", ".join(f"{a['allocated_quantity']} from batch {a['batch_id']}" for a in used)
            product = inventory.get_product(product_id)
            flash(f"Dispensed {quantity} units of {product['name']} ({batches}). "
                  f"Stock now {product['stock_on_hand']} - status: {product['reorder_status']}.",
                  "success")
            if product["reorder_status"] != "Sufficient":
                flash(f"Alert: {product['name']} is {product['reorder_status']}. "
                      f"Recommended order: {product['recommended_order_qty']} units.", "warning")
        except (ValueError, KeyError) as exc:
            flash(f"Could not dispense: {exc}", "danger")
        return redirect(url_for("dispense"))   # reload the page so the table shows the change

    products, _ = inventory.list_products(limit=100)
    return render_template("dispense.html", products=products,
                           recent=inventory.recent_dispenses())

@app.route("/alerts")
def alerts():
    """Open reorder / low-stock alerts, created automatically after dispense and receive."""
    return render_template("alerts.html", alerts=inventory.list_alerts("open"))


@app.route("/forecast")
def forecast():
    """Demand forecast for one product (models/demand.py), chosen from a dropdown."""
    products, _ = inventory.list_products(limit=100)
    selected_id = request.args.get("product_id", type=int) or (products[0]["product_id"] if products else None)
    product = inventory.get_product(selected_id) if selected_id else None
    result = inventory.demand_forecast(selected_id) if product else None
    return render_template("forecast.html", products=products, product=product, forecast=result)


@app.route("/expiry-risk")
def expiry_risk():
    """Batches classified as expired / expiring soon / fresh (models/expiry.py)."""
    return render_template("expiry_risk.html", batches=inventory.expiry_batches(),
                           kpis=inventory.dashboard_kpis())



@app.route("/kpi")
def kpi():
    """B3.3: KPIs calculated from live MySQL data and the supply chain models."""
    kpis = inventory.dashboard_kpis()
    impact_results = calculate_impact()
    products, _ = inventory.list_products(limit=100)
    to_restock = [p for p in products if p["reorder_status"] != "Sufficient"]
    return render_template(
    "kpi.html",
    kpis=kpis,
    to_restock=to_restock,
    impact_results=impact_results
)

@app.route("/login")
def login():
    return render_template("login.html")


if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"])