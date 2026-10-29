"""
One entry point for every chat request: input guardrails -> answer generation -> fact-check -> log.

run() is a generator of (event, data) pairs:
  ("tool", {...})      the agent called a tool
  ("token", {"text"})  a piece of the answer
  ("replace", {...})   the answer failed the fact-check and is replaced by a corrected one
  ("done", {...})      summary: tools, products, sources, verified, corrected, blocked, latency...

Modes (used by the evaluation to compare techniques):
  baseline  the model alone, no store data
  context   the current product's facts in the prompt (v1)
  rag       context + retrieved store-policy sections
  agent     tool-calling agent
  auto      router: the agent when the question needs tools, otherwise rag   (the production default)
"""
import time

import agent
import assistant
import guardrails
import llm
import rag
import store_db
import wayfinding

BASELINE_SYSTEM = (
    "You are a helpful shopping assistant in an Indian mall. Answer in 2-4 short sentences. Use Indian Rupees (₹), never '$'."
)


def _plain_history_text(history):
    return " ".join(m.get("content", "") for m in assistant.clean_history(history))


def _stream_single(mode, product, persona, history, question, model=None):
    """Non-agent paths. Yields ("token", text); returns (sources) via the final ("sources", [...])."""
    policies = []
    if mode == "baseline":
        messages = [{"role": "system", "content": BASELINE_SYSTEM}] + assistant.clean_history(history) \
            + [{"role": "user", "content": question.strip()}]
        for piece in llm.stream_chat(messages, model=model):
            yield "token", piece
    else:
        if mode == "rag":
            policies = rag.policy_context(question)
        for piece in assistant.stream_answer(product, persona, history, question, policies, model=model):
            yield "token", piece
    yield "sources", assistant.sources_for(policies)


def _regenerate(question, persona, products, issues, model=None, route_facts=None):
    """One non-streaming retry that is told exactly what was wrong and given only the verified facts."""
    facts = "\n\n".join(assistant.build_product_context(p) for p in products) or "(no product facts available)"
    if route_facts:
        facts += "\n\n" + "\n".join(route_facts) + "\nWhen the shopper asks how to get somewhere, list these steps. Do not estimate walking time."
    system = (
        f"You are ShopMart, an in-store shopping assistant talking to a '{persona}'. Answer in 2-4 short sentences using ONLY the "
        "facts below. Use ₹, never '$'. Do not mention any product, price or aisle that is not in the facts."
        + (" If the shopper asks for a recommendation, mention EVERY product below with its price and aisle, then say which one you would pick and why."
           if len(products) > 1 else "")
        + "\n\nFacts:\n" + facts
    )
    note = "Your previous answer contained errors: " + "; ".join(issues) + ". Answer again correctly."
    return llm.chat([{"role": "system", "content": system}, {"role": "user", "content": f"{question.strip()}\n\n{note}"}],
                    temperature=0.0, model=model)["content"].strip()


def run(question, persona="General Buyer", history=None, product=None, mode="auto", guard=True, debug_append=None, model=None, location=None):
    started = time.time()
    location = wayfinding.normalise_checkpoint(location) if location else None   # only 'entrance' / 'aisle-N' ever reach the prompt
    qr_code = product["qrCode"] if product else None
    history = history or []

    def finish(info):
        info["latency_ms"] = int((time.time() - started) * 1000)
        store_db.log_chat(question, qr_code, persona, info.get("mode"), info.get("tools"), info.get("blocked"),
                          info.get("verified"), info.get("corrected", False), info.get("issues"), info.get("fallback", False),
                          info["latency_ms"])
        return info

    # 1. input guardrails
    if guard:
        verdict = guardrails.check_input(question) or guardrails.check_input_llm(question, product["name"] if product else "")
        if verdict:
            yield "token", {"text": verdict["reply"]}
            yield "done", finish({"mode": mode, "blocked": verdict["category"], "tools": [], "products": [], "sources": [],
                                  "verified": None, "corrected": False, "facts_checked": 0, "issues": []})
            return

    # 2. generate
    use_agent = mode == "agent" or (mode == "auto" and agent.needs_agent(question, product))
    parts, info = [], {"tools": [], "products": [], "sources": [], "fallback": False}
    if use_agent:
        for ev in agent.run_agent(question, persona, history, product, model=model, location=location):
            kind = ev.pop("event")
            if kind == "token":
                parts.append(ev["text"])
                if not guard:
                    yield "token", ev
            elif kind == "tool":
                yield "tool", ev
            elif kind == "done":
                info.update(tools=ev["tools"], products=ev["products"], sources=ev["sources"], fallback=ev["fallback"], route_facts=ev.get("route_facts"))
        used_mode = "agent"
    else:
        used_mode = "baseline" if mode == "baseline" else "context" if mode == "context" else "rag"
        for kind, payload in _stream_single(used_mode, product, persona, history, question, model):
            if kind == "token":
                parts.append(payload)
                if not guard:
                    yield "token", {"text": payload}
            else:
                info["sources"] = payload

    if debug_append and guardrails.TEST_HOOKS:         # test hook: pretend the model made a wrong claim
        parts.append(debug_append)
        if not guard:
            yield "token", {"text": debug_append}

    text = "".join(parts).strip()
    info["mode"] = used_mode

    # 3. fact-check
    verified, corrected, issues, checked = None, False, [], 0
    qrs = list(dict.fromkeys(([qr_code] if qr_code else []) + info["products"]))
    if guard:
        source_titles = " ".join(s["title"] for s in info["sources"])
        # Aisles the shopper is standing in or walking through ("From Aisle 2, walk ...") are facts from the scan and the route tool
        where = ("" if not location or location == "entrance" else f"Aisle {location.split('-')[-1]}") + " " + " ".join(info.get("route_facts") or [])
        allowed = guardrails.build_allowed(qrs, question, _plain_history_text(history) + " " + where, source_titles)
        issues, checked = guardrails.verify_answer(text, allowed)
        verified = not issues
        if issues:
            corrected = True
            try:
                retry = _regenerate(question, persona, allowed["products"], issues, model, info.get("route_facts"))
                retry_issues, _ = guardrails.verify_answer(retry, allowed)
            except llm.LLMError:
                retry, retry_issues = "", ["retry failed"]
            final = retry if retry and not retry_issues else guardrails.safe_answer(allowed["products"])
            text, verified = final, True               # the replacement is verified or built straight from the database
    if guard and text:                                 # the shopper only ever sees the checked answer, never a draft that gets swapped
        yield "token", {"text": text}

    info.update(blocked=None, verified=verified, corrected=corrected, issues=issues, facts_checked=checked, answer=text)
    yield "done", finish(info)


def answer_once(question, persona="General Buyer", history=None, product=None, mode="auto", guard=True, debug_append=None, model=None, location=None):
    """Non-streaming helper (used by /api/ask and the evaluation). Returns the final text plus the done summary."""
    text, done, tool_events = "", {}, []
    for kind, data in run(question, persona, history, product, mode, guard, debug_append, model, location):
        if kind == "token":
            text += data["text"]
        elif kind == "replace":
            text = data["text"]
        elif kind == "tool":
            tool_events.append(data)
        elif kind == "done":
            done = data
    done["tool_events"] = tool_events
    return text.strip(), done
