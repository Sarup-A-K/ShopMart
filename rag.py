"""
Retrieval-Augmented Generation (RAG) and semantic search.

What is indexed (text only, embedded with nomic-embed-text):
  - one chunk per product (description, specs, features)
  - one chunk per customer review
  - one chunk per section of knowledge/store_policies.md
Prices are NOT indexed. They are always read live from the database, so an admin price
change is reflected immediately without re-embedding anything.
"""
import hashlib
import os
import re
import threading
import time

import numpy as np

import llm
import store_db

KNOWLEDGE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge", "store_policies.md")

# How strongly an exact word match nudges the score on top of the embedding similarity
KEYWORD_WEIGHT = 0.08
# Keep search results that are close to the best result
RELATIVE_CUTOFF = 0.12
# A policy section is added to a chat prompt when it is strongly similar (>= POLICY_STRONG_SCORE), or
# moderately similar (>= POLICY_MIN_SCORE) AND shares a content word with the question. The second
# route rescues natural questions whose extra words dilute the embedding ("Can I return this kurta if
# it does not fit?" scores 0.61) while still rejecting accidental matches ("battery life" -> warranty).
POLICY_STRONG_SCORE = 0.70
POLICY_MIN_SCORE = 0.58
# Product search: below MIN_SCORE nothing is shown; between MIN_SCORE and CONFIDENT_SCORE the
# results are labelled "closest matches" instead of "results". Calibrated on the demo catalogue
# (clear queries score 0.70+, vague ones 0.50-0.65, unrelated ones under 0.50).
MIN_SCORE = 0.50
CONFIDENT_SCORE = 0.62

_lock = threading.Lock()
_index = {"matrix": None, "meta": [], "ready": False, "error": None}

STOPWORDS = {
    "a", "an", "the", "for", "and", "or", "of", "in", "on", "to", "with", "is", "are", "me", "my", "i", "do", "does",
    "can", "you", "show", "find", "get", "want", "need", "looking", "some", "any", "what", "which", "best", "good",
    "under", "below", "than", "less", "within", "above", "over", "rs", "rupees", "price", "cost", "this", "that", "it",
    "have", "has", "had", "if", "not", "no", "how", "many", "much", "there", "your", "our", "we", "be", "was", "were",
    "will", "would", "should", "could", "about", "tell", "give", "let", "know", "please", "when", "where", "who",
    # words that appear in almost every policy section, so they say nothing about relevance
    "mall", "store", "option", "options", "available", "item", "items", "product", "products",
}

# Words shoppers use -> catalogue category. Categories themselves are matched from the data.
CATEGORY_WORDS = {
    "Footwear": {"shoe", "shoes", "sandal", "sandals", "footwear", "sneaker", "sneakers", "slipper", "slippers", "running"},
    "Electronics": {"phone", "phones", "mobile", "mobiles", "smartphone", "earbud", "earbuds", "headphone", "headphones",
                    "earphones", "electronics", "gadget", "gadgets", "audio"},
    "Fashion": {"shirt", "shirts", "tshirt", "t-shirt", "kurta", "kurtas", "clothes", "clothing", "apparel", "fashion",
                "dress", "wear"},
}


# ---------------------------------------------------------------------------
# Building the index
# ---------------------------------------------------------------------------

def _hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def policy_chunks():
    if not os.path.exists(KNOWLEDGE_PATH):
        return []
    with open(KNOWLEDGE_PATH, encoding="utf-8") as f:
        text = f.read()
    chunks = []
    for section in re.split(r"^## ", text, flags=re.MULTILINE)[1:]:
        title, _, body = section.partition("\n")
        title, body = title.strip(), body.strip()
        if body:
            slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            chunks.append({"id": f"policy:{slug}", "source_type": "policy", "source_id": slug,
                           "title": title, "text": f"{title}. {body}"})
    return chunks


