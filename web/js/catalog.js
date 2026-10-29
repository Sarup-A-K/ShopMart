/**
 * Catalogue page: product grid with category chips and search.
 */
(() => {
  const grid = document.getElementById("product-grid");
  const chips = document.getElementById("category-chips");
  const searchForm = document.getElementById("search-form");
  const searchInput = document.getElementById("search-input");
  const resultsTitle = document.getElementById("results-title");
  const resultsCount = document.getElementById("results-count");
  const emptyState = document.getElementById("empty-state");
  const { escapeHtml, priceHtml, inr, discountPercent, productUrl } = Omni;

  let products = [];
  let activeCategory = "";
  const params = new URLSearchParams(window.location.search);
  searchInput.value = params.get("q") || "";

  function awayText(p) {
    const meters = Wayfinding.distance(p, Omni.where.checkpoint());
    return meters == null ? "" : meters < 3 ? " · you're here" : ` · ${meters} m from you`;
  }

  function cardHtml(p) {
    const off = discountPercent(p);
    const loc = p.location || {};
    return `
      <a class="card product-card" href="${productUrl(p.qrCode)}">
        <div class="thumb"><img src="${escapeHtml(p.image)}" alt="${escapeHtml(p.name)}" loading="lazy" onerror="Omni.imageFallback(this)"></div>
        <div class="body">
          <span class="brand">${escapeHtml(p.brand)}</span>
          <span class="name">${escapeHtml(p.name)}</span>
          ${p.priceMatched ? `<span class="badge badge-match">Beats ${escapeHtml(p.compName)} price</span>` : ""}
          <div class="price-row">
            ${priceHtml(p.price)}
            ${p.originalPrice && p.originalPrice > p.price ? `<span class="mrp">M.R.P. <s>₹${inr(p.originalPrice)}</s></span><span class="off">${off}% off</span>` : ""}
          </div>
          ${loc.aisle ? `<span class="aisle">📍 ${escapeHtml(loc.aisle)} · ${escapeHtml(loc.section || "")}${awayText(p)}</span>` : ""}
        </div>
      </a>`;
  }

  // Semantic search state: multi-word queries ("running shoes under 3000") go to /api/search
  let semantic = null;      // {query, filters, results, confident} for the current query, or null
  let searchTimer = null;
  let searchSeq = 0;
  const searchNote = document.getElementById("search-note");

  const localMatches = (q) => products.filter(p => `${p.name} ${p.brand} ${p.category}`.toLowerCase().includes(q.toLowerCase()));

  // Multi-word queries use semantic search; so does a single word that matches nothing locally ("laptop")
  const isSemanticQuery = (q) => {
    if (q.length < 3) return false;
    return q.split(/\s+/).filter(Boolean).length >= 2 || localMatches(q).length === 0;
  };

  function filterText(filters) {
    const parts = [];
    if (filters.max_price) parts.push(`under ₹${inr(filters.max_price)}`);
    if (filters.category) parts.push(filters.category);
    return parts.join(" · ");
  }

  function render() {
    const raw = searchInput.value.trim();
    const q = raw.toLowerCase();
    let filtered;
    searchNote.classList.add("hidden");

    if (semantic && semantic.query === raw) {
      filtered = semantic.results.map(r => r.product).filter(p => !activeCategory || p.category === activeCategory);
      const f = filterText(semantic.filters);
      if (!semantic.results.length) {
        searchNote.textContent = `No products match "${raw}"${f ? ` (${f})` : ""}.`;
      } else if (!semantic.confident) {
        searchNote.textContent = `No exact match for "${raw}". These are the closest items.`;
      } else {
        searchNote.textContent = `✨ Smart search understood${f ? `: ${f}` : " your request"}.`;
      }
      searchNote.classList.remove("hidden");
    } else {
      filtered = products.filter(p =>
        (!activeCategory || p.category === activeCategory) &&
        (!q || `${p.name} ${p.brand} ${p.category}`.toLowerCase().includes(q))
      );
    }
    grid.innerHTML = filtered.map(cardHtml).join("");
    emptyState.classList.toggle("hidden", filtered.length > 0);
    resultsTitle.textContent = q ? `Results for "${raw}"` : (activeCategory || "All products");
    resultsCount.textContent = `${filtered.length} item${filtered.length === 1 ? "" : "s"}`;
  }

  async function runSemanticSearch() {
    const raw = searchInput.value.trim();
    if (!isSemanticQuery(raw)) { semantic = null; render(); return; }
    const seq = ++searchSeq;
    let res;
    try {
      res = await Omni.api(`/api/search?q=${encodeURIComponent(raw)}`);
    } catch (e) {
      res = { ok: false };
    }
    if (seq !== searchSeq) return; // a newer query is in flight
    semantic = res.ok && res.body && res.body.success ? res.body : null; // fall back to plain filtering
    render();
  }

  function onSearchInput() {
    clearTimeout(searchTimer);
    semantic = null;
    render();
    if (isSemanticQuery(searchInput.value.trim())) searchTimer = setTimeout(runSemanticSearch, 450);
  }

  function renderChips() {
    const categories = [...new Set(products.map(p => p.category).filter(Boolean))].sort();
    categories.forEach(cat => {
      const btn = document.createElement("button");
      btn.className = "chip";
      btn.dataset.category = cat;
      btn.textContent = cat;
      chips.appendChild(btn);
    });
    chips.addEventListener("click", (e) => {
      const btn = e.target.closest(".chip");
      if (!btn) return;
      activeCategory = btn.dataset.category;
      chips.querySelectorAll(".chip").forEach(c => c.classList.toggle("active", c === btn));
      render();
    });
  }

  // "You are here" bar: set by the Entrance QR, by scanning a shelf tag, or by hand
  const whereText = document.getElementById("where-text");
  const whereSub = document.getElementById("where-sub");
  const whereSelect = document.getElementById("where-select");
  const whereBar = document.getElementById("where-bar");
  function renderWhere() {
    const w = Omni.where.get();
    const scanned = Omni.where.justScanned();
    whereSelect.value = Omni.where.checkpoint();
    whereBar.classList.toggle("just-scanned", !!scanned);
    if (scanned === "master") {
      whereText.textContent = "Welcome to ShopMart! You're at the Entrance.";
      whereSub.textContent = "Search for what you want below. Every result shows how far it is from here, and its page gives step-by-step directions.";
    } else if (scanned === "product") {
      whereText.textContent = `You're near ${w.note || "this product"} (${w.label}).`;
      whereSub.textContent = "Search for the next item: directions will start from here.";
    } else if (w) {
      whereText.textContent = `You're at ${w.label}.`;
      whereSub.textContent = "Directions start from here. Scan the Entrance code or a shelf tag to update.";
    } else {
      whereText.textContent = "Where are you in the store?";
      whereSub.textContent = "Scan the Entrance code or a shelf tag, or pick your spot. Until then directions start at the Entrance.";
    }
    if (products.length) render();
  }
  whereSelect.addEventListener("change", () => { Omni.where.set(whereSelect.value, "manual"); });
  document.addEventListener("shopmart:where", renderWhere);

  searchForm.addEventListener("submit", (e) => { e.preventDefault(); clearTimeout(searchTimer); runSemanticSearch(); });
  searchInput.addEventListener("input", onSearchInput);

  (async () => {
    const res = await Omni.api("/api/products");
    if (!res.ok) {
      grid.innerHTML = "";
      emptyState.classList.remove("hidden");
      emptyState.querySelector("h2").textContent = "Store is offline";
      emptyState.querySelector("p").textContent = "Couldn't load products. Please try again in a moment.";
      return;
    }
    products = res.body.products || [];
    renderChips();
    renderWhere();
    render();
    if (isSemanticQuery(searchInput.value.trim())) runSemanticSearch();
  })();

  // Store-wide assistant (no current product; the backend uses its tools to look things up)
  const assistantPersona = document.getElementById("persona");
  try { assistantPersona.value = localStorage.getItem("omnitag_persona") || "General Buyer"; } catch (e) { /* storage blocked */ }
  assistantPersona.addEventListener("change", () => {
    try { localStorage.setItem("omnitag_persona", assistantPersona.value); } catch (e) { /* storage blocked */ }
  });
  OmniChat.create({
    log: document.getElementById("chat-log"), form: document.getElementById("chat-form"),
    input: document.getElementById("chat-input"), send: document.getElementById("chat-send"),
    suggestions: document.getElementById("suggestions"),
    getPayload: () => ({ persona: assistantPersona.value, location: Omni.where.checkpoint() }),
    welcome: "Hi! I can find products, compare prices, check store policies and give you directions inside the store."
  });
})();
