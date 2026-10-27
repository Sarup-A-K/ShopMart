/**
 * OmniTag Admin: log in, edit prices in a table or via Excel, and print QR price tags.
 */
(() => {
  const API = ""; // same origin: the backend serves this page
  const PRICE_FIELDS = ["price", "mrp", "amazon_price", "flipkart_price", "croma_price"];
  const COMPETITOR_FIELDS = ["amazon_price", "flipkart_price", "croma_price"];
  const PRICE_MATCH_DISCOUNT = 0.05; // keep in sync with store_db.PRICE_MATCH_DISCOUNT

  const $ = (id) => document.getElementById(id);
  const loginView = $("login-view");
  const managerView = $("manager-view");
  const loginStatus = $("login-status");
  const managerStatus = $("manager-status");
  const tbody = $("price-rows");
  const btnSave = $("btn-save");
  const btnLogout = $("btn-logout");
  const dirtyCount = $("dirty-count");
  const inputFile = $("input-file");

  let token = null;
  try { token = sessionStorage.getItem("omnitag_admin_token"); } catch (e) { /* storage blocked */ }

  function setToken(value) {
    token = value;
    try {
      if (value) sessionStorage.setItem("omnitag_admin_token", value);
      else sessionStorage.removeItem("omnitag_admin_token");
    } catch (e) { /* storage blocked */ }
  }

  function setStatus(el, text, kind) {
    el.textContent = text || "";
    el.className = `status ${kind || ""}`;
  }

  async function api(path, options = {}) {
    const res = await fetch(`${API}${path}`, {
      ...options,
      headers: { ...(options.headers || {}), Authorization: `Bearer ${token}` }
    });
    if (res.status === 401) {
      showLogin("Your session has expired. Please log in again.");
      throw new Error("unauthorized");
    }
    return res;
  }

  function errorText(body, fallback) {
    const detail = body && body.detail;
    if (!detail) return fallback;
    if (typeof detail === "string") return detail;
    if (detail.errors) return `${detail.message}\n• ${detail.errors.join("\n• ")}`;
    if (Array.isArray(detail)) return detail.map(d => d.msg).join("; ");
    return fallback;
  }

  // ---- Views ----
  function showLogin(message) {
    setToken(null);
    managerView.classList.add("hidden");
    btnLogout.classList.add("hidden");
    loginView.classList.remove("hidden");
    setStatus(loginStatus, message || "", "err");
    $("input-password").focus();
  }

  async function showManager() {
    loginView.classList.add("hidden");
    managerView.classList.remove("hidden");
    btnLogout.classList.remove("hidden");
    await loadRows();
  }

  // ---- Login ----
  $("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    setStatus(loginStatus, "");
    try {
      const res = await fetch(`${API}/api/admin/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: $("input-password").value })
      });
      const body = await res.json();
      if (!res.ok) {
        setStatus(loginStatus, errorText(body, "Login failed."), "err");
        return;
      }
      setToken(body.token);
      $("input-password").value = "";
      await showManager();
    } catch (err) {
      setStatus(loginStatus, "Could not reach the store server.", "err");
    }
  });

  btnLogout.addEventListener("click", async () => {
    if (hasUnsaved() && !confirm("You have unsaved changes. Log out anyway?")) return;
    try { await api("/api/admin/logout", { method: "POST" }); } catch (e) { /* already logged out */ }
    showLogin();
  });

  // ---- Table ----
  const fmt = (n) => `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;

  function parsePrice(text) {
    const t = text.replace(/[₹,\s]/g, "");
    if (t === "") return { value: null, ok: true };
    const n = Number(t);
    return { value: n, ok: Number.isFinite(n) && n > 0 };
  }

  // Same rule as the backend: ~5% under the cheapest online price, never above the store price
  function shownPrice(values) {
    const comps = COMPETITOR_FIELDS.map(f => values[f]).filter(v => v != null);
    if (values.price == null) return null;
    if (!comps.length) return { price: values.price, matched: false };
    const target = Math.floor(Math.min(...comps) * (1 - PRICE_MATCH_DISCOUNT));
    return target > 0 && target < values.price ? { price: target, matched: true } : { price: values.price, matched: false };
  }

  function rowValues(tr) {
    const values = {};
    let valid = true;
    tr.querySelectorAll("input[data-field]").forEach(input => {
      const { value, ok } = parsePrice(input.value);
      const required = input.dataset.field === "price";
      const fieldOk = ok && !(required && value == null);
      input.classList.toggle("invalid", !fieldOk);
      valid = valid && fieldOk;
      values[input.dataset.field] = value;
    });
    return { values, valid };
  }

  function refreshRow(tr) {
    tr.querySelectorAll("input[data-field]").forEach(input => {
      input.classList.toggle("dirty", input.value.trim() !== input.dataset.original);
    });
    const { values, valid } = rowValues(tr);
    const cell = tr.querySelector(".effective");
    const shown = valid ? shownPrice(values) : null;
    cell.textContent = shown ? `${fmt(shown.price)}${shown.matched ? " (matched)" : ""}` : "—";
    updateDirtyState();
  }

  function dirtyRows() {
    return [...tbody.querySelectorAll("tr")].filter(tr => tr.querySelector("input.dirty"));
  }

  function hasUnsaved() {
    return dirtyRows().length > 0;
  }

  function updateDirtyState() {
    const n = dirtyRows().length;
    btnSave.disabled = n === 0;
    dirtyCount.textContent = n ? `${n} product${n > 1 ? "s" : ""} with unsaved changes` : "";
  }

  function renderRows(rows) {
    tbody.innerHTML = "";
    rows.forEach(row => {
      const tr = document.createElement("tr");
      tr.dataset.qr = row.qr_code;

      const addCell = (text, className) => {
        const td = document.createElement("td");
        if (className) td.className = className;
        td.textContent = text;
        tr.appendChild(td);
        return td;
      };

      addCell(row.qr_code);
      addCell(`${row.name}${row.brand ? ` (${row.brand})` : ""}`, "name");
      PRICE_FIELDS.forEach(field => {
        const td = document.createElement("td");
        const input = document.createElement("input");
        input.type = "text";
        input.inputMode = "decimal";
        input.dataset.field = field;
        input.value = row[field] == null ? "" : String(row[field]);
        input.dataset.original = input.value;
        input.placeholder = field === "price" ? "required" : "—";
        input.setAttribute("aria-label", `${row.qr_code} ${field.replace("_", " ")}`);
        input.addEventListener("input", () => refreshRow(tr));
        td.appendChild(input);
        tr.appendChild(td);
      });
      addCell("", "effective");
      addCell(row.updated_at ? new Date(row.updated_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : "");
      tbody.appendChild(tr);
      refreshRow(tr);
    });
  }

  async function loadRows() {
    try {
      const res = await api("/api/admin/prices");
      const body = await res.json();
      renderRows(body.rows || []);
      renderTags();
    } catch (e) {
      if (e.message !== "unauthorized") setStatus(managerStatus, "Could not load prices from the server.", "err");
    }
  }

  // ---- Save edits ----
  btnSave.addEventListener("click", async () => {
    const rows = dirtyRows();
    const invalid = rows.filter(tr => !rowValues(tr).valid);
    if (invalid.length) {
      setStatus(managerStatus, `Fix the highlighted prices for: ${invalid.map(tr => tr.dataset.qr).join(", ")}. Store price is required and prices must be positive numbers.`, "err");
      return;
    }
    btnSave.disabled = true;
    setStatus(managerStatus, "Saving…");
    const failures = [];
    for (const tr of rows) {
      try {
        const res = await api(`/api/admin/prices/${encodeURIComponent(tr.dataset.qr)}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(rowValues(tr).values)
        });
        if (!res.ok) failures.push(`${tr.dataset.qr}: ${errorText(await res.json(), "save failed")}`);
      } catch (e) {
        if (e.message === "unauthorized") return;
        failures.push(`${tr.dataset.qr}: server not reachable`);
      }
    }
    await loadRows();
    if (failures.length) {
      setStatus(managerStatus, `Some prices were not saved:\n• ${failures.join("\n• ")}`, "err");
    } else {
      setStatus(managerStatus, `Saved ${rows.length} product${rows.length > 1 ? "s" : ""}. Shoppers will see the new prices on their next scan.`, "ok");
    }
  });

  // ---- Excel ----
  $("btn-download").addEventListener("click", async () => {
    if (hasUnsaved()) setStatus(managerStatus, "Note: the download contains saved prices only — save your table edits first if you want them included.", "");
    try {
      const res = await api("/api/admin/prices.xlsx");
      if (!res.ok) throw new Error("download failed");
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `omnitag_prices_${new Date().toISOString().slice(0, 10)}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    } catch (e) {
      if (e.message !== "unauthorized") setStatus(managerStatus, "Could not download the Excel file.", "err");
    }
  });

  $("btn-upload").addEventListener("click", () => {
    if (hasUnsaved() && !confirm("Uploading will reload the table and discard your unsaved edits. Continue?")) return;
    inputFile.value = "";
    inputFile.click();
  });

  inputFile.addEventListener("change", async () => {
    const file = inputFile.files[0];
    if (!file) return;
    setStatus(managerStatus, `Uploading ${file.name}…`);
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await api("/api/admin/prices/import", { method: "POST", body: form });
      const body = await res.json();
      if (!res.ok) {
        setStatus(managerStatus, errorText(body, "Upload failed."), "err");
        return;
      }
      await loadRows();
      if (body.updated === 0) {
        setStatus(managerStatus, `No price changes found in ${file.name}.`, "ok");
        return;
      }
      const labels = { price: "Store", mrp: "MRP", amazon_price: "Amazon", flipkart_price: "Flipkart", croma_price: "Croma" };
      const lines = body.changes.map(c =>
        `${c.qr_code}: ` + Object.entries(c.changes)
          .map(([f, v]) => `${labels[f]} ${v.from == null ? "—" : fmt(v.from)} → ${v.to == null ? "—" : fmt(v.to)}`)
          .join(", ")
      );
      setStatus(managerStatus, `Updated ${body.updated} product${body.updated > 1 ? "s" : ""} from ${file.name}:\n• ${lines.join("\n• ")}`, "ok");
    } catch (e) {
      if (e.message !== "unauthorized") setStatus(managerStatus, "Upload failed: server not reachable.", "err");
    }
  });

  window.addEventListener("beforeunload", (e) => {
    if (hasUnsaved()) { e.preventDefault(); e.returnValue = ""; }
  });

  // ---- Tabs ----
  document.querySelectorAll(".tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t === tab));
      ["prices-panel", "tags-panel", "content-panel", "insights-panel"].forEach(id => $(id).classList.toggle("hidden", id !== tab.dataset.tab));
      document.dispatchEvent(new CustomEvent("admin:tab", { detail: tab.dataset.tab }));
    });
  });

  // ---- QR price tags ----
  const baseUrlInput = $("input-base-url");
  const tagSheet = $("tag-sheet");
  const urlWarning = $("url-warning");

  function normalisedBaseUrl() {
    return baseUrlInput.value.trim().replace(/\/+$/, "");
  }

  function checkBaseUrl(base) {
    let message = "";
    try {
      const host = new URL(base).hostname;
      if (host === "localhost" || host === "127.0.0.1") {
        message = "Phones can't open \"localhost\". Start the store with ./start.sh (it detects this laptop's network address), or type the laptop's address, e.g. http://192.168.43.10:8000.";
      }
    } catch (e) {
      message = "Enter a full address starting with http:// or https://";
    }
    urlWarning.textContent = message;
    urlWarning.classList.toggle("hidden", !message);
    return !message || message.startsWith("Phones");
  }

  async function renderTags() {
    const base = normalisedBaseUrl();
    if (!checkBaseUrl(base)) { tagSheet.innerHTML = ""; return; }
    let products = [];
    try {
      products = (await (await fetch(`${API}/api/products`)).json()).products || [];
    } catch (e) {
      tagSheet.textContent = "Could not load products.";
      return;
    }
    await noteAddressChange(base);
    tagSheet.innerHTML = "";
    products.forEach(p => {
      const url = `${base}/p/${encodeURIComponent(p.qrCode)}`;
      const tag = document.createElement("div");
      tag.className = "price-tag";
      const loc = p.location || {};
      tag.innerHTML = `
        <div>
          <div class="t-brand">${Omni.escapeHtml(p.brand)}</div>
          <div class="t-name">${Omni.escapeHtml(p.name)}</div>
          <div class="t-price">₹${Omni.inr(p.price)}</div>
          ${p.originalPrice && p.originalPrice > p.price ? `<div class="t-mrp">M.R.P. <s>₹${Omni.inr(p.originalPrice)}</s></div>` : ""}
          ${loc.aisle ? `<div class="t-aisle">${Omni.escapeHtml(loc.aisle)} · ${Omni.escapeHtml(loc.section || "")}</div>` : ""}
        </div>
        <div class="t-qr">
          <div class="qr"></div>
          <div class="t-hint">Scan to compare online prices &amp; ask AI</div>
        </div>`;
      tagSheet.appendChild(tag);
      if (window.QRCode) {
        new window.QRCode(tag.querySelector(".qr"), { text: url, width: 192, height: 192, correctLevel: window.QRCode.CorrectLevel.M });
      }
      tag.title = url;
    });
  }

  $("btn-apply-url").addEventListener("click", renderTags);
  $("btn-print").addEventListener("click", () => window.print());

  // Which address should the tags point to? The one this admin page was opened from, if phones can reach
  // it (the laptop's network address or a tunnel address). From "localhost", use the address start.sh detected.
    const isLocalHost = (h) => h === "localhost" || h === "127.0.0.1" || h === "::1" || h === "[::1]";

  async function initBaseUrl() {
    let configured = "";
    try { configured = (await (await fetch(`${API}/api/config`)).json()).public_url || ""; } catch (e) { /* offline */ }
    baseUrlInput.value = isLocalHost(window.location.hostname) ? (configured || window.location.origin) : window.location.origin;
  }

  // Tags printed for an address that no longer exists will not open. Remind the admin when the address changed.
  let storedBase = null;                     // the address the tags were last made for, kept by the server
  let staleFrom = "";                        // the older address that earlier tags may still point to

  async function noteAddressChange(base) {
    const note = $("url-changed");
    let host = "";
    try { host = new URL(base).hostname; } catch (e) { /* invalid address, already warned about */ }
    if (!host || isLocalHost(host)) { note.classList.add("hidden"); return; }   // "localhost" tags are not usable anyway
    if (storedBase === null) {               // first render after login: ask the server once
      try { storedBase = (await (await api("/api/admin/tag-base")).json()).base || ""; } catch (e) { storedBase = ""; }
      if (storedBase && storedBase !== base) staleFrom = storedBase;
    }
    const show = staleFrom && staleFrom !== base;
    note.textContent = show ? `The address changed since you last made tags (it was ${staleFrom}). Tags made earlier will not open on phones; use the new tags below.` : "";
    note.classList.toggle("hidden", !show);
    if (storedBase !== base) {
      storedBase = base;
      try { await api("/api/admin/tag-base", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ base }) }); } catch (e) { /* not critical */ }
    }
  }

  window.OmniAdmin = { api, setStatus, errorText, fmt };

  // ---- Start ----
  initBaseUrl().then(() => { if (token) showManager(); else showLogin(); });
})();
