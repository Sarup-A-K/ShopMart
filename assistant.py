"""
Shopping-assistant logic: product grounding, persona insights (schema-constrained JSON,
cached) and multi-turn chat with token streaming.
"""
import json
import time

import llm

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
    priced = [c for c in (product.get("competitors") or []) if isinstance(c.get("price"), (int, float))]
    if priced:
        lines.append("Online prices: " + ", ".join(f"{c['name']} ₹{c['price']:.0f}" for c in priced))
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


def chat_system_prompt(product, persona):
    prompt = (
        f"You are OmniTag, a helpful in-store shopping assistant in an Indian mall, talking to a '{persona}'. "
        "Answer in 2-4 short sentences, tailored to that shopper. "
        "Use only the product facts below for prices, specs and location; if something is not in the facts, say you don't know. "
        "Use Indian Rupees (₹), never '$'. Never change or negotiate prices."
    )
    context = build_product_context(product)
    if context:
        prompt += f"\n\nProduct facts:\n{context}"
    return prompt


def build_chat_messages(product, persona, history, question):
    return (
        [{"role": "system", "content": chat_system_prompt(product, persona)}]
        + clean_history(history)
        + [{"role": "user", "content": question.strip()}]
    )


def answer(product, persona, history, question):
    """Non-streaming answer (used by /api/ask)."""
    return llm.chat(build_chat_messages(product, persona, history, question))["content"].strip()


def stream_answer(product, persona, history, question):
    """Yield answer text pieces as they are generated."""
    yield from llm.stream_chat(build_chat_messages(product, persona, history, question))
