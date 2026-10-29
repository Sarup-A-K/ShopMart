"""
Shopping agent: Llama 3.2 decides which tools to call (search, product lookup, comparison, directions,
store information), the code runs them against the live database, and the model writes the answer.

run_agent() is a generator of events:
  {"event": "tool",  "name", "args", "label"}      a tool was called
  {"event": "token", "text"}                        a piece of the final answer
  {"event": "done",  "tools", "products", "sources", "fallback", "rounds"}
"""
import json
import re

import assistant
import llm
import rag
import store_db
import wayfinding

MAX_ROUNDS = 4

TOOLS = [
    {"type": "function", "function": {
        "name": "search_products",
        "description": "Find products in this store by meaning, for example 'running shoes', 'earbuds for gym', 'gift for mother'. "
                       "Use for questions like 'which phone is best', 'what shoes do you have' or 'anything under 1000'.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "What the shopper is looking for"},
            "max_price": {"type": "number", "description": "Maximum price in rupees, only if the shopper gave a budget"},
            "category": {"type": "string", "description": "Electronics, Fashion or Footwear, only if clearly implied"},
        }, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "get_product",
        "description": "Get full details (price, MRP, online prices, specs, features, warranty, reviews, aisle) of one product.",
        "parameters": {"type": "object", "properties": {
            "qr_code": {"type": "string", "description": "The product's name as the shopper said it, or a qr_code from an earlier tool result. Never guess a code."},
        }, "required": ["qr_code"]},
    }},
    {"type": "function", "function": {
        "name": "compare_products",
        "description": "Compare two or more products side by side on price, specs and location. Use when asked which is cheaper or better.",
        "parameters": {"type": "object", "properties": {
            "qr_codes": {"type": "array", "items": {"type": "string"}, "description": "Product names as the shopper said them, or qr_codes from an earlier tool result. Never guess a code."},
        }, "required": ["qr_codes"]},
    }},
    {"type": "function", "function": {
        "name": "get_directions",
        "description": "Get walking directions inside the store to a product, from the entrance or from an aisle.",
        "parameters": {"type": "object", "properties": {
            "qr_code": {"type": "string", "description": "The product's name as the shopper said it, or a qr_code from an earlier tool result. Never guess a code."},
            "from_checkpoint": {"type": "string", "description": "'entrance' (default) or 'aisle-1' ... 'aisle-6'"},
        }, "required": ["qr_code"]},
    }},
    {"type": "function", "function": {
        "name": "search_store_info",
        "description": "Look up store policies and services: returns, exchanges, warranty, EMI, payment, offers, delivery, timings, parking.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "The policy question"},
        }, "required": ["query"]},
    }},
]
TOOL_NAMES = {t["function"]["name"] for t in TOOLS}


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def _num(x):
    return int(round(x)) if isinstance(x, (int, float)) else x


def _inr(x):
    """A ready-written price ('₹45,599'): a small model copies a formatted string more faithfully than a bare number."""
    return f"₹{int(round(x)):,}" if isinstance(x, (int, float)) else x


def _brief(p):
    loc = p.get("location") or {}
    online = [c for c in (p.get("competitors") or []) if isinstance(c.get("price"), (int, float))]
    return {
        "qr_code": p["qrCode"], "name": p["name"], "brand": p.get("brand"), "category": p.get("category"),
        "our_price": _inr(p["price"]), "mrp": _inr(p.get("originalPrice")),
        "online_prices": {c["name"]: _inr(c["price"]) for c in online},
        "aisle": loc.get("aisle"), "section": loc.get("section"),
        "quality_score": (p.get("specifications") or {}).get("qualityScore"),
        "key_specs": (p.get("specifications") or {}).get("keySpecs"),
    }


def _detail(p):
    specs = p.get("specifications") or {}
    out = _brief(p)
    out.update({
        "description": p.get("description"),
        "key_specs": specs.get("keySpecs"), "features": specs.get("features"), "warranty": specs.get("warranty"),
        "reviews": (p.get("reviews") or [])[:2],
        "emi": "eligible" if p["price"] >= assistant.EMI_MIN_PRICE else f"not available (below ₹{assistant.EMI_MIN_PRICE:,})",
    })
    return out


def _valid_codes_hint():
    return "Valid products: " + "; ".join(f"{p['qrCode']} = {p['name'][:40]}" for p in store_db.list_products())


