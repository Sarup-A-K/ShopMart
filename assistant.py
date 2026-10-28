"""
Shopping-assistant logic: product grounding, persona insights (schema-constrained JSON,
cached) and multi-turn chat with token streaming.
"""
import json
import time

import llm

# Mirrors the "Payment options and EMI" section of knowledge/store_policies.md. LLMs (especially small ones)
# are unreliable at comparing numbers, so conditions like this are computed in code and given to the model as facts.
EMI_MIN_PRICE = 10000

MAX_HISTORY_TURNS = 6          # user+assistant messages kept from the conversation
MAX_MESSAGE_CHARS = 800
INSIGHT_CACHE_SIZE = 200

INSIGHT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string"},
        "dealScore": {"type": "string"},
        "compatibility": {"type": "string"},
        "specsTranslation": {"type": "string"},
        "aiNote": {"type": "string"},
    },
    "required": ["verdict", "dealScore", "compatibility", "specsTranslation", "aiNote"],
}

_insight_cache = {}


# ---------------------------------------------------------------------------
# Grounding: turn the database record into LLM context
# ---------------------------------------------------------------------------

def build_product_context(product):
    if not product:
        return ""
    lines = [
        f"Product: {product.get('name')}",
        f"Brand: {product.get('brand')}",
        f"Category: {product.get('category')}",
    ]
    if product.get("price") is not None:
        lines.append(f"Our store price: ₹{product['price']:.0f}")
    if product.get("originalPrice"):
        lines.append(f"MRP: ₹{product['originalPrice']:.0f}")
    if product.get("price") is not None:
        if product["price"] >= EMI_MIN_PRICE:
            lines.append("EMI: eligible (no-cost EMI for 3 or 6 months with selected credit cards)")
        else:
            lines.append(f"EMI: not available for this product (its price is below the ₹{EMI_MIN_PRICE:,} minimum)")
    priced = [c for c in (product.get("competitors") or []) if isinstance(c.get("price"), (int, float))]
    if priced:
        lines.append("Online prices: " + ", ".join(f"{c['name']} ₹{c['price']:.0f}" for c in priced))
        if product.get("price") is not None:
            # Comparison worked out in code: small models get "higher/lower" and "lowest" wrong, even with the numbers in front of them
            ours, parts = float(product["price"]), []
            for c in sorted(priced, key=lambda c: c["price"]):
                gap = c["price"] - ours
                parts.append(f"{c['name']} ₹{c['price']:.0f} (our price is ₹{abs(gap):.0f} {'lower' if gap > 0 else 'higher'})" if gap else f"{c['name']} ₹{c['price']:.0f} (same as ours)")
            lowest = min(priced, key=lambda c: c["price"])
            lines.append("Price comparison (computed): " + "; ".join(parts) + f". The lowest online price is {lowest['name']} at ₹{lowest['price']:.0f}.")
    if product.get("description"):
        lines.append(f"Description: {product['description']}")
    specs = product.get("specifications") or {}
    if specs.get("keySpecs"):
        lines.append("Key specs: " + ", ".join(f"{k}: {v}" for k, v in specs["keySpecs"].items()))
    if specs.get("features"):
        lines.append("Features: " + ", ".join(specs["features"]))
    if specs.get("warranty"):
        lines.append(f"Warranty: {specs['warranty']}")
    if product.get("reviews"):
        lines.append("Customer reviews: " + " | ".join(product["reviews"]))
    loc = product.get("location") or {}
    if loc.get("aisle"):
        lines.append(f"In-store location: {loc['aisle']}, {loc.get('section', '')} section")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Persona insight (the card at the top of the AI section)
# ---------------------------------------------------------------------------

def _fallback_insight(product):
    return {
        "verdict": f"{product.get('name')} is well rated by most buyers.",
        "dealScore": "Fair Price",
        "compatibility": "Suits most everyday needs.",
        "specsTranslation": "Check the product details for the full specifications.",
        "aiNote": "The AI answer could not be read, so a default summary is shown.",
    }


