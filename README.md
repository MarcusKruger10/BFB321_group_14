# Pharmaceutical Stock Level Tracker

**BFB321 – Supply Chain Web Application Project**

## Project Description

The Pharmaceutical Stock Level Tracker is a web-based inventory management and replenishment decision-support system designed for community pharmacies in South Africa.

The application aims to improve pharmaceutical inventory visibility and support more effective stock management by integrating stock levels, expiry dates, replenishment requirements and demand information into a centralised dashboard.

The project addresses common inventory management challenges, including stockouts, overstocking, medicine expiry and inefficient replenishment decisions.

## Project Objectives

The application is designed around three main objectives:

1. **Real-Time Inventory Visibility:** Provide a centralised dashboard displaying pharmaceutical stock levels, expiry dates and reorder status.
2. **Safety Stock Alerts and Reorder Prompts:** Identify products that reach or fall below predefined safety-stock thresholds and notify pharmacy staff when replenishment should be considered.
3. **Demand Forecasting:** Analyse historical sales and consumption data to identify demand patterns and support informed replenishment decisions.

## Group Members

| Name and Surname | Student Number |
|---|---|
| Cara Dalporto | u22655809 |
| Rebecca Tejessy | u22570111 |
| Melissa du Plessis | u04467729 |
| Marcus Kruger | u23561310 |

## Installation and Setup Instructions

### Requirements
- Visual Studio Code
- Git
- Live Server extension for Visual Studio Code
- A modern web browser (Google Chrome or Microsoft Edge)

### Running the Application

1. Open the GitHub repository.
2. Click **Code → HTTPS** and copy the repository URL.
3. Open Visual Studio Code.
4. Select **Git: Clone** from the Command Palette (`Ctrl + Shift + P`).
5. Paste the repository URL and select a location to clone the repository.
6. Open the cloned project folder in Visual Studio Code.
7. Ensure that the **Live Server** extension is installed and enabled.
8. Navigate to the templates folder.
9. Right-click `dashboard.html` and select **Open with Live Server**.
10. The front-end dashboard will open in your default web browser.

### Note
This submission focuses on the front-end design of the Pharmaceutical Stock Level Tracker. Flask and backend functionality will be implemented in the Exam submission. No Flask installation or backend server is required to view the current front-end design. The login page is included as part of the user interface design; however, login authentication is not yet functional, as it requires Flask backend integration planned for the second submission. For this submission, please launch the application directly from dashboard.html rather than login.html.


## Database design

![Entity Relationship Diagram](database/erd.png)

The MySQL schema is in `database/schema.sql` and demo data in `database/seed.sql`.
Build both with `python init_db.py` (settings come from `.env`; copy `.env.example`).

## REST API (Step 4)

The Flask app exposes a JSON REST API under `/api`. The pages call the same
functions, so the API and the screens always show the same data.

### Application structure

| Folder / file | What it holds |
|---|---|
| `app.py` | Creates the Flask app, registers the API blueprint and the error handlers, serves the HTML pages |
| `config.py` | Settings per environment: `DevelopmentConfig`, `TestingConfig`, `ProductionConfig` (chosen by `FLASK_ENV` in `.env`) |
| `db.py` | MySQL connection per request, parameterised queries, transactions with rollback |
| `api/` | **Blueprint `api`** (`/api/...`): `products.py`, `suppliers.py`, `stock.py`, `alerts.py`, plus `validators.py` (input checks) and `errors.py` (central error handling) |
| `services/` | Database functions used by the API (suppliers, product updates, alerts) |
| `models/` | Supply chain model (replenishment, demand, expiry) and `inventory.py` (database access) |
| `tests/test_api.py` | Integration tests for every endpoint (`pytest tests/test_api.py -v`) |

### Endpoints

