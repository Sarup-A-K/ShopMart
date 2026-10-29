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
    document.title = "Tag not found | ShopMart";
  }

  // ---------- Header, price and comparison ----------
  function renderHead(p) {
    document.title = `${p.name} | ShopMart`;
    $("crumb-category").textContent = p.category || "Products";
    $("crumb-brand").textContent = p.brand || "";
    $("p-image").onerror = () => Omni.imageFallback($("p-image"));
    $("p-image").src = p.image;
    $("p-image").alt = p.name;
    $("p-image-note").classList.toggle("hidden", !!p.imageCustom);
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
    const rows = [`<tr class="ours"><td>ShopMart (this store)</td><td>₹${inr(p.price)}</td></tr>`];
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

    const sum = p.aiSummary;
    if (sum && sum.summary) {
      const list = (label, items) => items && items.length ? `<div><strong>${label}:</strong> ${items.map(escapeHtml).join(" · ")}</div>` : "";
      $("ai-summary").innerHTML = `<div class="ai-summary-tag">✨ AI summary of the reviews below</div>${escapeHtml(sum.summary)}${list("Pros", sum.pros)}${list("Cons", sum.cons)}`;
      $("ai-summary").classList.remove("hidden");
    }
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
    // A scanned shelf tag (link ends in ?scan=1) tells us the shopper is at this product's aisle
    const params = new URLSearchParams(window.location.search);
    if (params.get("scan")) {
      Omni.where.set(loc.aisle || "entrance", "product", product.name);
      params.delete("scan");
      const rest = params.toString();
      try { history.replaceState(null, "", window.location.pathname + (rest ? `?${rest}` : "")); } catch (e) { /* ignore */ }
    }
    const nearSelect = $("w-near");
    nearSelect.value = Omni.where.checkpoint();
    function showWhereNote() {
      const w = Omni.where.get();
      $("w-where-note").textContent = !w ? "Not scanned yet: scan the Entrance QR or a shelf tag, or pick where you are."
        : w.source === "master" ? "You scanned the Entrance code, so directions start at the Entrance."
        : w.source === "product" ? `You scanned the tag of ${w.note}, so directions start from ${w.label}.`
        : `Directions start from the place you picked (${w.label}).`;
    }
    nearSelect.addEventListener("change", () => { Omni.where.set(nearSelect.value, "manual"); showWhereNote(); });
    showWhereNote();
    Wayfinding.init({ product, canvas: $("w-map"), select: nearSelect, stepsEl: $("w-steps"), summaryEl: $("w-summary") });

    OmniChat.create({
      log: $("chat-log"), form: $("chat-form"), input: $("chat-input"), send: $("chat-send"), suggestions: $("suggestions"),
      getPayload: () => ({ qr_code: product.qrCode, product_name: product.name, persona: personaSelect.value, location: Omni.where.checkpoint() }),
      welcome: `Hi! Ask me anything about the ${product.brand} ${product.category ? product.category.toLowerCase() : "product"}: price, specs, how it compares with other items, or where to find it.`
    });
    loadInsight();
  })();
})();
