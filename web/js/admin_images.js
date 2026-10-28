/**
 * Admin: set the real photo of each product (upload a file or paste a link).
 * Uses helpers exposed by admin.js (window.OmniAdmin).
 */
(() => {
  const $ = (id) => document.getElementById(id);
  const { api, setStatus: setStatusOn, errorText } = window.OmniAdmin;
  const statusEl = $("photo-status");
  const setStatus = (text, kind) => setStatusOn(statusEl, text, kind);
  const { escapeHtml } = Omni;
  const grid = $("photo-grid");
  let loaded = false;

  async function load() {
    const res = await fetch("/api/products");
    const products = (await res.json()).products || [];
    grid.innerHTML = products.map(p => `
      <div class="photo-card" data-qr="${escapeHtml(p.qrCode)}">
        <img src="${escapeHtml(p.image || "")}" alt="" onerror="Omni.imageFallback(this)">
        <div class="photo-name">${escapeHtml(p.qrCode)} · ${escapeHtml(p.name)}</div>
        <div class="small muted">${p.imageCustom ? "✓ Your photo" : "Illustrative image"}</div>
        <div class="row">
          <label class="btn" style="cursor:pointer;">Upload photo<input type="file" accept="image/jpeg,image/png,image/webp" hidden data-act="file"></label>
          ${p.imageCustom ? '<button class="btn" data-act="reset">Reset</button>' : ""}
        </div>
        <div class="row">
          <input class="input" placeholder="Paste image link" data-act="url">
          <button class="btn" data-act="link">Use link</button>
        </div>
      </div>`).join("");
    loaded = true;
  }

  async function done(res, okText) {
    if (res.ok) { setStatus(okText, "ok"); await load(); return; }
    const body = await res.json().catch(() => ({}));
    setStatus(errorText(body, "Could not save the photo."), "err");
  }

  grid.addEventListener("change", async (e) => {
    if (e.target.dataset.act !== "file" || !e.target.files.length) return;
    const qr = e.target.closest(".photo-card").dataset.qr;
    const form = new FormData();
    form.append("file", e.target.files[0]);
    setStatus("Uploading photo…", "info");
    await done(await api(`/api/admin/products/${encodeURIComponent(qr)}/image`, { method: "POST", body: form }), "Photo saved.");
  });

  grid.addEventListener("click", async (e) => {
    const act = e.target.dataset.act;
    const card = e.target.closest(".photo-card");
    if (!card || (act !== "link" && act !== "reset")) return;
    const path = `/api/admin/products/${encodeURIComponent(card.dataset.qr)}/image`;
    if (act === "reset") return done(await api(path, { method: "DELETE" }), "Photo reset.");
    const url = card.querySelector('[data-act="url"]').value.trim();
    if (!url) return setStatus("Paste an image link first.", "err");
    done(await api(path, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url }) }), "Photo saved.");
  });

  document.addEventListener("admin:tab", (e) => { if (e.detail === "images-panel" && !loaded) load(); });
})();
