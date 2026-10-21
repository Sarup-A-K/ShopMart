"""
GenAI features for the store admin:
  - summarise_reviews(): pros/cons summary of a product's customer reviews
  - draft_description(): a short product description written from the specs
  - shopper_report(): themes and suggested actions from what shoppers have been asking
Drafts are previews: nothing is saved until the admin approves it.
"""
import json
import re

import llm
import store_db

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "pros": {"type": "array", "items": {"type": "string"}},
        "cons": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "pros", "cons"],
}
DESCRIPTION_SCHEMA = {"type": "object", "properties": {"description": {"type": "string"}}, "required": ["description"]}
REPORT_SCHEMA = {
    "type": "object",
    "properties": {"themes": {"type": "array", "items": {"type": "string"}}, "suggestions": {"type": "array", "items": {"type": "string"}}},
    "required": ["themes", "suggestions"],
}

NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _numbers(text):
    return {n.replace(",", "") for n in NUMBER_RE.findall(text)}


def _source_text(product):
    """Everything about the product that a draft may legitimately be based on."""
    specs = product.get("specifications") or {}
    return " ".join([
        product.get("name", ""), product.get("brand", "") or "", product.get("category", "") or "",
        product.get("description", "") or "",
        " ".join(f"{k} {v}" for k, v in (specs.get("keySpecs") or {}).items()),
        " ".join(specs.get("features") or []), specs.get("warranty", "") or "",
        " ".join(product.get("reviews") or []),
    ])


def _unsupported_numbers(draft_text, product):
    """Numbers in a draft that appear nowhere in the product data (likely invented specs or prices)."""
    return sorted(_numbers(draft_text) - _numbers(_source_text(product)))


# Everyday words that carry no product claim; anything else not in the product data is listed for the admin to check
COMMON_WORDS = set("""
about above after also another around because before being between both built came come could does each even every find from gives
good great have help here into just keep know like look made make many more most much need never next only other over perfect
really right same should since some such take than that their them then there these they thing this those through time under
until upon used uses using very want well were what when where which while will with within without would your yours
ready featuring features feature designed design shoppers shopper store customers customer product products everyday daily
choice option options ideal comfort comfortable style stylish look looks lovely praised noting commended customers said say
""".split())


def _unfamiliar_words(draft_text, product):
    source = _source_text(product).lower()
    seen, out = set(), []
    for word in re.findall(r"[A-Za-z]{6,}", draft_text):
        low = word.lower()
        if low in seen or low in COMMON_WORDS:
            continue
        seen.add(low)
        if low[:5] not in source:                  # prefix match so "feature" matches "features"
            out.append(word)
    return out[:6]


def _warnings(draft_text, product, what):
    warnings = [f"Number {n} is not in the {what}" for n in _unsupported_numbers(draft_text, product)]
    words = _unfamiliar_words(draft_text, product)
    if words:
        warnings.append(f"These words are not in the {what}; make sure they are accurate: {', '.join(words)}")
    return warnings


def _json(raw):
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def summarise_reviews(product):
    reviews = product.get("reviews") or []
    if not reviews:
        return {"error": "This product has no reviews to summarise."}
    system = (
        "You summarise customer reviews for a store's product page. Use only what the reviews say. "
        "Do not add features, numbers or claims that are not in the reviews. Reply with a JSON object only."
    )
    prompt = (
        f"Product: {product['name']}\n\nCustomer reviews:\n" + "\n".join(f"- {r}" for r in reviews) +
        "\n\nWrite: summary (2 sentences), pros (up to 3 short phrases), cons (up to 3 short phrases; an empty list if the reviews mention none)."
    )
    data = _json(llm.generate(system, prompt, format=REVIEW_SCHEMA, temperature=0.2))
    if not data or not isinstance(data.get("summary"), str):
        return {"error": "The AI answer could not be read. Please try again."}
    data["pros"] = [str(x) for x in (data.get("pros") or [])][:3]
    data["cons"] = [str(x) for x in (data.get("cons") or [])][:3]
    text = data["summary"] + " " + " ".join(data["pros"] + data["cons"])
    return {"draft": data, "warnings": _warnings(text, product, "reviews")}


def draft_description(product):
    specs = product.get("specifications") or {}
    system = (
        "You write short product descriptions for a store's website. Use only the facts given. "
        "Do not invent specifications, numbers, materials, awards or prices. Reply with a JSON object only."
    )
    facts = [f"Name: {product['name']}", f"Brand: {product.get('brand')}", f"Category: {product.get('category')}"]
    if specs.get("keySpecs"):
        facts.append("Specs: " + ", ".join(f"{k}: {v}" for k, v in specs["keySpecs"].items()))
    if specs.get("features"):
        facts.append("Features: " + ", ".join(specs["features"]))
    if specs.get("warranty"):
        facts.append(f"Warranty: {specs['warranty']}")
    prompt = "\n".join(facts) + "\n\nWrite a description of 25 to 40 words for shoppers, in plain friendly language."
    data = _json(llm.generate(system, prompt, format=DESCRIPTION_SCHEMA, temperature=0.4))
    if not data or not isinstance(data.get("description"), str) or not data["description"].strip():
        return {"error": "The AI answer could not be read. Please try again."}
    description = data["description"].strip()
    warnings = _warnings(description, product, "product data")
    words = len(description.split())
    if words > 60:
        warnings.append(f"The draft is long ({words} words)")
    return {"draft": {"description": description}, "warnings": warnings}


def shopper_report(stats=None):
    stats = stats or store_db.chat_stats()
    questions = [q["question"] for q in stats["recent_questions"] if not q["blocked"]]
    if len(questions) < 3:
        return {"error": "Not enough shopper questions yet (need at least 3)."}
    system = (
        "You help a store manager understand what shoppers ask an in-store AI assistant. "
        "Use only the questions listed. Do not invent numbers or products. Reply with a JSON object only."
    )
    prompt = (
        "Recent shopper questions:\n" + "\n".join(f"- {q}" for q in questions[:40]) +
        "\n\nWrite: themes (3 short bullet points describing what shoppers are asking about) and "
        "suggestions (3 concrete actions the store could take, for example signage, FAQ, stock or pricing changes)."
    )
    data = _json(llm.generate(system, prompt, format=REPORT_SCHEMA, temperature=0.3))
    if not data:
        return {"error": "The AI answer could not be read. Please try again."}
    return {"themes": [str(x) for x in (data.get("themes") or [])][:5],
            "suggestions": [str(x) for x in (data.get("suggestions") or [])][:5],
            "based_on": len(questions)}
