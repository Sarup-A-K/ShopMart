"""
Ollama client used by every GenAI feature: chat (with optional tools and JSON schema),
token streaming, and text embeddings.
"""
import json
import os

import requests

# Base URL of the Ollama server. OLLAMA_API_URL (older setting, pointing at /api/generate) is still accepted.
_legacy = os.environ.get("OLLAMA_API_URL", "")
OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL") or (_legacy.split("/api/")[0] if _legacy else "http://llm-engine:11434")
CHAT_MODEL = os.environ.get("LLM_MODEL", "llama3.2")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")


class LLMError(Exception):
    pass


def _post(path, payload, timeout, stream=False):
    try:
        res = requests.post(f"{OLLAMA_BASE}{path}", json=payload, timeout=timeout, stream=stream)
        res.raise_for_status()
        return res
    except requests.HTTPError as e:
        detail = ""
        try:
            detail = e.response.json().get("error", "")
        except Exception:
            pass
        raise LLMError(f"Ollama error: {detail or e}")
    except requests.RequestException:
        raise LLMError(f"Unable to reach the local Ollama LLM at {OLLAMA_BASE}. Ensure the llm-engine container is running.")


def chat(messages, tools=None, format=None, model=None, temperature=0.4, timeout=120):
    """One chat completion. Returns the assistant message dict: {"content": str, "tool_calls": [...]}."""
    payload = {
        "model": model or CHAT_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature, "top_p": 0.9},
    }
    if tools:
        payload["tools"] = tools
    if format is not None:
        payload["format"] = format  # "json" or a JSON schema dict
    data = _post("/api/chat", payload, timeout).json()
    message = data.get("message") or {}
    message.setdefault("content", "")
    message.setdefault("tool_calls", [])
    return message


def stream_chat(messages, model=None, temperature=0.4, timeout=120):
    """Yield the assistant's reply text piece by piece as Ollama generates it."""
    payload = {
        "model": model or CHAT_MODEL,
        "messages": messages,
        "stream": True,
        "options": {"temperature": temperature, "top_p": 0.9},
    }
    res = _post("/api/chat", payload, timeout, stream=True)
    try:
        for line in res.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            if chunk.get("error"):
                raise LLMError(f"Ollama error: {chunk['error']}")
            text = (chunk.get("message") or {}).get("content", "")
            if text:
                yield text
            if chunk.get("done"):
                break
    except requests.RequestException:
        raise LLMError("The connection to the local LLM was interrupted.")
    finally:
        res.close()


def generate(system, prompt, format=None, model=None, temperature=0.4):
    """Convenience wrapper: system prompt + one user message, returns the reply text."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    return chat(messages, format=format, model=model, temperature=temperature)["content"]


def embed(texts, kind="document", model=None):
    """
    Embed a list of texts. nomic-embed-text expects a task prefix:
    "search_document: " for indexed content and "search_query: " for user queries.
    """
    if not texts:
        return []
    prefix = "search_query: " if kind == "query" else "search_document: "
    payload = {"model": model or EMBED_MODEL, "input": [prefix + t for t in texts]}
    data = _post("/api/embed", payload, timeout=120).json()
    return data.get("embeddings", [])
