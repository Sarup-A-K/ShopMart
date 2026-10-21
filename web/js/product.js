/**
 * Product page (/p/<qr_code>): what a shopper sees after scanning a price tag.
 */
(() => {
  const $ = (id) => document.getElementById(id);
  const { api, escapeHtml, inr, priceHtml, discountPercent } = Omni;

  const match = window.location.pathname.match(/\/p\/([^/?#]+)/);
  const qrCode = match ? decodeURIComponent(match[1]) : "";

  const PERSONA_KEY = "omnitag_persona";
  let product = null;

  function showNotFound() {
    $("loading").classList.add("hidden");
    $("not-found").classList.remove("hidden");
    document.title = "Tag not found | OmniTag Mall";
  }

  // ---------- Header, price and comparison ----------
  function renderHead(p) {
    document.title = `${p.name} | OmniTag Mall`;
    $("crumb-category").textContent = p.category || "Products";
    $("crumb-brand").textContent = p.brand || "";
    $("p-image").onerror = () => Omni.imageFallback($("p-image"));
    $("p-image").src = p.image;
    $("p-image").alt = p.name;
    $("p-brand").textContent = `Brand: ${p.brand}`;
    $("p-brand").href = `/?q=${encodeURIComponent(p.brand || "")}`;
    $("p-name").textContent = p.name;
    $("p-desc").textContent = p.description || "";

    const off = discountPercent(p);
    const badges = [];
    if (p.priceMatched) badges.push(`<span class="badge badge-match">✓ Beats online price</span>`);
    $("p-badges").innerHTML = badges.join("");

    $("p-price-row").innerHTML = `
      ${off ? `<span class="off" style="font-size: 1.3rem; font-weight: 400;">-${off}%</span>` : ""}
      ${priceHtml(p.price)}
      ${p.originalPrice && p.originalPrice > p.price ? `<span class="mrp">M.R.P.: <s>₹${inr(p.originalPrice)}</s></span>` : ""}`;

    const note = $("p-save-note");
    if (p.priceMatched && typeof p.compPrice === "number") {
      note.textContent = `You save ₹${inr(p.compPrice - p.price)} compared to ${p.compName} (₹${inr(p.compPrice)}). We price ~5% below the cheapest online store.`;
      note.classList.remove("hidden");
    }
  }

  function renderCompare(p) {
    const priced = p.competitors.filter(c => typeof c.price === "number");
    const cheapest = priced.length ? Math.min(...priced.map(c => c.price)) : null;
    const rows = [`<tr class="ours"><td>OmniTag Mall (this store)</td><td>₹${inr(p.price)}</td></tr>`];
    p.competitors.forEach(c => {
      if (typeof c.price === "number") {
        const tag = c.price === cheapest ? `<span class="cheapest-tag">lowest online</span>` : "";
        rows.push(`<tr><td>${escapeHtml(c.name)}${tag}</td><td>₹${inr(c.price)}</td></tr>`);
      } else {
        rows.push(`<tr><td>${escapeHtml(c.name)}</td><td class="na">Not available</td></tr>`);
      }
    });
    $("compare-rows").innerHTML = rows.join("");
    if (p.pricesUpdatedAt) {
      const when = new Date(p.pricesUpdatedAt).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
      $("compare-updated").textContent = `Online prices checked by the store on ${when}.`;
    }
  }

  // ---------- Details & reviews ----------
  function renderDetails(p) {
    const specs = p.specifications || {};
    const rows = Object.entries(specs.keySpecs || {}).map(([k, v]) => [k, v]);
    if (specs.warranty) rows.push(["Warranty", specs.warranty]);
    if (p.category) rows.push(["Category", p.category]);
    $("spec-rows").innerHTML = rows.map(([k, v]) => `<tr><th>${escapeHtml(k)}</th><td>${escapeHtml(v)}</td></tr>`).join("");
    $("feature-list").innerHTML = (specs.features || []).map(f => `<li>${escapeHtml(f)}</li>`).join("");

    const reviews = p.reviews || [];
    $("reviews").innerHTML = reviews.length
      ? reviews.map((r, i) => `<div class="review"><div class="who">Shopper review ${i + 1}</div>${escapeHtml(r)}</div>`).join("")
      : `<p class="muted">No reviews yet.</p>`;
  }

  // ---------- AI assistant ----------
  const personaSelect = $("persona");
  try { personaSelect.value = localStorage.getItem(PERSONA_KEY) || "General Buyer"; } catch (e) { /* storage blocked */ }
  if (!personaSelect.value) personaSelect.value = "General Buyer";

  let insightRequest = 0;
  async function loadInsight() {
    const requestId = ++insightRequest;
    $("insight").innerHTML = `<div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>`;
    let res;
    try {
      res = await api("/api/scan_tag", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ product_name: product.name, qr_code: product.qrCode, category: product.category, user_context: personaSelect.value })
      });
    } catch (e) {
      res = { ok: false };
    }
    if (requestId !== insightRequest) return; // persona changed meanwhile
    if (!res.ok || !res.body || !res.body.success) {
      $("insight").innerHTML = `<div class="insight-item">The AI assistant is unavailable right now. Prices, directions and details above are still up to date.</div>`;
      return;
    }
    const a = res.body.data.analysis;
    const items = [
      ["Verdict", a.verdict],
      ["Deal score", a.dealScore],
      [`How it fits a ${personaSelect.value}`, a.compatibility],
      ["In plain words", a.specsTranslation]
    ].filter(([, v]) => v);
    $("insight").innerHTML = items.map(([k, v]) => `<div class="insight-item"><strong>${escapeHtml(k)}</strong>${escapeHtml(v)}</div>`).join("");
  }

  personaSelect.addEventListener("change", () => {
    try { localStorage.setItem(PERSONA_KEY, personaSelect.value); } catch (e) { /* storage blocked */ }
    loadInsight();
  });

  function addMessage(text, kind) {
    const div = document.createElement("div");
    div.className = `msg msg-${kind}`;
    div.textContent = text;
    $("chat-log").appendChild(div);
    $("chat-log").scrollTop = $("chat-log").scrollHeight;
    return div;
  }

  function addSources(bubble, sources) {
    const row = document.createElement("div");
    row.className = "sources";
    row.append("Sources: ");
    sources.forEach(src => {
      const chip = document.createElement("span");
      chip.className = "source-chip";
      chip.textContent = src.title;
      row.appendChild(chip);
    });
    bubble.appendChild(row);
  }

  // Conversation memory: the server receives the recent turns so follow-ups ("and the price?") make sense
  const history = [];

  function showTyping(el) {
    el.classList.add("typing");
    el.textContent = "Thinking…";
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

  async function ask(question) {
    question = question.trim();
    if (!question) return;
    addMessage(question, "user");
    $("chat-input").value = "";
    $("chat-send").disabled = true;
    const bubble = addMessage("", "ai");
    showTyping(bubble);
    let text = "";
    let failed = false;
    try {
      const res = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          product_name: product.name, qr_code: product.qrCode, question,
          persona: personaSelect.value, history: history.slice(-6)
        })
      });
      if (!res.ok || !res.body) throw new Error("bad response");
      await readEvents(res, (name, data) => {
        if (name === "token") {
          if (!text) bubble.classList.remove("typing");
          text += data.text;
          bubble.textContent = text;
          $("chat-log").scrollTop = $("chat-log").scrollHeight;
        } else if (name === "done") {
          if (data.sources && data.sources.length) addSources(bubble, data.sources);
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
    }
    $("chat-send").disabled = false;
    $("chat-input").focus();
  }

  $("chat-form").addEventListener("submit", (e) => { e.preventDefault(); ask($("chat-input").value); });
  $("suggestions").addEventListener("click", (e) => {
    const btn = e.target.closest(".suggestion");
    if (btn) ask(btn.textContent);
  });

  // ---------- Load ----------
  (async () => {
    if (!qrCode) return showNotFound();
    let res;
    try {
      res = await api(`/api/products/${encodeURIComponent(qrCode)}`);
    } catch (e) {
      res = { ok: false, status: 0 };
    }
    if (!res.ok) {
      if (res.status !== 404) {
        $("not-found").querySelector("h2").textContent = "Store is offline";
        $("not-found").querySelector("p").textContent = "We couldn't load this product. Please try again in a moment.";
      }
      return showNotFound();
    }
    product = res.body.product;

    $("loading").classList.add("hidden");
    $("product-view").classList.remove("hidden");
    $("sticky-bar").classList.remove("hidden");

    renderHead(product);
    renderCompare(product);
    renderDetails(product);

    const loc = product.location || {};
    $("w-aisle").textContent = `📍 ${loc.aisle || "Ask staff"}${loc.section ? ` · ${loc.section}` : ""}`;
    Wayfinding.init({ product, canvas: $("w-map"), select: $("w-near"), stepsEl: $("w-steps"), summaryEl: $("w-summary") });

    addMessage(`Hi! Ask me anything about the ${product.brand} ${product.category ? product.category.toLowerCase() : "product"}: price, fit, or where to find it.`, "ai");
    loadInsight();
  })();
})();
