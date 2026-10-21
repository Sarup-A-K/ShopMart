"""
SQLite product store for OmniTag AR.

Prices (store price, MRP and the competitor prices entered by the admin) live in
their own columns so they can be edited and imported from Excel. The rest of the
product record (image, specs, reviews, location...) is kept as JSON in `details`.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "omnitag.db"))
SEED_PATH = os.path.join(BASE_DIR, "seed_products.json")

COMPETITORS = ["Amazon", "Flipkart", "Croma"]
COMPETITOR_COLUMNS = {"Amazon": "amazon_price", "Flipkart": "flipkart_price", "Croma": "croma_price"}
PRICE_FIELDS = ["price", "mrp", "amazon_price", "flipkart_price", "croma_price"]
FIELD_LABELS = {"price": "Store price", "mrp": "MRP", "amazon_price": "Amazon price",
                "flipkart_price": "Flipkart price", "croma_price": "Croma price"}

# Dynamic pricing: undercut the cheapest online price by this fraction,
# but never sell above the admin's store price.
PRICE_MATCH_DISCOUNT = 0.05


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the schema and seed it from seed_products.json on first run."""
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                qr_code         TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                brand           TEXT,
                category        TEXT,
                price           REAL NOT NULL,
                mrp             REAL,
                amazon_price    REAL,
                flipkart_price  REAL,
                croma_price     REAL,
                details         TEXT NOT NULL DEFAULT '{}',
                updated_at      TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                id          TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                source_id   TEXT NOT NULL,
                title       TEXT NOT NULL,
                text        TEXT NOT NULL,
                text_hash   TEXT NOT NULL,
                vector      BLOB NOT NULL
            )
        """)
        if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
            seed(conn)


def seed(conn):
    with open(SEED_PATH, encoding="utf-8") as f:
        products = json.load(f)
    ts = now_iso()
    for p in products:
        p = dict(p)
        comp = p.pop("competitorPrices", {}) or {}
        row = {
            "qr_code": p.pop("qrCode"),
            "name": p.pop("name"),
            "brand": p.pop("brand", None),
            "category": p.pop("category", None),
            "price": p.pop("price"),
            "mrp": p.pop("originalPrice", None),
            "amazon_price": comp.get("Amazon"),
            "flipkart_price": comp.get("Flipkart"),
            "croma_price": comp.get("Croma"),
            "details": json.dumps(p, ensure_ascii=False),
            "updated_at": ts,
        }
        conn.execute(
            f"INSERT INTO products ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})",
            list(row.values()),
        )
    print(f"Seeded {len(products)} products into {DB_PATH}")


def row_to_product(row):
    """Shape a DB row like the frontend product object, with price matching applied."""
    product = json.loads(row["details"] or "{}")
    competitors = [
        {"name": name, "price": row[col] if row[col] is not None else "NA"}
        for name, col in COMPETITOR_COLUMNS.items()
    ]
    priced = [c for c in competitors if c["price"] != "NA"]
    cheapest = min(priced, key=lambda c: c["price"]) if priced else None

    shelf = row["price"]
    effective = shelf
    if cheapest:
        target = int(cheapest["price"] * (1 - PRICE_MATCH_DISCOUNT))
        if 0 < target < shelf:
            effective = target

    product.update({
        "qrCode": row["qr_code"],
        "name": row["name"],
        "brand": row["brand"],
        "category": row["category"],
        "shelfPrice": shelf,
        "price": effective,
        "priceMatched": effective < shelf,
        "originalPrice": row["mrp"],
        "competitors": competitors,
        "compName": cheapest["name"] if cheapest else None,
        "compPrice": cheapest["price"] if cheapest else "NA",
        "pricesUpdatedAt": row["updated_at"],
    })
    return product


def list_products():
    with connect() as conn:
        rows = conn.execute("SELECT * FROM products ORDER BY qr_code").fetchall()
    return [row_to_product(r) for r in rows]


def get_product(qr_code):
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM products WHERE lower(qr_code) = lower(?)", (qr_code.strip(),)
        ).fetchone()
    return row_to_product(row) if row else None


def list_price_rows():
    """Flat rows for the admin table and Excel export."""
    with connect() as conn:
        rows = conn.execute(
            f"SELECT qr_code, name, brand, {', '.join(PRICE_FIELDS)}, updated_at FROM products ORDER BY qr_code"
        ).fetchall()
    return [dict(r) for r in rows]


def validate_prices(values):
    """Return (clean_values, errors). Store price is required; others may be blank (None)."""
    clean, errors = {}, []
    for field in PRICE_FIELDS:
        if field not in values:
            continue
        v = values[field]
        if v is None or (isinstance(v, str) and v.strip() == ""):
            if field == "price":
                errors.append("Store price is required")
            else:
                clean[field] = None
            continue
        try:
            num = float(str(v).replace(",", "").replace("₹", "").strip())
        except ValueError:
            errors.append(f"{FIELD_LABELS[field]}: '{v}' is not a number")
            continue
        if num <= 0:
            errors.append(f"{FIELD_LABELS[field]} must be greater than 0")
            continue
        clean[field] = round(num, 2)
    return clean, errors


def update_prices(qr_code, values):
    """Update the given price fields for one product. Returns the updated product or None."""
    if not values:
        return get_product(qr_code)
    sets = ", ".join(f"{k} = ?" for k in values) + ", updated_at = ?"
    with connect() as conn:
        cur = conn.execute(
            f"UPDATE products SET {sets} WHERE qr_code = ?",
            [*values.values(), now_iso(), qr_code],
        )
        if cur.rowcount == 0:
            return None
    return get_product(qr_code)


def bulk_update_prices(updates):
    """Apply {qr_code: values} in a single transaction (all or nothing)."""
    ts = now_iso()
    with connect() as conn:
        for qr_code, values in updates.items():
            if not values:
                continue
            sets = ", ".join(f"{k} = ?" for k in values) + ", updated_at = ?"
            conn.execute(f"UPDATE products SET {sets} WHERE qr_code = ?", [*values.values(), ts, qr_code])


def existing_qr_codes():
    with connect() as conn:
        return {r[0] for r in conn.execute("SELECT qr_code FROM products")}
