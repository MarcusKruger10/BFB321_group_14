"""Integration tests for the JSON API (rubric B2).

They run against the separate TEST database, which is rebuilt from
database/schema.sql + seed.sql before the tests start:

    python init_db.py --test      (once, or let the fixture below do it)
    pytest tests/test_api.py -v

If MySQL is not reachable the tests are skipped instead of failing.
"""
import os

import pytest

os.environ["FLASK_ENV"] = "testing"          # must be set before app is imported

import pymysql                                # noqa: E402
from dotenv import load_dotenv               # noqa: E402

import init_db                                # noqa: E402

load_dotenv()


def _rebuild_test_database():
    db_name = os.getenv("TEST_DB_NAME", "pharmacy_tracker_test")
    conn = pymysql.connect(host=os.getenv("DB_HOST", "localhost"), port=int(os.getenv("DB_PORT", "3306")),
                           user=os.getenv("DB_USER", "root"), password=os.getenv("DB_PASSWORD", ""),
                           charset="utf8mb4")
    with conn.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4")
        cur.execute(f"USE `{db_name}`")
    init_db.run_file(conn, init_db.SCHEMA)
    init_db.run_file(conn, init_db.SEED)
    conn.close()


@pytest.fixture(scope="module")
def client():
    try:
        _rebuild_test_database()
    except pymysql.err.OperationalError as exc:
        pytest.skip(f"MySQL not available: {exc}")
    from app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


NEW_PRODUCT = {"sku": "TST-001", "name": "Test Tablet", "category_id": 2,
               "unit_cost": 1.00, "unit_price": 2.50, "pack_size": 10}


def test_list_products_is_paged(client):
    r = client.get("/api/products?page=1&size=5")
    assert r.status_code == 200
    body = r.get_json()
    assert len(body["data"]) <= 5
    assert {"page", "size", "total", "pages"} <= body.keys()


def test_filter_by_status_only_returns_that_status(client):
    r = client.get("/api/products?status=Reorder%20Needed")
    assert r.status_code == 200
    assert all(p["reorder_status"] == "Reorder Needed" for p in r.get_json()["data"])


@pytest.mark.parametrize("url", ["/api/products?status=Bad", "/api/products?page=abc",
                                 "/api/products?size=1000", "/api/alerts?type=fire"])
def test_bad_query_parameters_return_400(client, url):
    assert client.get(url).status_code == 400


def test_unknown_product_returns_404_json(client):
    r = client.get("/api/products/99999")
    assert r.status_code == 404
    assert r.get_json()["error"]["code"] == 404


def test_create_product_then_read_it(client):
    r = client.post("/api/products", json=NEW_PRODUCT)
    assert r.status_code == 201
    new_id = r.get_json()["data"]["product_id"]
    assert r.headers["Location"].endswith(f"/api/products/{new_id}")
    assert client.get(f"/api/products/{new_id}").get_json()["data"]["sku"] == "TST-001"


def test_duplicate_sku_returns_409(client):
    r = client.post("/api/products", json=NEW_PRODUCT)       # same SKU as the test above
    assert r.status_code == 409


def test_invalid_product_lists_every_problem(client):
    r = client.post("/api/products", json={"sku": "", "unit_cost": -1})
    assert r.status_code == 400
    details = r.get_json()["error"]["details"]
    assert {"sku", "name", "category_id", "unit_cost", "unit_price"} <= details.keys()


def test_update_threshold_changes_status(client):
    r = client.patch("/api/products/1", json={"reorder_point_override": 100000})
    assert r.status_code == 200
    assert r.get_json()["data"]["reorder_status"] == "Reorder Needed"
    r = client.patch("/api/products/1", json={"reorder_point_override": None})
    assert r.get_json()["data"]["override_active"] is False


def test_receive_then_dispense_changes_stock(client):
    before = client.get("/api/products/2").get_json()["data"]["stock_on_hand"]
    r = client.post("/api/stock/receive", json={
        "product_id": 2, "supplier_id": 1, "batch_number": "TEST-LOT-1",
        "expiry_date": "2030-01-31", "quantity": 100, "unit_cost": 0.32})
    assert r.status_code == 201
    r = client.post("/api/stock/dispense", json={"product_id": 2, "quantity": 30})
    assert r.status_code == 200
    assert r.get_json()["data"]["product"]["stock_on_hand"] == before + 100 - 30


def test_dispensing_more_than_stock_returns_409_and_changes_nothing(client):
    before = client.get("/api/products/2").get_json()["data"]["stock_on_hand"]
    r = client.post("/api/stock/dispense", json={"product_id": 2, "quantity": 10_000_000 // 11})
    assert r.status_code == 409
    assert client.get("/api/products/2").get_json()["data"]["stock_on_hand"] == before


def test_supplier_create_update_and_duplicate(client):
    r = client.post("/api/suppliers", json={"name": "Test Supplier", "email": "a@b.co"})
    assert r.status_code == 201
    sid = r.get_json()["data"]["supplier_id"]
    r = client.patch(f"/api/suppliers/{sid}", json={"phone": "012 000 0000"})
    assert r.get_json()["data"]["phone"] == "012 000 0000"
    assert client.post("/api/suppliers", json={"name": "Test Supplier"}).status_code == 409


def test_alert_can_be_resolved(client):
    alert = client.get("/api/alerts?status=open&size=1").get_json()["data"][0]
    r = client.patch(f"/api/alerts/{alert['alert_id']}", json={"status": "resolved"})
    assert r.status_code == 200
    assert r.get_json()["data"]["resolved_at"] is not None


def test_kpis(client):
    data = client.get("/api/kpis").get_json()["data"]
    assert data["total_products"] >= 12


def test_body_must_be_json(client):
    r = client.post("/api/stock/dispense", data="hello")
    assert r.status_code == 400
