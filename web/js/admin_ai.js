/**
 * Admin: AI-assisted content (review summaries, descriptions) and shopper insights.
 * Uses helpers exposed by admin.js (window.OmniAdmin).
 */
(() => {
  const $ = (id) => document.getElementById(id);
  const { api, setStatus, errorText } = window.OmniAdmin;
  const { escapeHtml } = Omni;

  let products = [];

  const select = $("content-product");
  const status = $("content-status");
  const current = () => products.find(p => p.qrCode === select.value);

  async function postJson(path, body) {
    const res = await api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
    return { ok: res.ok, body: await res.json().catch(() => ({})) };
  }

  function showWarnings(el, warnings) {
    el.classList.toggle("hidden", !warnings.length);
    el.innerHTML = warnings.length
      ? "⚠ Check before publishing:<br>• " + warnings.map(escapeHtml).join("<br>• ")
      : "";
  }

  // ---------- AI content ----------
  async function loadProducts() {
    const res = await fetch("/api/products");
    products = (await res.json()).products || [];
    const keep = select.value;
    select.innerHTML = products.map(p => `<option value="${escapeHtml(p.qrCode)}">${escapeHtml(p.qrCode)} · ${escapeHtml(p.name.slice(0, 50))}</option>`).join("");
    if (keep) select.value = keep;
    renderCurrent();
  }

  function renderCurrent() {
    const p = current();
    if (!p) return;
    const s = p.aiSummary;
    $("summary-current").textContent = s && s.summary
      ? `Published: ${s.summary}`
      : `No AI summary published. This product has ${(p.reviews || []).length} review(s).`;
    $("btn-clear-summary").classList.toggle("hidden", !(s && s.summary));
    $("description-current").textContent = `Current: ${p.description || "(none)"}`;
    $("summary-preview").classList.add("hidden");
    $("description-preview").classList.add("hidden");
    setStatus(status, "");
  }

  async function generate(path, button, label) {
    setStatus(status, `${label}… (the local model can take up to a minute the first time)`);
    button.disabled = true;
    try {
      const { ok, body } = await postJson(path);
      if (!ok) { setStatus(status, errorText(body, "The AI could not produce a draft."), "err"); return null; }
      setStatus(status, "");
      return body;
    } catch (e) {
      if (e.message !== "unauthorized") setStatus(status, "Could not reach the server.", "err");
      return null;
    } finally {
      button.disabled = false;
    }
  }

  $("btn-gen-summary").addEventListener("click", async () => {
    const p = current();
    const body = await generate(`/api/admin/ai/review-summary/${encodeURIComponent(p.qrCode)}`, $("btn-gen-summary"), "Summarising reviews");
    if (!body) return;
    $("summary-text").value = body.draft.summary;
    $("summary-lists").innerHTML =
      (body.draft.pros.length ? `<strong>Pros:</strong> ${body.draft.pros.map(escapeHtml).join(" · ")}<br>` : "") +
      (body.draft.cons.length ? `<strong>Cons:</strong> ${body.draft.cons.map(escapeHtml).join(" · ")}` : "<strong>Cons:</strong> none mentioned");
    $("summary-preview").dataset.pros = JSON.stringify(body.draft.pros);
    $("summary-preview").dataset.cons = JSON.stringify(body.draft.cons);
    showWarnings($("summary-warnings"), body.warnings || []);
    $("summary-preview").classList.remove("hidden");
  });

  $("btn-save-summary").addEventListener("click", async () => {
    const p = current();
    const box = $("summary-preview");
    const { ok, body } = await postJson(`/api/admin/products/${encodeURIComponent(p.qrCode)}/content`, {
      ai_summary: { summary: $("summary-text").value, pros: JSON.parse(box.dataset.pros || "[]"), cons: JSON.parse(box.dataset.cons || "[]") }
    });
    if (!ok) return setStatus(status, errorText(body, "Could not save."), "err");
    await loadProducts();
    setStatus(status, "Summary published. It now shows above the reviews on the product page.", "ok");
  });

  $("btn-clear-summary").addEventListener("click", async () => {
    const { ok, body } = await postJson(`/api/admin/products/${encodeURIComponent(current().qrCode)}/content`, { clear_summary: true });
    if (!ok) return setStatus(status, errorText(body, "Could not remove."), "err");
    await loadProducts();
    setStatus(status, "Summary removed.", "ok");
  });

  $("btn-gen-description").addEventListener("click", async () => {
    const p = current();
    const body = await generate(`/api/admin/ai/description/${encodeURIComponent(p.qrCode)}`, $("btn-gen-description"), "Drafting description");
    if (!body) return;
    $("description-text").value = body.draft.description;
    showWarnings($("description-warnings"), body.warnings || []);
    $("description-preview").classList.remove("hidden");
  });

  $("btn-save-description").addEventListener("click", async () => {
    const p = current();
    const { ok, body } = await postJson(`/api/admin/products/${encodeURIComponent(p.qrCode)}/content`, { description: $("description-text").value });
    if (!ok) return setStatus(status, errorText(body, "Could not save."), "err");
    await loadProducts();
    setStatus(status, "Description updated.", "ok");
  });

  select.addEventListener("change", renderCurrent);

  // ---------- Shopper insights ----------
  const iStatus = $("insights-status");

  async function loadInsights() {
    let res;
    try { res = await api("/api/admin/insights"); } catch (e) { return; }
    const d = await res.json();
    const tile = (n, label) => `<div class="stat"><b>${n}</b><span>${label}</span></div>`;
    $("stat-grid").innerHTML =
      tile(d.total_questions, "questions asked") +
      tile(d.blocked_total, "blocked by guardrails") +
      tile(d.corrected, "answers corrected by fact-check") +
      tile(d.fallback, "answered by search fallback") +
      tile(d.avg_latency_ms != null ? (d.avg_latency_ms / 1000).toFixed(1) + " s" : "n/a", "average answer time");
    $("top-products").innerHTML = d.top_products.length
      ? d.top_products.map(p => `<li>${escapeHtml(p.name.slice(0, 48))} <span class="when">${p.questions} question(s)</span></li>`).join("")
      : "<li class='muted'>No product-page questions yet.</li>";
    const tools = Object.entries(d.tools);
    $("tool-usage").innerHTML = tools.length
      ? tools.sort((a, b) => b[1] - a[1]).map(([t, n]) => `<li>${escapeHtml(t)} <span class="when">${n}×</span></li>`).join("")
      : "<li class='muted'>No tool calls yet.</li>";
    $("recent-questions").innerHTML = d.recent_questions.length
      ? d.recent_questions.map(q =>
          `<li>${escapeHtml(q.question)}<span class="when">${q.product ? escapeHtml(q.product.slice(0, 30)) : "store assistant"}${q.blocked ? " · blocked: " + escapeHtml(q.blocked) : ""}</span></li>`).join("")
      : "<li class='muted'>No questions yet.</li>";
  }

  $("btn-refresh-insights").addEventListener("click", loadInsights);

  $("btn-clear-log").addEventListener("click", async () => {
    if (!confirm("Delete all logged shopper questions?")) return;
    const res = await api("/api/admin/insights/log", { method: "DELETE" });
    if (res.ok) { $("report-box").classList.add("hidden"); await loadInsights(); setStatus(iStatus, "Log cleared.", "ok"); }
  });

  $("btn-gen-report").addEventListener("click", async () => {
    const btn = $("btn-gen-report");
    btn.disabled = true;
    setStatus(iStatus, "Writing the report…");
    try {
      const { ok, body } = await postJson("/api/admin/insights/report");
      const box = $("report-box");
      if (!ok) { setStatus(iStatus, errorText(body, "Could not write the report."), "err"); return; }
      setStatus(iStatus, "");
      box.innerHTML =
        `<div class="small muted">Based on ${body.based_on} recent questions. AI-written; check it against the list below.</div>` +
        `<strong>What shoppers ask about</strong><ul class="report-list">${body.themes.map(t => `<li>${escapeHtml(t)}</li>`).join("")}</ul>` +
        `<strong>Suggested actions</strong><ul class="report-list">${body.suggestions.map(t => `<li>${escapeHtml(t)}</li>`).join("")}</ul>`;
      box.classList.remove("hidden");
    } catch (e) {
      if (e.message !== "unauthorized") setStatus(iStatus, "Could not reach the server.", "err");
    } finally {
      btn.disabled = false;
    }
  });

  // Load each tab's data when it is opened
  document.addEventListener("admin:tab", (e) => {
    if (e.detail === "content-panel") loadProducts();
    if (e.detail === "insights-panel") loadInsights();
  });
})();
