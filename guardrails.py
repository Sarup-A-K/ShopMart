"""
Guardrails for the shopping assistant.

1. check_input(): rule-based checks that run BEFORE the model is called
   (prompt injection, price negotiation, off-topic or harmful requests, over-long messages).
2. verify_answer(): checks the model's answer AFTER it is written. Every rupee amount, every
   "Aisle N" and every product name in the answer must be backed by the store data for the
   products involved in the conversation.
3. safe_answer(): a templated answer built directly from the database, used when the model's answer
   keeps failing the check.

These are heuristics, not proofs: they catch the failures observed in testing (invented products,
wrong prices, wrong aisles, price haggling) and the evaluation reports how often they fire.
"""
import os
import re

import store_db

MAX_QUESTION_CHARS = 500

REPLIES = {
    "too_long": "That message is too long for me. Please ask a shorter question (under 500 characters).",
    "injection": "I can only help with shopping in this store: products, prices, directions and store policies. What would you like to know?",
    "off_topic": "I can only help with shopping in this store: products, prices, directions and store policies. What would you like to know?",
    "negotiation": (
        "I'm not able to change or negotiate prices. Prices are set by the store, and we already price about 5% below the lowest "
        "online price. If you find a lower price for the same model on Amazon, Flipkart or Croma, show it at the service desk "
        "and the staff will review it."
    ),
}

_I = re.IGNORECASE
INJECTION_PATTERNS = [re.compile(p, _I) for p in [
    r"\b(ignore|disregard|forget|override|bypass)\b.{0,30}\b(previous|prior|above|earlier|all|any|your|the|these)\b.{0,20}\b(instructions?|rules?|prompts?|guidelines?|restrictions?)\b",
    r"\b(reveal|show|print|repeat|tell me|display|leak)\b.{0,20}\b(your|the)\b.{0,15}\b(system|hidden|initial|secret)?\s*(prompt|instructions?|rules)\b",
    r"\bsystem prompt\b",
    r"\byou are now\b",
    r"\bdeveloper mode\b",
    r"\bjailbreak\b",
    r"\bdo anything now\b",
    r"\bpretend (to be|you are|you're)\b",
    r"\b(new|updated) instructions?\b\s*:",
]]
NEGOTIATION_PATTERNS = [re.compile(p, _I) for p in [
    r"\b(give|get|make|let)\b.{0,25}\b(me|it|this)\b.{0,25}(\d{1,3}\s*%|half[- ]price|for free|free of charge|for (just |only )?(₹|rs\.?|inr)?\s*\d+)",
    r"\b(change|set|lower|reduce|drop|cut|slash|decrease|update|edit|modify)\b.{0,20}\bprice\b",
    r"\b(make|give|sell)\b.{0,15}\b(it|this|them|me)\b.{0,10}\bfree\b",
    r"\b(negotiate|bargain|haggle)\b",
    r"\bbest price you can (do|give|offer)\b",
    r"\b(give|apply|offer)\b.{0,20}\b\d{1,3}\s*%\s*(off|discount)\b",
    r"\b\d{1,3}\s*%\s*(off|discount)\b.{0,30}\b(for me|please|right now|today|or else)\b",
    r"\b(sell|offer)\b.{0,15}\b(it|this|them)\b.{0,15}\bfor\b",
    r"\b(manager|owner|staff|employee|cashier)\b.{0,40}\b(said|told|promised|approved|allowed|authori[sz]ed|agreed)\b",
    r"\bpay (only|just)\b",
]]
OFF_TOPIC_PATTERNS = [re.compile(p, _I) for p in [
    r"\bwrite\b.{0,15}\b(poem|essay|story|song|code|script|program|joke|email|letter)\b",
    r"\b(recipe|weather|stock market|bitcoin|crypto|horoscope|homework|election|politic\w*)\b",
    r"\bwho (is|was) the (president|prime minister|ceo)\b",
    r"\bcapital of\b",
    r"\btranslate\b",
    r"\b(how|ways) (do|to|can) (i |we )?(hack|steal|make a bomb|kill|shoplift)\b",
    r"\b(bomb|explosive|illegal drugs?|self[- ]harm)\b",
]]


def check_input(question):
    """Return None if the question may go to the model, else {"category", "reply"} to show instead."""
    text = (question or "").strip()
    if len(text) > MAX_QUESTION_CHARS:
        return {"category": "too_long", "reply": REPLIES["too_long"]}
    for category, patterns in (("injection", INJECTION_PATTERNS), ("negotiation", NEGOTIATION_PATTERNS), ("off_topic", OFF_TOPIC_PATTERNS)):
        if any(p.search(text) for p in patterns):
            return {"category": category, "reply": REPLIES[category]}
    return None


# ---------------------------------------------------------------------------
# Output fact-check
# ---------------------------------------------------------------------------

RUPEE_RE = re.compile(r"(?:₹|\bRs\.?|\bINR)\s?(\d[\d,]*(?:\.\d+)?)", _I)
AISLE_RE = re.compile(r"\bAisles?\s+((?:\d\s*(?:,|and|&|or|to|-)?\s*)+)", _I)
PHRASE_RE = re.compile(r"[A-Z][A-Za-z0-9'’\-]*(?:\s+[A-Z0-9][A-Za-z0-9'’\-]*)+")
NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
WORD_RE = re.compile(r"[a-z0-9]+")

