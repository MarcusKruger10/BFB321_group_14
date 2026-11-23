"""Pharmaceutical Stock Level Tracker - Flask application.

Run:  flask --app app run        (after: pip install -r requirements.txt,
                                  copy .env.example to .env, python init_db.py)
"""
import logging

from flask import Flask, abort, flash, redirect, render_template, request, url_for

import db
from api import api_bp
from api.errors import register_error_handlers
from config import get_config
from models import inventory

app = Flask(__name__)
app.config.from_object(get_config())   
db.init_app(app)                       
app.register_blueprint(api_bp)         
register_error_handlers(app)               

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


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    """Drill-down: the product's model figures and its batches (FEFO order)."""
    product = inventory.get_product(product_id)
    if product is None:
        abort(404)
    return render_template("product_detail.html", product=product,
                           batches=inventory.get_product_batches(product_id))



@app.route("/receive")
def receive():
    return render_template("receive.html")


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
    return render_template("alerts.html")


@app.route("/forecast")
def forecast():
    return render_template("forecast.html")


@app.route("/expiry-risk")
def expiry_risk():
    return render_template("expiry_risk.html")


@app.route("/kpi")
def kpi():
    return render_template("kpi.html")


@app.route("/login")
def login():
    return render_template("login.html")


if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"])