| Method | Path | Purpose | Success |
|---|---|---|---|
| GET | `/api/products` | List products with stock, nearest expiry and reorder status. Query: `page`, `size`, `category`, `status`, `search` | 200 |
| GET | `/api/products/<id>` | One product with the model's safety stock, reorder point and recommended order | 200 |
| POST | `/api/products` | Create a product | 201 |
| PATCH | `/api/products/<id>` | Update product details and/or the reorder threshold | 200 |
| GET | `/api/products/<id>/batches` | Batches of a product, nearest expiry first. Query: `include_empty` | 200 |
| GET | `/api/products/<id>/forecast` | Demand forecast (moving average, exponential smoothing, backtest). Query: `window`, `alpha` | 200 |
| GET | `/api/categories` | All categories with product counts | 200 |
| GET | `/api/suppliers` | List suppliers. Query: `page`, `size`, `search`, `active` | 200 |
| GET | `/api/suppliers/<id>` | One supplier with the products it supplies | 200 |
| POST | `/api/suppliers` | Create a supplier | 201 |
| PATCH | `/api/suppliers/<id>` | Update a supplier | 200 |
| POST | `/api/stock/receive` | Receive stock: creates a batch and a receipt movement | 201 |
| POST | `/api/stock/dispense` | Dispense stock First-Expiry-First-Out; updates the reorder alert | 200 |
| GET | `/api/alerts` | List alerts. Query: `page`, `size`, `status`, `type` | 200 |
| PATCH | `/api/alerts/<id>` | Acknowledge or resolve an alert | 200 |
| GET | `/api/kpis` | Live KPIs for the dashboard | 200 |

### Response format

Every response is JSON in one of three shapes:

```json
{"data": {"product_id": 1, "sku": "AMX-500", "stock_on_hand": 240, "reorder_status": "Sufficient"}}

{"data": [ ... ], "page": 1, "size": 20, "total": 12, "pages": 1}

{"error": {"code": 400, "message": "Invalid input",
           "details": {"quantity": "must be at least 1"}}}
```

Status codes: `200` OK, `201` created, `400` invalid input, `404` not found,
`405` wrong method, `409` conflict (duplicate SKU, supplier name or batch number,
or not enough stock to dispense), `500` unexpected server error (logged, no
stack trace shown).

### Request examples

**Create a product** – `POST /api/products`
```json
{"sku": "LOR-010", "name": "Loratadine", "strength": "10mg", "category_id": 4,
 "unit_cost": 0.75, "unit_price": 1.80, "pack_size": 10}
```
Required: `sku`, `name`, `category_id`, `unit_cost`, `unit_price`.
Optional: `strength`, `dosage_form`, `pack_size`, `service_level`, `reorder_point_override`, `shelf_life_days`.

**Change the reorder threshold** – `PATCH /api/products/1`
```json
{"reorder_point_override": 150}
```
Send `null` to go back to the reorder point calculated by the model.

**Receive stock** – `POST /api/stock/receive`
```json
{"product_id": 2, "supplier_id": 1, "batch_number": "LOT-7781",
 "expiry_date": "2028-06-30", "quantity": 400, "unit_cost": 0.32}
```

**Dispense stock** – `POST /api/stock/dispense`
```json
{"product_id": 2, "quantity": 30, "reference": "RX-1001"}
```
Response includes the batches used and the product's new stock and reorder status.

**Resolve an alert** – `PATCH /api/alerts/3`
```json
{"status": "resolved"}
```

### Trying the API

```bash
curl "http://127.0.0.1:5000/api/products?status=Reorder%20Needed&size=5"
curl -X POST http://127.0.0.1:5000/api/stock/dispense \
     -H "Content-Type: application/json" \
     -d '{"product_id": 2, "quantity": 30}'
```

### Validation, errors and logging

* Input is checked in `api/validators.py`; every problem is returned at once with a 400.
* All errors are handled centrally in `api/errors.py`: JSON for `/api/...`, a friendly page for screens.
* Failed database writes are rolled back in `db.transaction()`.
* Every API call and every failure is logged with Python's `logging` module.