def _as_list(value):
    """Models sometimes send a list as a JSON string ('["a","b"]') or a comma-separated string."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("["):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
        return [part.strip() for part in re.split(r"[,;]| and ", text) if part.strip()]
    return []


def resolve_product(ref):
    """A qr_code ('item-2'), or a product name the model typed instead."""
    ref = str(ref or "").strip()
    if not ref:
        return None
    p = store_db.get_product(ref)
    if p:
        return p
    words = set(rag.tokens(ref))
    best, best_hits = None, 0
    for cand in store_db.list_products():
        hay = f"{cand['name']} {cand.get('brand')}".lower()
        hits = sum(1 for w in words if w in hay)
        if hits > best_hits:
            best, best_hits = cand, hits
    return best if best_hits else None


def tool_search_products(query="", max_price=None, category=None):
    found = rag.search_products(str(query), limit=4, max_price=max_price, category=category)
    results = [{**_brief(r["product"]), "relevance": r["score"]} for r in found["results"]]
    out = {"results": results, "exact_match": found["confident"]}
    if re.search(r"\b(best|top|recommend\w*|suggest\w*|good|better)\b", str(query).lower()) and len(results) > 1:
        out["note"] = ("The shopper wants a recommendation. Mention every product in the results with its price and aisle, "
                       "say which one you would pick and why (specs, quality score, value), and do not simply pick the cheapest.")
    if not results:
        out["note"] = "No matching products in this store."
    elif not found["confident"] and "note" not in out:
        out["note"] = "Nothing matches exactly; these are the closest items."
    return out, f"Searched products for “{query}”", [r["qr_code"] for r in results], []


def tool_get_product(qr_code=""):
    p = resolve_product(qr_code)
    if not p:
        return {"error": f"No product found for '{qr_code}'. {_valid_codes_hint()}"}, "Looked up a product", [], []
    return _detail(p), f"Looked up {p['name'][:40]}", [p["qrCode"]], []


def tool_compare_products(qr_codes=None):
    products, seen = [], set()
    for ref in _as_list(qr_codes)[:4]:
        p = resolve_product(ref)
        if p and p["qrCode"] not in seen:
            seen.add(p["qrCode"])
            products.append(p)
    if len(products) < 2:
        return {"error": f"Need at least two valid products. {_valid_codes_hint()}"}, "Compared products", [p["qrCode"] for p in products], []
    rows = [{**_brief(p), "key_specs": (p.get("specifications") or {}).get("keySpecs")} for p in products]
    ordered = sorted(products, key=lambda p: p["price"])
    cheapest, priciest = ordered[0], ordered[-1]
    where = lambda p: (p.get("location") or {}).get("aisle", "an aisle")
    # The comparison itself is computed here; the model only has to put it into words.
    summary = (
        f"All {len(products)} products are available in this store. "
        f"The cheapest is {cheapest['name']} at ₹{_num(cheapest['price'])} ({where(cheapest)}), "
        f"which is ₹{_num(priciest['price'] - cheapest['price'])} less than {priciest['name']} at ₹{_num(priciest['price'])} ({where(priciest)})."
    )
    return ({"summary": summary, "products": rows,
             "cheapest_in_store": {"qr_code": cheapest["qrCode"], "name": cheapest["name"], "price_rupees": _num(cheapest["price"]), "aisle": where(cheapest)}},
            f"Compared {len(products)} products", [p["qrCode"] for p in products], [])


def tool_get_directions(qr_code="", from_checkpoint="entrance"):
    p = resolve_product(qr_code)
    if not p:
        return {"error": f"No product found for '{qr_code}'. {_valid_codes_hint()}"}, "Got directions", [], []
    route = wayfinding.directions(p, from_checkpoint)
    if not route:
        return {"error": "This product has no location."}, "Got directions", [p["qrCode"]], []
    return {"product": p["name"], **route}, f"Got directions to {route['aisle']}", [p["qrCode"]], []


def tool_search_store_info(query=""):
    try:
        hits = [h for h in rag.search_chunks(str(query), k=2, source_types={"policy"}) if h["score"] >= 0.5]
    except Exception as e:
        return {"error": f"Store information is unavailable ({e})."}, "Checked store info", [], []
    if not hits:
        return {"results": [], "note": "No matching store information."}, f"Checked store info for “{query}”", [], []
    out = {"results": [{"title": h["title"], "text": h["text"]} for h in hits],
           "note": f"EMI is only for purchases of ₹{assistant.EMI_MIN_PRICE:,} or more."}
    return out, f"Checked store info for “{query}”", [], [{"type": "policy", "title": h["title"]} for h in hits]


TOOL_FUNCS = {
    "search_products": tool_search_products,
    "get_product": tool_get_product,
    "compare_products": tool_compare_products,
    "get_directions": tool_get_directions,
    "search_store_info": tool_search_store_info,
}


def execute_tool(name, args):
    """Run one tool call safely. Always returns (result_dict, label, qr_codes, sources) so the model can recover from errors."""
    if name not in TOOL_FUNCS:
        return {"error": f"Unknown tool '{name}'. Available tools: {', '.join(sorted(TOOL_NAMES))}."}, f"Unknown tool {name}", [], []
    if not isinstance(args, dict):
        args = {}
    fn = TOOL_FUNCS[name]
    allowed = set(fn.__code__.co_varnames[:fn.__code__.co_argcount])
    clean = {k: v for k, v in args.items() if k in allowed}
    try:
        return fn(**clean)
    except Exception as e:  # a tool bug must not crash the chat
        return {"error": f"Tool {name} failed: {e}"}, f"{name} failed", [], []


# ---------------------------------------------------------------------------
# Tool-call parsing (structured calls, or JSON the model wrote as plain text)
# ---------------------------------------------------------------------------

def _normalise_calls(raw_calls):
    calls = []
    for c in raw_calls or []:
        fn = c.get("function", c)
        name, args = fn.get("name"), fn.get("arguments", fn.get("parameters", {}))
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        if name:
            calls.append({"name": name, "args": args if isinstance(args, dict) else {}})
    return calls


def _calls_from_text(text):
    """Some outputs contain the call as text: {"name": "get_product", "parameters": {...}}."""
    t = text.strip()
    t = re.sub(r"^<\|python_tag\|>", "", t).strip()
    try:
        data = json.loads(t)
    except json.JSONDecodeError:
        return []
    items = data if isinstance(data, list) else [data]
    return _normalise_calls([i for i in items if isinstance(i, dict) and ("name" in i or "function" in i)])


# ---------------------------------------------------------------------------
# Router: does this question need tools?
# ---------------------------------------------------------------------------

# Questions that need other products, search or directions. Store-policy words are NOT here on purpose: the evaluation
# showed the single-call RAG path answers pure policy questions more reliably than the agent (which sometimes skips
# the policy tool and invents a number), and faster.
AGENT_HINTS = re.compile(
    r"\b(compare|comparison|versus|vs|cheaper|cheapest|costlier|better than|than|other|others|another|similar|alternative|"
    r"alternatives|instead|recommend|suggest|under|below|budget|show me|do you have|how do i get|directions?|way to)\b",
    re.IGNORECASE,
)
POLICY_HINTS = re.compile(
    r"\b(policy|policies|return|returns|refund|exchange|emi|warranty|delivery|deliver|parking|timings?|open|close|closes|"
    r"offers?|payment|pay|upi|card|loyalty|rewards?|gift)\b",
    re.IGNORECASE,
)


def _mentions_other_product(question, product):
    q = question.lower()
    for other in store_db.list_products():
        if product and other["qrCode"] == product["qrCode"]:
            continue
        names = {w for w in re.findall(r"[a-z]{4,}", f"{other.get('brand', '')} {other['name']}".lower())}
        if any(n in q for n in names if n not in {"men", "women", "with", "wireless", "regular"}):
            return True
    return False


# ---------------------------------------------------------------------------
# Obvious tool calls made in code
# ---------------------------------------------------------------------------
# A 3B model often picks the wrong arguments for the two most common shop-floor questions (it compared the wrong pair of shoes,
# or walked "from the entrance" when the shopper was standing in an aisle). When the question names its products, the call is
# made here and its result is handed to the model, which only has to put it into words. Anything less clear goes to the model.

DIRECTIONS_RE = re.compile(r"\b(how (?:do|can|should) i (?:get|go|reach)|directions?|way to|take me|navigate|where (?:is|are|can i find|do i find))\b", re.I)
COMPARE_RE = re.compile(r"\b(cheaper|cheapest|costlier|compare|comparison|versus|vs|difference|more expensive|which is better)\b", re.I)
THIS_RE = re.compile(r"\b(this|it|these|that one)\b", re.I)
NAME_NOISE = {"men", "mens", "women", "womens", "shoe", "shoes", "running", "sneaker", "sneakers", "shirt", "jeans", "with", "wireless",
              "bluetooth", "regular", "fit", "slim", "black", "navy", "blue", "green", "grey", "gray", "white", "silver", "pink",
              "ear", "earbuds", "headphones", "speaker", "portable", "truly", "waterproof", "set", "suit", "the", "and"}


def _named_products(question):
    """Products the question names by a model word or brand: [(product, distinctive_words_hit)]."""
    q = set(re.findall(r"[a-z0-9]+", question.lower()))
    brands = {(p.get("brand") or "").lower() for p in store_db.list_products()}
    found = []
    for p in store_db.list_products():
        words = set(re.findall(r"[a-z0-9]{3,}", f"{p.get('brand') or ''} {p['name']}".lower())) - NAME_NOISE
        hits = words & q
        if hits:
            found.append((p, hits - brands, len(hits)))
    return found


def plan_calls(question, product):
    """[(tool_name, args)] that can be decided without the model, or []."""
    named = _named_products(question)
    specific = [p for p, distinct, _ in named if distinct]
    if product:
        specific = [p for p in specific if p["qrCode"] != product["qrCode"]]
    if COMPARE_RE.search(question):
        codes = [p["qrCode"] for p in specific]
        if product and THIS_RE.search(question):
            codes.insert(0, product["qrCode"])
        codes = list(dict.fromkeys(codes))
        if len(codes) >= 2:
            return [("compare_products", {"qr_codes": codes})]
    if DIRECTIONS_RE.search(question) and len(specific) == 1:
        origin = "entrance"
        m = re.search(r"from aisle\s*(\d)", question, re.I)
        if m:
            origin = f"aisle-{m.group(1)}"
        elif product and re.search(r"\bfrom (?:here|this)\b", question, re.I):
            origin = (product.get("location") or {}).get("aisle") or "entrance"
        return [("get_directions", {"qr_code": specific[0]["qrCode"], "from_checkpoint": origin})]
    return []


def needs_agent(question, product):
    """
    Route a question: the agent for anything that involves other products, search or directions; the single-call
    RAG path for questions about the product on screen and for pure store-policy questions (retrieval is automatic
    there, which proved more reliable than letting the model decide to call a tool).
    """
    if AGENT_HINTS.search(question) or _mentions_other_product(question, product):
        return True
    if POLICY_HINTS.search(question):
        return False
    return product is None


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------

def system_prompt(persona, product):
    prompt = (
        f"You are ShopMart, the in-store shopping assistant of an Indian mall, talking to a '{persona}'.\n"
        "Rules:\n"
        "- Use the tools to look up products, prices, comparisons, store information and directions. Never guess a price, aisle or policy.\n"
        "- Call a tool only when you need it. If the answer is already in 'Product the shopper is viewing', answer directly.\n"
        "- Prices are in Indian Rupees (₹). Never use '$'. Never change or negotiate prices.\n"
        "- Answer in 2-4 short sentences. When you recommend or compare products, give each name, price and aisle.\n"
        "- Never guess a qr_code. Use the product name as the shopper said it, or a code from an earlier tool result.\n"
        "- Mention only products that the tools returned. Never invent or suggest products, brands, prices or aisles that are not in the tool results.\n"
        "- If the tools return nothing relevant, say you couldn't find it."
    )
    catalogue = store_db.list_products()[:40]    # a compact index; with a large catalogue the search tool is the way in
    prompt += "\n\nCatalogue (pass the product name to the tools):\n" + "\n".join(f"- {p['name']}" for p in catalogue)
    if product:
        aisle = (product.get("location") or {}).get("aisle") or ""
        num = re.search(r"\d+", aisle)
        if num:
            prompt += (f"\n\nThe shopper is standing in {aisle} next to this product. When they ask for directions 'from here', call "
                       f"get_directions with from_checkpoint='aisle-{num.group(0)}'. When you give directions, list the steps from the tool result "
                       "and do not estimate walking time. Words like 'this' or 'it' mean this product, so include its qr_code "
                       f"({product['qrCode']}) whenever you compare it with something else.")
        prompt += f"\n\nProduct the shopper is viewing (qr_code {product['qrCode']}):\n{assistant.build_product_context(product)}"
    return prompt


def _fallback_prompt(question, persona):
    """RAG-only answer when the agent loop produced nothing: nearest products + policies, no tools."""
    parts = []
    try:
        found = rag.search_products(question, limit=3)
        parts += [assistant.build_product_context(r["product"]) for r in found["results"]]
        products = [r["product"]["qrCode"] for r in found["results"]]
    except Exception:
        products = []
    policies = rag.policy_context(question)
    text = (
        f"You are ShopMart, an in-store shopping assistant talking to a '{persona}'. Answer in 2-4 short sentences using only the "
        "information below. Use ₹, never '$'. If the information does not answer the question, say you don't know."
    )
    if parts:
        text += "\n\nProducts:\n" + "\n\n".join(parts)
    if policies:
        text += "\n\nStore information:\n" + "\n".join(f"[{p['title']}] {p['text']}" for p in policies)
    return text, products, assistant.sources_for(policies)


def run_agent(question, persona="General Buyer", history=None, product=None, max_rounds=MAX_ROUNDS, model=None):
    messages = [{"role": "system", "content": system_prompt(persona, product)}]
    messages += assistant.clean_history(history)
    messages.append({"role": "user", "content": question.strip()})

    tools_used, products, sources = [], [], []
    final_text, seen_calls, rounds = "", set(), 0

    planned = plan_calls(question, product)
    if planned:
        messages.append({"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": name, "arguments": args}} for name, args in planned]})
        for name, args in planned:
            seen_calls.add((name, json.dumps(args, sort_keys=True)))
            result, label, qrs, srcs = execute_tool(name, args)
            tools_used.append(name)
            yield {"event": "tool", "name": name, "args": args, "label": label}
            products += [q for q in qrs if q not in products]
            sources += [s for s in srcs if s not in sources]
            messages.append({"role": "tool", "tool_name": name, "content": json.dumps(result, ensure_ascii=False)[:3500]})

    for rounds in range(1, max_rounds + 1):
        text_parts, raw_calls, buffering, started = [], [], False, False
        for kind, payload in llm.stream_chat_events(messages, tools=TOOLS, model=model):
            if kind == "tool_calls":
                raw_calls.extend(payload)
                continue
            text_parts.append(payload)
            if not started:
                head = "".join(text_parts).lstrip()
                if not head:
                    continue
                started = True
                buffering = head[0] in "{[<"          # looks like a tool call written as text: hold it back
                if not buffering:
                    yield {"event": "token", "text": "".join(text_parts)}
                continue
            if not buffering:
                yield {"event": "token", "text": payload}

        text = "".join(text_parts)
        calls = _normalise_calls(raw_calls) or (_calls_from_text(text) if buffering else [])
        if not calls:
            if buffering:                              # it was an ordinary answer that happened to start with a bracket
                yield {"event": "token", "text": text}
            final_text = text.strip()
            break

        messages.append({"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": c["name"], "arguments": c["args"]}} for c in calls]})
        for c in calls:
            key = (c["name"], json.dumps(c["args"], sort_keys=True))
            if key in seen_calls:
                result, label, qrs, srcs = {"note": "You already called this tool with these arguments. Use the earlier result and answer now."}, None, [], []
            else:
                seen_calls.add(key)
                result, label, qrs, srcs = execute_tool(c["name"], c["args"])
                tools_used.append(c["name"])
                yield {"event": "tool", "name": c["name"], "args": c["args"], "label": label}
            products += [q for q in qrs if q not in products]
            sources += [s for s in srcs if s not in sources]
            messages.append({"role": "tool", "tool_name": c["name"], "content": json.dumps(result, ensure_ascii=False)[:3500]})
    else:
        # Out of rounds with tools still being requested: ask for the answer without tools
        messages.append({"role": "user", "content": "Now answer the shopper using the information above. Do not call any more tools."})
        for kind, payload in llm.stream_chat_events(messages, tools=None, model=model):
            if kind == "text":
                final_text += payload
                yield {"event": "token", "text": payload}
        final_text = final_text.strip()

    fallback = False
    if not final_text:
        fallback = True
        system, fb_products, fb_sources = _fallback_prompt(question, persona)
        products += [q for q in fb_products if q not in products]
        sources += [s for s in fb_sources if s not in sources]
        fb_messages = [{"role": "system", "content": system}] + assistant.clean_history(history) + [{"role": "user", "content": question.strip()}]
        for piece in llm.stream_chat(fb_messages, temperature=0.2, model=model):
            final_text += piece
            yield {"event": "token", "text": piece}

    yield {"event": "done", "tools": tools_used, "products": products, "sources": sources,
           "fallback": fallback, "rounds": rounds, "answer": final_text.strip()}
