"""Pharmaceutical Stock Level Tracker - Flask application.

Run:  flask --app app run        (after: pip install -r requirements.txt,
                                  copy .env.example to .env, python init_db.py)
"""
import logging

from flask import Flask, abort, render_template, request

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


@app.route("/dispense")
def dispense():
    return render_template("dispense.html")


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