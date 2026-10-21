/**
 * Reusable streaming chat widget for the product page and the store-wide assistant.
 * Handles: Server-Sent Events from /api/chat/stream, conversation memory, tool-use chips,
 * policy-source chips and links to the products the assistant looked at.
 */
const OmniChat = (() => {
  let productMapPromise = null;
  function productMap() {
    if (!productMapPromise) {
      productMapPromise = Omni.api("/api/products").then(res => {
        const map = {};
        ((res.body && res.body.products) || []).forEach(p => { map[p.qrCode] = p; });
        return map;
      }).catch(() => ({}));
    }
    return productMapPromise;
  }

  /** Read a Server-Sent Events response and call onEvent(name, data) for each event. */
  async function readEvents(response, onEvent) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let split;
      while ((split = buffer.indexOf("\n\n")) !== -1) {
        const raw = buffer.slice(0, split);
        buffer = buffer.slice(split + 2);
        const name = (raw.match(/^event: (.*)$/m) || [])[1];
        const data = (raw.match(/^data: (.*)$/m) || [])[1];
        if (name && data) onEvent(name, JSON.parse(data));
      }
    }
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  /**
   * options: { log, form, input, send, suggestions?, getPayload(): {qr_code?, persona}, welcome?: string, mode? }
   */
  function create(options) {
    const { log, form, input, send, suggestions, getPayload } = options;
    const history = [];

    function scroll() { log.scrollTop = log.scrollHeight; }

    function addMessage(text, kind) {
      const div = el("div", `msg msg-${kind}`, text);
      log.appendChild(div);
      scroll();
      return div;
    }

    async function ask(question) {
      question = question.trim();
      if (!question || send.disabled) return;
      addMessage(question, "user");
      input.value = "";
      send.disabled = true;

      const bubble = el("div", "msg msg-ai");
      const toolsRow = el("div", "tools");
      const textEl = el("span", "answer", "Thinking…");
      bubble.classList.add("typing");
      bubble.append(toolsRow, textEl);
      log.appendChild(bubble);
      scroll();

      let text = "";
      let failed = false;
      let doneInfo = null;
      try {
        const res = await fetch("/api/chat/stream", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...getPayload(), question, history: history.slice(-6), mode: options.mode || "auto" })
        });
        if (!res.ok || !res.body) throw new Error("bad response");
        await readEvents(res, (name, data) => {
          if (name === "tool") {
            toolsRow.appendChild(el("span", "tool-chip", `🔧 ${data.label}`));
            scroll();
          } else if (name === "token") {
            if (!text) bubble.classList.remove("typing");
            text += data.text;
            textEl.textContent = text;
            scroll();
          } else if (name === "replace") {
            // The first answer failed the fact-check: show the corrected one instead
            text = data.text;
            textEl.textContent = text;
          } else if (name === "done") {
            doneInfo = data;
          } else if (name === "error") {
            failed = true;
          }
        });
      } catch (e) {
        failed = true;
      }
      bubble.classList.remove("typing");

      if (failed && !text) {
        bubble.className = "msg msg-error";
        bubble.textContent = "Sorry, the AI assistant is unavailable right now. Please try again shortly.";
      } else {
        history.push({ role: "user", content: question }, { role: "assistant", content: text.trim() });
        if (doneInfo) await decorate(bubble, doneInfo);
      }
      send.disabled = false;
      input.focus();
    }

    async function decorate(bubble, info) {
      if (info.corrected) {
        bubble.appendChild(el("div", "verify warn", "⚠ Corrected using store data"));
      } else if (info.verified && info.facts_checked > 0) {
        bubble.appendChild(el("div", "verify ok", "✓ Prices and locations checked against store data"));
      }
      if (info.sources && info.sources.length) {
        const row = el("div", "sources", "Sources: ");
        info.sources.forEach(src => row.appendChild(el("span", "source-chip", src.title)));
        bubble.appendChild(row);
      }
      if (info.products && info.products.length) {
        const map = await productMap();
        const row = el("div", "related");
        info.products.slice(0, 3).forEach(qr => {
          const p = map[qr];
          if (!p) return;
          const link = el("a", "related-chip", `${p.brand} · ₹${Omni.inr(p.price)} · ${(p.location || {}).aisle || ""}`);
          link.href = Omni.productUrl(qr);
          row.appendChild(link);
        });
        if (row.children.length) bubble.appendChild(row);
      }
      if (info.fallback) {
        bubble.appendChild(el("div", "sources", "Answered from search results (the assistant could not use its tools)."));
      }
      scroll();
    }

    form.addEventListener("submit", (e) => { e.preventDefault(); ask(input.value); });
    if (suggestions) {
      suggestions.addEventListener("click", (e) => {
        const btn = e.target.closest(".suggestion");
        if (btn) ask(btn.textContent);
      });
    }
    if (options.welcome) addMessage(options.welcome, "ai");
    return { ask, addMessage };
  }

  return { create };
})();
