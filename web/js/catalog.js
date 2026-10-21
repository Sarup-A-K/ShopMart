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
          ${loc.aisle ? `<span class="aisle">📍 ${escapeHtml(loc.aisle)} · ${escapeHtml(loc.section || "")}</span>` : ""}
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
    render();
    if (isSemanticQuery(searchInput.value.trim())) runSemanticSearch();
  })();
})();
