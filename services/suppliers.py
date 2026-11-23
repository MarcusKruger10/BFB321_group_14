"""Suppliers: list, read, create and update (table `suppliers`)."""
from db import query, query_one, transaction

# Columns a client may set. Column names in SQL come ONLY from this list,
# never from the request, so building the SET clause below is safe.
EDITABLE = ("name", "contact_name", "phone", "email", "is_active")


def _with_booleans(row, *fields):
    """MySQL returns BOOLEAN columns as 1/0; send them to the client as true/false."""
    for f in fields:
        if row.get(f) is not None:
            row[f] = bool(row[f])
    return row


def list_suppliers(search=None, active=None, limit=20, offset=0):
    """Return (rows, total) for one page of suppliers, optionally filtered."""
    where, params = [], []
    if search:
        where.append("(name LIKE %s OR contact_name LIKE %s)")
        params += [f"%{search}%", f"%{search}%"]
    if active is not None:
        where.append("is_active = %s")
        params.append(active)
    clause = ("WHERE " + " AND ".join(where)) if where else ""

    total = query_one(f"SELECT COUNT(*) AS n FROM suppliers {clause}", params)["n"]
    rows = query(
        f"""SELECT supplier_id, name, contact_name, phone, email, is_active, created_at, updated_at
            FROM suppliers {clause}
            ORDER BY name
            LIMIT %s OFFSET %s""",
        params + [limit, offset],
    )
    return [_with_booleans(r, "is_active") for r in rows], total


def get_supplier(supplier_id):
    """One supplier with the products it supplies, or None if it doesn't exist."""
    supplier = query_one(
        """SELECT supplier_id, name, contact_name, phone, email, is_active, created_at, updated_at
           FROM suppliers WHERE supplier_id = %s""",
        (supplier_id,),
    )
    if supplier:
        supplier["products"] = query(
            """SELECT p.product_id, p.sku, p.name, ps.supplier_sku, ps.lead_time_days,
                      ps.supplier_cost, ps.is_preferred
               FROM product_suppliers ps
               JOIN products p ON p.product_id = ps.product_id
               WHERE ps.supplier_id = %s
               ORDER BY p.name""",
            (supplier_id,),
        )
        supplier["products"] = [_with_booleans(p, "is_preferred") for p in supplier["products"]]
        _with_booleans(supplier, "is_active")
    return supplier


def create_supplier(name, contact_name=None, phone=None, email=None):
    """Insert a supplier and return its new id. A duplicate name raises
    pymysql.err.IntegrityError, which the API turns into 409 Conflict."""
    with transaction() as cur:
        cur.execute(
            "INSERT INTO suppliers (name, contact_name, phone, email) VALUES (%s, %s, %s, %s)",
            (name, contact_name, phone, email),
        )
        return cur.lastrowid


def update_supplier(supplier_id, changes):
    """Update only the given columns. Returns False if the supplier doesn't exist."""
    if query_one("SELECT 1 FROM suppliers WHERE supplier_id = %s", (supplier_id,)) is None:
        return False
    columns = [c for c in EDITABLE if c in changes]
    if columns:
        set_clause = ", ".join(f"{c} = %s" for c in columns)
        with transaction() as cur:
            cur.execute(f"UPDATE suppliers SET {set_clause} WHERE supplier_id = %s",
                        [changes[c] for c in columns] + [supplier_id])
    return True