def product_chunks():
    chunks = []
    for p in store_db.list_products():
        specs = p.get("specifications") or {}
        parts = [f"{p['name']} by {p.get('brand')}. Category: {p.get('category')}.", p.get("description") or ""]
        if specs.get("keySpecs"):
            parts.append("Specifications: " + ", ".join(f"{k} {v}" for k, v in specs["keySpecs"].items()) + ".")
        if specs.get("features"):
            parts.append("Features: " + ", ".join(specs["features"]) + ".")
        if specs.get("warranty"):
            parts.append(f"Warranty: {specs['warranty']}.")
        if p.get("aiSummary"):
            parts.append(f"Review summary: {p['aiSummary']}")
        chunks.append({"id": f"product:{p['qrCode']}", "source_type": "product", "source_id": p["qrCode"],
                       "title": p["name"], "text": " ".join(x for x in parts if x)})
        for i, review in enumerate(p.get("reviews") or [], start=1):
            chunks.append({"id": f"review:{p['qrCode']}:{i}", "source_type": "review", "source_id": p["qrCode"],
                           "title": f"Review of {p.get('brand') or p['name']}", "text": f"Customer review of {p['name']}: {review}"})
    return chunks


def all_chunks():
    return product_chunks() + policy_chunks()


def ensure_index(force=False):
    """Embed new or changed chunks, drop removed ones, and (re)load the in-memory search matrix."""
    chunks = all_chunks()
    with store_db.connect() as conn:
        existing = {r["id"]: r["text_hash"] for r in conn.execute("SELECT id, text_hash FROM embeddings")}
        wanted = {c["id"]: _hash(c["text"]) for c in chunks}
        stale = [c for c in chunks if force or existing.get(c["id"]) != wanted[c["id"]]]
        removed = [i for i in existing if i not in wanted]

        if stale:
            vectors = []
            for start in range(0, len(stale), 16):
                vectors += llm.embed([c["text"] for c in stale[start:start + 16]], kind="document")
            for c, vec in zip(stale, vectors):
                blob = np.asarray(vec, dtype=np.float32).tobytes()
                conn.execute(
                    "INSERT OR REPLACE INTO embeddings (id, source_type, source_id, title, text, text_hash, vector) VALUES (?,?,?,?,?,?,?)",
                    (c["id"], c["source_type"], c["source_id"], c["title"], c["text"], wanted[c["id"]], blob),
                )
        for i in removed:
            conn.execute("DELETE FROM embeddings WHERE id = ?", (i,))
        rows = conn.execute("SELECT id, source_type, source_id, title, text, vector FROM embeddings").fetchall()

    meta, vecs = [], []
    for r in rows:
        meta.append({"id": r["id"], "source_type": r["source_type"], "source_id": r["source_id"], "title": r["title"], "text": r["text"]})
        vecs.append(np.frombuffer(r["vector"], dtype=np.float32))
    matrix = np.vstack(vecs) if vecs else None
    if matrix is not None:
        matrix = matrix / np.clip(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-9, None)
    with _lock:
        _index.update(matrix=matrix, meta=meta, ready=matrix is not None, error=None)
    return {"chunks": len(meta), "embedded_now": len(stale), "removed": len(removed)}


def start_background_index(retries=30, delay=4):
    """Build the index when the server starts, waiting for Ollama to come up."""
    def run():
        for attempt in range(retries):
            try:
                stats = ensure_index()
                print(f"RAG index ready: {stats}")
                return
            except llm.LLMError as e:
                _index["error"] = str(e)
                time.sleep(delay)
            except Exception as e:  # never crash the server because of indexing
                _index["error"] = str(e)
                print(f"RAG indexing failed: {e}")
                return
        print("RAG index not built: Ollama never became reachable")
    threading.Thread(target=run, daemon=True).start()


def status():
    return {"ready": _index["ready"], "chunks": len(_index["meta"]), "error": _index["error"]}


# ---------------------------------------------------------------------------
# Query understanding
# ---------------------------------------------------------------------------

PRICE_PATTERNS = [
    r"(?:under|below|less than|within|upto|up to|max(?:imum)?|cheaper than|not more than)\s*(?:rs\.?|inr|₹)?\s*(\d[\d,]*)",
    r"<\s*=?\s*(?:rs\.?|inr|₹)?\s*(\d[\d,]*)",
    r"(?:rs\.?|inr|₹)\s*(\d[\d,]*)\s*(?:or less|and below|max)",
]


def tokens(text):
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOPWORDS and len(t) > 1]