# Capitalised words that are fine in an answer but do not appear in the catalogue or policy text
GENERIC_WORDS = set("""
the a an and or but so yes no ok okay sure please sorry thanks thank hello hi hey welcome great good best better fair nice
deal price prices cheap cheaper cheapest store mall shop aisle aisles section here there this that these those you your
we our us it its they their i my me would could should can will may might also however another other more less
omnitag amazon flipkart croma upi emi mrp inr rs rupees gst sms ac
india indian monday tuesday wednesday thursday friday saturday sunday diwali eid christmas
general buyer budget shopper student tech enthusiast fashion forward
""".split())


def _tokens(text):
    return WORD_RE.findall(str(text).lower().replace("’", "'").replace("'", ""))


def _num(text):
    try:
        return float(str(text).replace(",", ""))
    except ValueError:
        return None


def _policy_text():
    try:
        import rag
        with open(rag.KNOWLEDGE_PATH, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def build_allowed(qr_codes, question="", history_text="", extra_text=""):
    """
    Everything the answer may legitimately mention, for the given products:
    prices (store, MRP, online), their differences (savings), aisles, and the product vocabulary.
    """
    products = [p for p in (store_db.get_product(q) for q in dict.fromkeys(qr_codes)) if p]
    catalogue = store_db.list_products()
    policy = _policy_text()

    # Allowed rupee amounts. Kept deliberately small: a big allowed set would accept almost any number.
    amounts = set()
    shown_prices = []
    for p in products:
        shown_prices.append(float(p["price"]))
        amounts.add(float(p["price"]))
        mrp = p.get("originalPrice")
        if isinstance(mrp, (int, float)):
            amounts.add(float(mrp))
            amounts.add(float(mrp) - float(p["price"]))                 # saving versus M.R.P.
        for c in p.get("competitors", []):
            if isinstance(c.get("price"), (int, float)):
                amounts.add(float(c["price"]))
                amounts.add(abs(float(c["price"]) - float(p["price"])))  # saving versus that online store
    for i, a in enumerate(shown_prices):                                  # price gap between compared products
        for b in shown_prices[i + 1:]:
            amounts.add(abs(a - b))
    stated = [question, history_text]
    if extra_text.strip():                                                # policy numbers only when a policy was cited
        stated.append(policy)
    for text in stated:
        for m in NUMBER_RE.finditer(text):
            n = _num(m.group(0))
            if n is not None:
                amounts.add(n)

    aisles = set()
    for p in products:
        m = re.search(r"\d+", (p.get("location") or {}).get("aisle", ""))
        if m:
            aisles.add(int(m.group(0)))
    for m in AISLE_RE.finditer(question + " " + history_text):
        aisles.update(int(d) for d in re.findall(r"\d", m.group(1)))
    if "Aisles" in policy:                                # store layout is described in the policy, allow 1-6 when it is cited
        if re.search(r"store timings|layout|aisle", extra_text, _I):
            aisles.update(range(1, 7))

    vocab = set(GENERIC_WORDS)
    for p in catalogue:
        vocab.update(_tokens(repr({k: v for k, v in p.items() if k not in ("image", "competitors")})))
    vocab.update(_tokens(policy))
    vocab.update(_tokens(question + " " + history_text))
    return {"products": products, "amounts": amounts, "aisles": aisles, "vocab": vocab}


def _amount_ok(value, allowed_amounts):
    return any(abs(value - a) <= 0.51 for a in allowed_amounts)   # exact, allowing for rounding of .5


def verify_answer(answer, allowed):
    """Return (issues, facts_checked). `issues` is a list of short human-readable problems."""
    issues, checked = [], 0

    for m in RUPEE_RE.finditer(answer):
        value = _num(m.group(1))
        if value is None:
            continue
        checked += 1
        if not _amount_ok(value, allowed["amounts"]):
            issues.append(f"₹{m.group(1)} is not a price from the store data")

    for m in AISLE_RE.finditer(answer):
        for d in re.findall(r"\d", m.group(1)):
            checked += 1
            if int(d) not in allowed["aisles"]:
                issues.append(f"Aisle {d} is not where these products are")

    for m in PHRASE_RE.finditer(answer):
        words = [w for w in _tokens(m.group(0)) if w.isalpha() and len(w) >= 3]
        unknown = [w for w in words if w not in allowed["vocab"]]
        if words:
            checked += 1
        if unknown:
            issues.append(f"'{m.group(0)}' looks like a product that is not in this store")

    return list(dict.fromkeys(issues)), checked


def safe_answer(products):
    """A plain, database-built answer used when the model's own answer keeps failing verification."""
    if not products:
        return ("I couldn't verify that answer against our store data. Please ask the staff at the service desk, "
                "or try rephrasing your question.")
    lines = []
    for p in products[:3]:
        loc = p.get("location") or {}
        mrp = f" (M.R.P. ₹{p['originalPrice']:,.0f})" if p.get("originalPrice") else ""
        lines.append(f"{p['name']}: ₹{p['price']:,.0f}{mrp}, {loc.get('aisle', 'see staff')}"
                     + (f", {loc['section']}" if loc.get("section") else "") + ".")
    return "Here is what I can confirm from our store data. " + " ".join(lines)


# Test hook: lets automated tests append a wrong claim to an answer to prove the fact-checker catches it.
# Disabled unless the server is started with OMNITAG_TEST_HOOKS=1.
TEST_HOOKS = os.environ.get("OMNITAG_TEST_HOOKS") == "1"
