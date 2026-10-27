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
    """Create the schema and add any seed products that are missing."""
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          TEXT NOT NULL,
                qr_code     TEXT,
                persona     TEXT,
                question    TEXT NOT NULL,
                mode        TEXT,
                tools       TEXT,
                guardrail   TEXT,
                verified    INTEGER,
                corrected   INTEGER NOT NULL DEFAULT 0,
                issues      TEXT,
                fallback    INTEGER NOT NULL DEFAULT 0,
                latency_ms  INTEGER
            )
        """)
        conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        seed(conn)


def seed(conn):
    """Insert seed products that are not in the database yet.

    Existing rows are never touched, so prices edited by the admin survive a restart, and new
    products added to seed_products.json appear in an existing database.
    """
    with open(SEED_PATH, encoding="utf-8") as f:
        products = json.load(f)
    have = {r[0] for r in conn.execute("SELECT qr_code FROM products")}
    products = [p for p in products if p["qrCode"] not in have]
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
    if products:
        print(f"Seeded {len(products)} new products into {DB_PATH}")


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
        rows = conn.execute("SELECT * FROM products ORDER BY CAST(SUBSTR(qr_code, INSTR(qr_code, '-') + 1) AS INTEGER), qr_code").fetchall()
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
            f"SELECT qr_code, name, brand, {', '.join(PRICE_FIELDS)}, updated_at FROM products ORDER BY CAST(SUBSTR(qr_code, INSTR(qr_code, '-') + 1) AS INTEGER), qr_code"
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


def log_chat(question, qr_code=None, persona=None, mode=None, tools=None, guardrail=None, verified=None,
             corrected=False, issues=None, fallback=False, latency_ms=None):
    """Record one exchange for the admin insights. Stores the (truncated) question, not who asked it."""
    try:
        with connect() as conn:
            conn.execute(
                "INSERT INTO chat_log (ts, qr_code, persona, question, mode, tools, guardrail, verified, corrected, issues, fallback, latency_ms) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (now_iso(), qr_code, persona, (question or "")[:300], mode, ",".join(tools or []), guardrail,
                 None if verified is None else int(bool(verified)), int(bool(corrected)), "; ".join(issues or [])[:500],
                 int(bool(fallback)), latency_ms),
            )
    except sqlite3.Error as e:
        print(f"chat_log write failed: {e}")


def update_details(qr_code, patch):
    """Merge keys (for example description, aiSummary) into the product's details JSON. Returns the product or None."""
    with connect() as conn:
        row = conn.execute("SELECT details FROM products WHERE qr_code = ?", (qr_code,)).fetchone()
        if not row:
            return None
        details = json.loads(row["details"] or "{}")
        for key, value in patch.items():
            if value is None:
                details.pop(key, None)
            else:
                details[key] = value
        conn.execute("UPDATE products SET details = ?, updated_at = ? WHERE qr_code = ?",
                     (json.dumps(details, ensure_ascii=False), now_iso(), qr_code))
    return get_product(qr_code)


def chat_stats(recent=40):
    """Aggregate numbers and recent questions from chat_log for the admin insights page."""
    with connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM chat_log").fetchone()[0]
        rows = conn.execute("SELECT * FROM chat_log ORDER BY id DESC").fetchall()
        names = {r["qr_code"]: r["name"] for r in conn.execute("SELECT qr_code, name FROM products")}
    blocked, tools, modes, products = {}, {}, {}, {}
    corrected = fallback = latency_total = latency_n = 0
    for r in rows:
        if r["guardrail"]:
            blocked[r["guardrail"]] = blocked.get(r["guardrail"], 0) + 1
        for t in (r["tools"] or "").split(","):
            if t:
                tools[t] = tools.get(t, 0) + 1
        if r["mode"]:
            modes[r["mode"]] = modes.get(r["mode"], 0) + 1
        if r["qr_code"]:
            products[r["qr_code"]] = products.get(r["qr_code"], 0) + 1
        corrected += r["corrected"] or 0
        fallback += r["fallback"] or 0
        if r["latency_ms"] and not r["guardrail"]:
            latency_total += r["latency_ms"]
            latency_n += 1
    top_products = sorted(products.items(), key=lambda kv: -kv[1])[:5]
    return {
        "total_questions": total,
        "blocked": blocked,
        "blocked_total": sum(blocked.values()),
        "corrected": corrected,
        "fallback": fallback,
        "tools": tools,
        "modes": modes,
        "avg_latency_ms": int(latency_total / latency_n) if latency_n else None,
        "top_products": [{"qr_code": q, "name": names.get(q, q), "questions": n} for q, n in top_products],
        "recent_questions": [
            {"ts": r["ts"], "question": r["question"], "product": names.get(r["qr_code"]), "blocked": r["guardrail"]}
            for r in rows[:recent]
        ],
    }


def clear_chat_log():
    with connect() as conn:
        conn.execute("DELETE FROM chat_log")


def get_setting(key, default=""):
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    with connect() as conn:
        conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                     (key, value))