def parse_query(query):
    """Pull structured filters out of a natural-language query: max price and category."""
    q = query.strip()
    filters = {}
    for pattern in PRICE_PATTERNS:
        m = re.search(pattern, q, flags=re.IGNORECASE)
        if m:
            filters["max_price"] = float(m.group(1).replace(",", ""))
            q = (q[:m.start()] + " " + q[m.end():]).strip()
            break
    words = set(re.findall(r"[a-z\-]+", q.lower()))
    for category, vocab in CATEGORY_WORDS.items():
        # "running"/"wear" are weak hints; only apply a category on stronger words
        strong = vocab - {"running", "wear"}
        if words & strong:
            filters["category"] = category
            break
    return q, filters


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def _scores(query, query_terms):
    """Return (meta list, score array) for a query over every chunk."""
    with _lock:
        matrix, meta = _index["matrix"], _index["meta"]
    if matrix is None:
        raise RuntimeError("index not ready")
    qvec = np.asarray(llm.embed([query], kind="query")[0], dtype=np.float32)
    qvec /= max(np.linalg.norm(qvec), 1e-9)
    sims = matrix @ qvec
    if query_terms:
        boosts = np.array([
            sum(1 for t in query_terms if t in (m["title"] + " " + m["text"]).lower()) / len(query_terms)
            for m in meta
        ])
        sims = sims + KEYWORD_WEIGHT * boosts
    return meta, sims


def search_chunks(query, k=4, source_types=None, source_id=None):
    """Top-k chunks, optionally restricted to certain types or to one product."""
    meta, sims = _scores(query, tokens(query))
    order = np.argsort(-sims)
    results = []
    for i in order:
        m = meta[i]
        if source_types and m["source_type"] not in source_types:
            continue
        if source_id and m["source_type"] != "policy" and m["source_id"] != source_id:
            continue
        results.append({**m, "score": float(sims[i])})
        if len(results) >= k:
            break
    return results


def search_products(query, limit=6):
    """
    Semantic product search: embed the query, score product and review chunks, take each
    product's best chunk, then apply the price/category filters parsed from the query.
    Prices come live from the database.
    """
    cleaned, filters = parse_query(query)
    semantic_query = cleaned if tokens(cleaned) else query
    products = {p["qrCode"]: p for p in store_db.list_products()}

    def keep(p):
        if filters.get("max_price") and p["price"] > filters["max_price"]:
            return False
        if filters.get("category") and p.get("category") != filters["category"]:
            return False
        return True

    candidates = {qr for qr, p in products.items() if keep(p)}
    if not candidates:
        return {"query": query, "filters": filters, "results": [], "confident": False}

    meta, sims = _scores(semantic_query, tokens(semantic_query))
    best = {}
    for m, score in zip(meta, sims):
        if m["source_type"] in ("product", "review") and m["source_id"] in candidates:
            best[m["source_id"]] = max(best.get(m["source_id"], -1.0), float(score))

    ranked = sorted(best.items(), key=lambda kv: -kv[1])
    ranked = [r for r in ranked if r[1] >= MIN_SCORE]
    if ranked:
        top = ranked[0][1]
        ranked = [r for r in ranked if r[1] >= top - RELATIVE_CUTOFF]
    results = [{"product": products[qr], "score": round(score, 3)} for qr, score in ranked[:limit]]
    confident = bool(results) and results[0]["score"] >= CONFIDENT_SCORE
    if not confident:
        results = results[:3]  # weak matches: show only the nearest few rather than the whole catalogue
    return {"query": query, "filters": filters, "results": results, "confident": confident}


def _shares_content_word(question, text):
    """True if any content word of the question (matched by its first 5 letters) appears in the text."""
    low = text.lower()
    return any(t[:5] in low for t in tokens(question) if len(t) >= 4)


def policy_context(question, k=2):
    """Policy sections relevant to a question, for adding to a chat prompt. Returns [] if none qualify."""
    if not _index["ready"]:
        return []
    try:
        hits = search_chunks(question, k=k, source_types={"policy"})
    except Exception:
        return []
    return [
        h for h in hits
        if h["score"] >= POLICY_STRONG_SCORE
        or (h["score"] >= POLICY_MIN_SCORE and _shares_content_word(question, h["text"]))
    ]
