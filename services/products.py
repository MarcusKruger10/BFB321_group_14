"""Product changes and lookups that models/inventory.py doesn't cover."""
from db import query, query_one, transaction

# Product details a client may change with PATCH /api/products/<id>.
# (The reorder threshold and service level go through
#  inventory.update_reorder_settings, so the stock alert is refreshed.)
EDITABLE = ("name", "strength", "dosage_form", "pack_size", "category_id",
            "unit_cost", "unit_price", "ordering_cost", "shelf_life_days", "is_active")

DOSAGE_FORMS = ("tablet", "capsule", "syrup", "suspension", "inhaler", "cream", "injection", "other")


def product_exists(product_id):
    return query_one("SELECT 1 FROM products WHERE product_id = %s", (product_id,)) is not None


def get_reorder_override(product_id):
    row = query_one("SELECT reorder_point_override FROM products WHERE product_id = %s", (product_id,))
    return row["reorder_point_override"] if row else None


def update_product_details(product_id, changes):
    """Update only the given product columns (names come from EDITABLE)."""
    columns = [c for c in EDITABLE if c in changes]
    if not columns:
        return
    set_clause = ", ".join(f"{c} = %s" for c in columns)
    with transaction() as cur:
        cur.execute(f"UPDATE products SET {set_clause} WHERE product_id = %s",
                    [changes[c] for c in columns] + [product_id])


def list_categories():
    return query(
        """SELECT c.category_id, c.name, c.description, COUNT(p.product_id) AS product_count
           FROM categories c
           LEFT JOIN products p ON p.category_id = c.category_id AND p.is_active = TRUE
           GROUP BY c.category_id, c.name, c.description
           ORDER BY c.name"""
    )
