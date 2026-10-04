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

  function render() {
    const q = searchInput.value.trim().toLowerCase();
    const filtered = products.filter(p =>
      (!activeCategory || p.category === activeCategory) &&
      (!q || `${p.name} ${p.brand} ${p.category}`.toLowerCase().includes(q))
    );
    grid.innerHTML = filtered.map(cardHtml).join("");
    emptyState.classList.toggle("hidden", filtered.length > 0);
    resultsTitle.textContent = q ? `Results for "${searchInput.value.trim()}"` : (activeCategory || "All products");
    resultsCount.textContent = `${filtered.length} item${filtered.length === 1 ? "" : "s"}`;
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

  searchForm.addEventListener("submit", (e) => { e.preventDefault(); render(); });
  searchInput.addEventListener("input", render);

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
  })();
})();
