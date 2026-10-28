/**
 * Shared helpers for the ShopMart pages: API calls, formatting,
 * QR link parsing and the "Scan a price tag" modal in the header.
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
      const code = codeFromQR(data);
      if (!code) return;
      handled = true;
      msg.textContent = `Found ${code}, opening…`;
      window.qrEngine.stopCamera();
      window.location.href = productUrl(code);
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
      msg.textContent = "Point your camera at the QR code on the price tag.";
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
      const code = codeFromQR(document.getElementById("manual-code").value);
      if (code) window.location.href = productUrl(code);
    });
  }

  document.addEventListener("DOMContentLoaded", initScanner);

  return { api, escapeHtml, inr, priceHtml, discountPercent, productUrl, codeFromQR, imageFallback };
})();
