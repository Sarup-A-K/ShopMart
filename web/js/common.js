/**
 * Shared helpers for the ShopMart pages: API calls, formatting,
 * QR link parsing and the "Scan a QR tag" modal in the header.
 */
const Omni = (() => {
  async function api(path, options = {}) {
    const res = await fetch(path, options);
    let body = null;
    try { body = await res.json(); } catch (e) { /* non-JSON response */ }
    return { ok: res.ok, status: res.status, body };
  }

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
  }

  const inr = (n) => Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });

  function priceHtml(amount) {
    return `<span class="price"><span class="sym">₹</span>${inr(amount)}</span>`;
  }

  function discountPercent(product) {
    const mrp = product.originalPrice;
    return mrp && mrp > product.price ? Math.round(((mrp - product.price) / mrp) * 100) : 0;
  }

  // Shown when a product photo link is broken
  const PLACEHOLDER_IMG = "data:image/svg+xml," + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200"><rect width="200" height="200" fill="#eef1f4"/>' +
    '<path d="M60 135l30-38 22 27 15-18 23 29z" fill="#c3cbd4"/><circle cx="128" cy="72" r="12" fill="#c3cbd4"/>' +
    '<text x="100" y="168" font-family="sans-serif" font-size="13" fill="#7b8794" text-anchor="middle">Photo coming soon</text></svg>');

  function imageFallback(img) {
    img.onerror = null;
    img.src = PLACEHOLDER_IMG;
  }

  function productUrl(qrCode) {
    return `/p/${encodeURIComponent(qrCode)}`;
  }

  // ---- Where the shopper is ----
  // The Entrance (master) QR sets it to the Entrance; a shelf tag sets it to that product's aisle (the product page does this
  // when the tag's link carries ?scan=1); the shopper can also pick it by hand. Directions everywhere start from it.
  const WHERE_KEY = "shopmart_where";
  const WHERE_TTL_MS = 4 * 60 * 60 * 1000;
  let memoryWhere = null;                     // used when browser storage is blocked

  function readWhere() {
    let value = memoryWhere;
    try { const raw = localStorage.getItem(WHERE_KEY); if (raw) value = JSON.parse(raw); } catch (e) { /* storage blocked */ }
    return value && Date.now() - value.at < WHERE_TTL_MS ? value : null;
  }

  function setWhere(checkpoint, source, note) {
    const n = parseInt(String(checkpoint).replace(/\D/g, ""), 10);
    const cp = n >= 1 && n <= 6 ? `aisle-${n}` : "entrance";
    const value = { checkpoint: cp, label: cp === "entrance" ? "Entrance" : `Aisle ${n}`, source, note: note || "", at: Date.now() };
    memoryWhere = value;
    try { localStorage.setItem(WHERE_KEY, JSON.stringify(value)); } catch (e) { /* storage blocked */ }
    document.dispatchEvent(new CustomEvent("shopmart:where", { detail: value }));
    return value;
  }

  const where = {
    get: readWhere,
    set: setWhere,
    checkpoint: () => (readWhere() || {}).checkpoint || "entrance",
    /** "master" or "product" if the shopper scanned a tag in the last 30 seconds (used for the welcome line), else "". */
    justScanned: () => { const v = readWhere(); return v && v.source !== "manual" && Date.now() - v.at < 30000 ? v.source : ""; }
  };

  // The master QR opens "/?at=entrance"
  (function readEntranceLink() {
    const params = new URLSearchParams(window.location.search);
    if (params.get("at") !== "entrance") return;
    setWhere("entrance", "master");
    params.delete("at");
    const rest = params.toString();
    try { history.replaceState(null, "", window.location.pathname + (rest ? `?${rest}` : "") + window.location.hash); } catch (e) { /* ignore */ }
  })();

  /** Where to go for scanned or typed text: the home page for the master QR, otherwise the product page (marked as scanned). */
  function tagTarget(text) {
    const raw = String(text || "").trim();
    if (/^(master|entrance)$/i.test(raw)) return "/?at=entrance";
    try {
      const url = new URL(raw);
      if (url.searchParams.get("at") === "entrance" && !/\/p\//.test(url.pathname)) return "/?at=entrance";
    } catch (e) { /* not a URL */ }
    const code = codeFromQR(raw);
    return code ? `${productUrl(code)}?scan=1` : "";
  }

  /**
   * QR codes contain a product link like http://192.168.43.10:8000/p/item-1.
   * Older tags may contain just the code ("item-1"); both are accepted.
   */
  function codeFromQR(text) {
    const raw = String(text || "").trim();
    try {
      const url = new URL(raw);
      const match = url.pathname.match(/\/p\/([^/?#]+)/);
      if (match) return decodeURIComponent(match[1]);
      if (url.searchParams.get("qr")) return url.searchParams.get("qr");
    } catch (e) { /* not a URL */ }
    return raw;
  }

  // ---- Scanner modal (markup lives in each page) ----
  function initScanner() {
    const modal = document.getElementById("scan-modal");
    if (!modal) return;
    const video = document.getElementById("scan-video");
    const canvas = document.getElementById("scan-canvas");
    const msg = document.getElementById("scan-msg");
    const view = document.getElementById("scan-view");
    let handled = false;

    window.qrEngine.init(video, canvas, (data) => {
      if (handled) return;
      const target = tagTarget(data);
      if (!target) return;
      handled = true;
      msg.textContent = target.startsWith("/?at=") ? "Found the Entrance code, opening…" : `Found ${codeFromQR(data)}, opening…`;
      window.qrEngine.stopCamera();
      window.location.href = target;
    });

    async function open() {
      handled = false;
      modal.classList.remove("hidden");
      msg.className = "scan-msg";
      // Phones only allow the camera on https:// pages (or localhost)
      if (!window.isSecureContext || !navigator.mediaDevices) {
        view.classList.add("hidden");
        msg.className = "scan-msg warn";
        msg.innerHTML = "Your browser only allows the camera on secure (https) pages. <strong>Use your phone's camera app</strong> to scan the price tag; it opens the product page directly. Or type the tag code below.";
        return;
      }
      view.classList.remove("hidden");
      msg.textContent = "Point your camera at the QR code on the tag (a shelf tag, or the Entrance code).";
      const started = await window.qrEngine.startCamera();
      if (!started) {
        view.classList.add("hidden");
        msg.className = "scan-msg warn";
        msg.textContent = "Camera not available or permission denied. You can type the tag code below instead.";
      }
    }

    function close() {
      window.qrEngine.stopCamera();
      modal.classList.add("hidden");
    }

    document.querySelectorAll("[data-open-scanner]").forEach(btn => btn.addEventListener("click", open));
    document.getElementById("scan-close").addEventListener("click", close);
    modal.addEventListener("click", (e) => { if (e.target === modal) close(); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !modal.classList.contains("hidden")) close(); });

    document.getElementById("manual-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const target = tagTarget(document.getElementById("manual-code").value);
      if (target) window.location.href = target;
    });
  }

  document.addEventListener("DOMContentLoaded", initScanner);

  return { api, escapeHtml, inr, priceHtml, discountPercent, productUrl, codeFromQR, imageFallback, where, tagTarget };
})();
