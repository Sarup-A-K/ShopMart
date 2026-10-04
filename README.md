# OmniTag AR: Smart Price Tags & GenAI Retail Assistant

OmniTag is a next-generation brick-and-mortar retail solution. It turns static paper price tags into QR-linked product pages with online price comparison, in-store directions and a locally hosted **Generative AI** shopping assistant.

Instead of fighting "showrooming" (where customers check online prices while in-store), OmniTag embraces it. Store staff manage prices, including Amazon India, Flipkart and Croma prices, from an admin page or an Excel upload. When a customer scans a product's QR code with their phone, its product page opens and shows the online prices, and the store undercuts the lowest one by ~5%. A locally hosted Llama 3.2 model gives persona-tailored product insights and answers questions grounded in the store's product data, and a store map guides the shopper to the right aisle.

---

## 🌟 Key Features

* **Scan-to-product pages**: Each shelf price tag has a QR code that links to `/p/<code>`. Any phone camera opens the product page directly: price vs MRP, online price comparison, directions to the aisle, AI advice, specs and reviews. The site has a light, mobile-first e-commerce design with a searchable catalogue and an in-page QR scanner (jsQR).
* **Admin price manager** (`/admin`): Password-protected page to print QR price tags and to edit the store price, MRP and the Amazon / Flipkart / Croma prices in a table, with a live preview of the price shoppers will see. For bulk updates, **Download Excel**, edit the price columns, and **Upload Excel**. Rows are matched by QR code. If any row is invalid, nothing is saved and every bad row is listed.
* **SQLite product database** (`omnitag.db`): Created and seeded from `seed_products.json` on first start. Every scan reads the latest record, so price changes show up on the next scan without reloading.
* **Dynamic price matching**: Shoppers see a price ~5% below the cheapest online price entered by the admin, but never more than the admin's store price.
* **Indoor wayfinding**: Store map with an "I'm near" checkpoint selector (Entrance or Aisle 1–6). It draws the route along the front corridor and up the aisle walkway, and gives step-by-step directions with distances.
* **Persona-based GenAI assistant** (Llama 3.2 via Ollama):
  * Personas: General Buyer, Budget Shopper, Student, Tech Enthusiast, Fashion Forward.
  * Structured JSON insights (`Verdict`, `Deal Score`, `Compatibility`, `Specs Translation`), tailored to the persona.
  * A chat that is **grounded** in the product record (price, online prices, specs, reviews, aisle), so answers quote real prices and locations instead of made-up ones.

---

## 📁 Project Structure

* `web/` - The website, served by the backend:
  * `index.html`, `js/catalog.js` - Store catalogue with search, categories and a "Scan tag" button.
  * `product.html`, `js/product.js` - Product page at `/p/<qr_code>`, the page a price-tag QR code opens: price, online price comparison, directions, AI assistant, specs and reviews.
  * `admin.html`, `js/admin.js` - Store admin: price table, Excel import/export, printable QR price tags.
  * `js/wayfinding.js` - Route and step-by-step directions to the product's aisle.
  * `js/common.js`, `js/qrEngine.js` - Shared helpers and the in-page QR camera scanner.
  * `css/store.css` - Light, mobile-first e-commerce theme.
* `server.py` - FastAPI backend: website, product API, admin API, Excel import/export and LLM routing.
* `store_db.py` - SQLite storage, validation and the price-matching rule.
* `seed_products.json` - Initial products (details, location, prices) used to create the database on first run.
* `start.sh` - Starts everything and sets the network address used in QR codes.
* `eval.py` - Evaluation harness (JSON validity, grounding accuracy, latency, currency compliance).
* `docker-compose.yml`, `Dockerfile` - The backend and the Ollama LLM engine.

---

## 🚀 How to Run the Project

You need [Docker](https://www.docker.com/) installed. The site runs on your laptop and is opened by phones on the same network, for example your phone's hotspot with the laptop connected to it.

### 1. Start
```bash
./start.sh
```
This detects the laptop's network address (e.g. `http://192.168.43.10:8000`), starts Ollama (pulling **Llama 3.2** on first run) and the FastAPI server on port `8000`, and prints the addresses to use. On first run it creates `.env` with a random admin password (`ADMIN_PASSWORD`).

### 2. Use it
* **Shoppers:** open the printed address on a phone, or scan a QR price tag with the phone's camera app. The tag opens that product's page directly, even if the site isn't open yet.
* **Admin:** `<address>/admin`. Edit prices, use Excel, and under **QR price tags** print the shelf tags.
* **This laptop:** `http://localhost:8000`.

**If the laptop's address changes** (e.g. after reconnecting to the hotspot), run `./start.sh` again and reprint the tags, because the address is inside the QR codes.

**In-page camera scanner:** browsers only allow camera access on `https://` pages or on `localhost`. On phones opening the plain `http://` address, the **Scan tag** button explains this and offers code entry. Use the phone's camera app to scan tags instead. The in-page scanner works on the laptop.

To reset all prices to the seed data, stop the stack, delete `omnitag.db`, and start it again.

### 3. Stop
```bash
docker compose down
```

---

## 🛠️ API Endpoints Reference

The FastAPI backend (`http://localhost:8000`) exposes the following core endpoints:
* `GET /api/products`, `GET /api/products/{qr_code}`: Product records with store, shown (price-matched) and competitor prices.
* `POST /api/scan_tag`: Asks Llama 3.2 for structured, persona-tailored product insights grounded in the product record.
* `POST /api/ask`: Grounded, persona-aware chat about a specific product.
* `GET /api/health`: Backend and model status.
* `GET /api/config`: The public address used for QR codes.

Admin endpoints (need `Authorization: Bearer <token>` from `POST /api/admin/login`):
* `GET /api/admin/prices`, `PUT /api/admin/prices/{qr_code}`: List and edit prices.
* `GET /api/admin/prices.xlsx`, `POST /api/admin/prices/import`: Excel export and import.

If the LLM is unreachable, `/api/scan_tag` and `/api/ask` return `{"success": false, "error": ...}`.

---

## 📊 Evaluation

With the stack running:
```bash
docker exec -w /workspace local_web_app python3 eval.py            # all personas
docker exec -w /workspace local_web_app python3 eval.py --personas 1
```
This runs every product × persona × question against the API. It prints a summary and writes `eval_results.csv`, which has an empty `human_rating` column for manual 1–5 scoring. Metrics reported:
* Insight JSON validity rate
* Price and aisle grounding accuracy (does the answer quote the correct ₹ price / aisle?)
* Currency compliance (no `$` in outputs)
* Latency (mean / p95) for insights and chat

---

## ⚠️ Known Limitations
* Competitor prices are entered by store staff (table or Excel), not fetched automatically. Retailers block scraping, so a manual or feed-based update is more reliable.
* Admin login is a single shared password with in-memory sessions (8 hours); restarting the backend logs the admin out. After 5 wrong passwords, logins from that device are blocked for 5 minutes.
* The site is served over plain HTTP on the local network, so anyone on the same network can open it. Use your own hotspot rather than shared Wi-Fi when demoing.
* Indoor position comes from the shopper's chosen checkpoint, not continuous tracking (browsers have no indoor positioning).
* `docker-compose.yml` reserves an NVIDIA GPU for Ollama; remove the `deploy:` block to run on CPU (slower).