def get_insight(product, persona):
    """Returns (analysis dict, llm_ok, cached). Raises llm.LLMError if the model is unreachable."""
    key = (product["qrCode"], persona, product.get("price"), product.get("pricesUpdatedAt"))
    if key in _insight_cache:
        return _insight_cache[key], True, True

    comp_price, comp_name = product.get("compPrice"), product.get("compName")
    price_line = ""
    if isinstance(comp_price, (int, float)):
        price_line = f" The lowest online price is ₹{comp_price:.0f} on {comp_name}; our store price is ₹{product['price']:.0f}."

    system = (
        f"You are an in-store shopping assistant in an Indian mall. The shopper is a '{persona}'. "
        f"Analyze the product.{price_line} Use only the product facts provided. "
        "Use Indian Rupees (₹) and never the '$' symbol. Reply with a JSON object only."
    )
    prompt = (
        f"Product facts:\n{build_product_context(product)}\n\n"
        f"Write a JSON object with these keys, tailored for a {persona}:\n"
        "- verdict: a 2-sentence summary of the customer reviews\n"
        "- dealScore: a short rating such as 'Great Deal', 'Fair Price' or 'Wait for Sale', based on our price vs the online prices\n"
        "- compatibility: how it fits their needs, outfits or devices\n"
        "- specsTranslation: one plain-English sentence about its key feature\n"
        "- aiNote: one short friendly line speaking to the shopper"
    )
    raw = llm.generate(system, prompt, format=INSIGHT_SCHEMA)
    try:
        analysis = json.loads(raw)
        ok = all(isinstance(analysis.get(k), str) and analysis[k].strip() for k in INSIGHT_SCHEMA["required"])
    except (json.JSONDecodeError, AttributeError):
        analysis, ok = {}, False

    if not ok:
        analysis = {**_fallback_insight(product), **{k: v for k, v in (analysis or {}).items() if isinstance(v, str) and v.strip()}}
        return analysis, False, False

    if len(_insight_cache) >= INSIGHT_CACHE_SIZE:
        _insight_cache.pop(next(iter(_insight_cache)))
    _insight_cache[key] = analysis
    return analysis, True, False


# ---------------------------------------------------------------------------
# Chat with memory
# ---------------------------------------------------------------------------

def clean_history(history):
    """Keep only the last few well-formed turns so the prompt stays small and safe."""
    turns = []
    for m in history or []:
        role, content = m.get("role"), m.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            turns.append({"role": role, "content": content.strip()[:MAX_MESSAGE_CHARS]})
    return turns[-MAX_HISTORY_TURNS:]


def chat_system_prompt(product, persona, policies=()):
    """`policies` are store-information chunks retrieved by rag.policy_context for this question."""
    prompt = (
        f"You are ShopMart, a helpful in-store shopping assistant in an Indian mall, talking to a '{persona}'. "
        "Answer in 2-4 short sentences, tailored to that shopper. "
        "Use only the product facts and store information below for prices, specs, policies and location; "
        "if something is not covered there, say you don't know. "
        "When store information has conditions (minimum purchase amount, number of days, product types), "
        "check them against this product's price and type before saying yes. "
        "Use Indian Rupees (₹), never '$'. Never change or negotiate prices."
    )
    context = build_product_context(product)
    if context:
        prompt += f"\n\nProduct facts:\n{context}"
    if policies:
        prompt += "\n\nStore information:\n" + "\n".join(f"[{p['title']}] {p['text']}" for p in policies)
    return prompt


def sources_for(policies):
    return [{"type": "policy", "title": p["title"]} for p in policies]


def build_chat_messages(product, persona, history, question, policies=()):
    return (
        [{"role": "system", "content": chat_system_prompt(product, persona, policies)}]
        + clean_history(history)
        + [{"role": "user", "content": question.strip()}]
    )


def answer(product, persona, history, question, policies=(), model=None):
    """Non-streaming answer."""
    return llm.chat(build_chat_messages(product, persona, history, question, policies), model=model)["content"].strip()


def stream_answer(product, persona, history, question, policies=(), model=None):
    """Yield answer text pieces as they are generated."""
    yield from llm.stream_chat(build_chat_messages(product, persona, history, question, policies), model=model)
