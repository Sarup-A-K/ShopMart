"""
OmniTag AR evaluation harness.

Runs every product x persona x question against the running backend and records:
  - JSON validity of /api/scan_tag insights (llm_ok)
  - response latency (mean / p95)
  - currency compliance (no '$' in any output)
  - grounding: does the chat answer quote the correct ₹ store price / aisle?
Products and prices are read from the backend database (/api/products), exactly as the app sees them.
Writes eval_results.csv (with an empty human_rating column for 1-5 manual scoring)
and prints a summary table.

Usage:  python eval.py [--url http://localhost:8000] [--personas 2]
"""
import argparse
import csv
import json
import re
import statistics
import time

import requests

PERSONAS = ["General Buyer", "Budget Shopper", "Student", "Tech Enthusiast", "Fashion Forward"]

# (question, what the answer should contain: "price", "aisle" or None for open-ended)
QUESTIONS = [
    ("What is the price of this in your store?", "price"),
    ("Which aisle can I find this in?", "aisle"),
    ("Is this a good deal compared to buying online?", "price"),
    ("Who is this product best suited for?", None),
]


def contains_price(text, price):
    """True if the text mentions the exact price as a whole number (15999, 15,999, 15999.00)."""
    numbers = re.findall(r"\d[\d,]*(?:\.\d+)?", text)
    target = round(float(price))
    for n in numbers:
        try:
            if round(float(n.replace(",", ""))) == target:
                return True
        except ValueError:
            continue
    return False


def contains_aisle(text, aisle):
    num = re.sub(r"\D", "", aisle)
    return re.search(rf"\baisle\s*{num}\b", text, re.IGNORECASE) is not None


def timed_post(url, payload, timeout=120):
    t0 = time.perf_counter()
    res = requests.post(url, json=payload, timeout=timeout)
    return res.json(), time.perf_counter() - t0


def p95(values):
    if not values:
        return 0.0
    values = sorted(values)
    return values[min(len(values) - 1, int(round(0.95 * (len(values) - 1))))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--personas", type=int, default=len(PERSONAS), help="how many personas to test")
    ap.add_argument("--out", default="eval_results.csv")
    args = ap.parse_args()

    products = requests.get(f"{args.url}/api/products", timeout=30).json()["products"]
    personas = PERSONAS[: args.personas]

    rows = []
    scan_latencies, ask_latencies = [], []

    for product in products:
        # Price shown to shoppers (after the ~5% price match), as computed by the backend
        store_price = product["price"]

        for persona in personas:
            # 2. Structured insight
            scan, lat = timed_post(f"{args.url}/api/scan_tag", {
                "product_name": product["name"],
                "qr_code": product["qrCode"],
                "category": product["category"],
                "user_context": persona,
            })
            scan_latencies.append(lat)
            analysis_text = json.dumps(scan.get("data", {}).get("analysis", {}), ensure_ascii=False)
            rows.append({
                "product": product["qrCode"], "persona": persona, "endpoint": "scan_tag",
                "question": "", "latency_s": round(lat, 2),
                "success": scan.get("success", False), "json_valid": scan.get("llm_ok", False),
                "no_dollar": "$" not in analysis_text, "grounded": "",
                "output": analysis_text, "human_rating": "",
            })

            # 3. Grounded chat
            for question, expects in QUESTIONS:
                ask, lat = timed_post(f"{args.url}/api/ask", {
                    "product_name": product["name"], "qr_code": product["qrCode"],
                    "question": question, "persona": persona,
                })
                ask_latencies.append(lat)
                answer = ask.get("answer") or ask.get("error", "")
                if expects == "price":
                    grounded = contains_price(answer, store_price)
                elif expects == "aisle":
                    grounded = contains_aisle(answer, product["location"]["aisle"])
                else:
                    grounded = ""
                rows.append({
                    "product": product["qrCode"], "persona": persona, "endpoint": "ask",
                    "question": question, "latency_s": round(lat, 2),
                    "success": ask.get("success", False), "json_valid": "",
                    "no_dollar": "$" not in answer, "grounded": grounded,
                    "output": answer, "human_rating": "",
                })
            print(f"  {product['qrCode']} / {persona}: done")

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    def rate(items):
        items = [x for x in items if x != ""]
        return f"{100 * sum(bool(x) for x in items) / len(items):.1f}% ({sum(bool(x) for x in items)}/{len(items)})" if items else "n/a"

    scan_rows = [r for r in rows if r["endpoint"] == "scan_tag"]
    ask_rows = [r for r in rows if r["endpoint"] == "ask"]
    price_rows = [r for r in ask_rows if r["question"] in {q for q, e in QUESTIONS if e == "price"}]
    aisle_rows = [r for r in ask_rows if r["question"] in {q for q, e in QUESTIONS if e == "aisle"}]

    print("\n=== OmniTag AR evaluation summary ===")
    print(f"Products x personas           : {len(products)} x {len(personas)}")
    print(f"Insight JSON validity          : {rate([r['json_valid'] for r in scan_rows])}")
    print(f"Chat success rate              : {rate([r['success'] for r in ask_rows])}")
    print(f"Price grounding accuracy       : {rate([r['grounded'] for r in price_rows])}")
    print(f"Aisle grounding accuracy       : {rate([r['grounded'] for r in aisle_rows])}")
    print(f"No '$' in outputs (₹ only)     : {rate([r['no_dollar'] for r in rows])}")
    if scan_latencies:
        print(f"Insight latency mean / p95 (s) : {statistics.mean(scan_latencies):.2f} / {p95(scan_latencies):.2f}")
    if ask_latencies:
        print(f"Chat latency mean / p95 (s)    : {statistics.mean(ask_latencies):.2f} / {p95(ask_latencies):.2f}")
    print(f"\nFull results written to {args.out} (fill the human_rating column 1-5 for human eval).")


if __name__ == "__main__":
    main()
