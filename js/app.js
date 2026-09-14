/**
 * Main Application Orchestrator
 * Binds DOM events, camera controls, product DB queries, AR card updates, Grocery-AI Model recommendations, and modals.
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM Element References
  const btnToggleCamera = document.getElementById("btn-toggle-camera");
  const cameraBtnText = document.getElementById("camera-btn-text");
  const btnStartCameraHero = document.getElementById("btn-start-camera-hero");
  const cameraVideo = document.getElementById("camera-video");
  const qrCanvas = document.getElementById("qr-canvas");
  const cameraFallback = document.getElementById("camera-fallback");
  const arReticle = document.getElementById("ar-reticle");

  // AR Card & Content Tabs
  const arCard = document.getElementById("ar-card");
  const btnCloseAr = document.getElementById("btn-close-ar");
  const arProdImg = document.getElementById("ar-prod-img");
  const arProdBrand = document.getElementById("ar-prod-brand");
  const arProdTitle = document.getElementById("ar-prod-title");
  const arProdPrice = document.getElementById("ar-prod-price");
  const arProdOldPrice = document.getElementById("ar-prod-old-price");
  const arProdDiscount = document.getElementById("ar-prod-discount");
  const arProdUnit = document.getElementById("ar-prod-unit");
  const arProdStock = document.getElementById("ar-prod-stock");
  const arProdRating = document.getElementById("ar-prod-rating");
  const arProdHighlights = document.getElementById("ar-prod-highlights");
  
  // Front-and-Center AI Recommendations Banner
  const aiProviderBadgeMain = document.getElementById("ai-provider-badge-main");
  const aiRecContentMain = document.getElementById("ai-rec-content-main");

  const arSpecWarranty = document.getElementById("ar-spec-warranty");
  const arSpecQuality = document.getElementById("ar-spec-quality");
  const arMacrosGrid = document.getElementById("ar-macros-grid");
  const arReviewsContainer = document.getElementById("ar-reviews-container");
  const arAccessoriesContainer = document.getElementById("ar-accessories-container");
  const arWayfinderAisle = document.getElementById("ar-wayfinder-aisle");
  const arWayfinderText = document.getElementById("ar-wayfinder-text");
  const radarCanvas = document.getElementById("radar-canvas");

  // GenAI Elements
  const selectAiPersona = document.getElementById("select-ai-persona");
  const btnTriggerGenaiReport = document.getElementById("btn-trigger-genai-report");
  const aiReportOutput = document.getElementById("ai-report-output");
  const aiChatHistory = document.getElementById("ai-chat-history");
  const inputAiChat = document.getElementById("input-ai-chat");
  const btnSendAiChat = document.getElementById("btn-send-ai-chat");

  const modalGenaiConfig = document.getElementById("modal-genai-config");
  const btnGenaiConfig = document.getElementById("btn-genai-config");
  const btnCloseGenaiModal = document.getElementById("btn-close-genai-modal");
  
  const selectOsProvider = document.getElementById("select-os-provider");
  const inputPythonUrl = document.getElementById("input-python-url");
  const inputHfModel = document.getElementById("input-hf-model");
  const inputHfToken = document.getElementById("input-hf-token");
  const inputOllamaUrl = document.getElementById("input-ollama-url");
  const inputGroqKey = document.getElementById("input-groq-key");
  const osConfigPythonFields = document.getElementById("os-config-python-fields");
  const osConfigHfFields = document.getElementById("os-config-hf-fields");
  const osConfigOllamaFields = document.getElementById("os-config-ollama-fields");
  const osConfigGroqFields = document.getElementById("os-config-groq-fields");
  const btnSaveGenaiSettings = document.getElementById("btn-save-genai-settings");

  // Modals
  const modalStoreMap = document.getElementById("modal-store-map");
  const btnOpenMap = document.getElementById("btn-open-map");
  const btnCloseMapModal = document.getElementById("btn-close-map-modal");
  const btnView3dRoute = document.getElementById("btn-view-3d-route");
  const storeMapCanvas = document.getElementById("store-map-canvas");
  const mapTargetStatus = document.getElementById("map-target-status");

  const modalQrGen = document.getElementById("modal-qr-gen");
  const btnQrGenerator = document.getElementById("btn-qr-generator");
  const btnCloseGenModal = document.getElementById("btn-close-gen-modal");
  const selectQrProduct = document.getElementById("select-qr-product");
  const qrcodeDisplay = document.getElementById("qrcode-display");
  const qrCodeLabel = document.getElementById("qr-code-label");
  const btnScanThisQr = document.getElementById("btn-scan-this-qr");

  // Sample Chips Grid
  const sampleChipsGrid = document.getElementById("sample-chips-grid");

  let activeProduct = null;

  // Initialize QR Camera Engine
  window.qrEngine.init(cameraVideo, qrCanvas, (code) => {
    handleQRScanned(code, true);
  });

  // Populate Sample Test Chips
  async function renderSampleChips() {
    const products = await window.productService.getAllProducts();
    sampleChipsGrid.innerHTML = "";

    products.forEach((prod) => {
      const chip = document.createElement("button");
      chip.className = "sample-chip";
      chip.dataset.qr = prod.qrCode;
      chip.innerHTML = `
        <img class="chip-thumb" src="${prod.image}" alt="${prod.name}">
        <div>
          <div class="chip-name">${prod.name}</div>
          <div class="chip-sub">${prod.brand} • ₹${prod.price.toFixed(2)}</div>
        </div>
      `;
      chip.addEventListener("click", () => {
        handleQRScanned(prod.qrCode);
      });
      sampleChipsGrid.appendChild(chip);
    });
  }

  let currentUserCoords = { x: 30, y: 240, label: "Entrance" };

  // Handle QR Code Detected (Live or Simulated)
  async function handleQRScanned(qrCode, isActualScan = false) {
    arReticle.classList.add("locked");
    window.arRenderer.playLockChime();

    const response = await window.productService.fetchProductByQR(qrCode);

    if (response.success) {
      activeProduct = response.data;
      
      // Update location if actually scanned via camera
      if (isActualScan && activeProduct.location && activeProduct.location.coordinates) {
        const coords = activeProduct.location.coordinates;
        // Map 3D coordinates to 2D canvas coordinates
        const startX = 60;
        const startY = 50;
        const numAisles = 6;
        const gapX = 65;
        const aisleHeight = 160;
        currentUserCoords = {
          x: startX + (coords.x / 40) * (numAisles * gapX),
          y: startY + (coords.z / 30) * aisleHeight,
          label: `Scanned at ${activeProduct.name}`
        };
      }
      
      // Render card immediately with a loading state for the price
      renderARCard(activeProduct, true);
      arProdPrice.innerHTML = `<span class="loading-pulse" style="font-size: 1rem; color: #38bdf8;">⚡ Checking Amazon...</span>`;
      
      // Fetch Competitor Price
      const scrapeResult = await window.aiService.scrapeCompetitor(activeProduct);
      if (scrapeResult && scrapeResult.price) {
        activeProduct.compPrice = scrapeResult.price;
        activeProduct.competitors = scrapeResult.competitors;
        // Dynamic Pricing: Beat least price by ~5%
        let targetPrice = 0;
        if (scrapeResult.price !== "NA") {
          targetPrice = Math.floor(scrapeResult.price * 0.95);
        }
        if (targetPrice > 0) {
          activeProduct.price = targetPrice;
          // Update JSON file via backend
          fetch('http://localhost:5000/api/update_price', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ qrCode: activeProduct.qrCode, new_price: targetPrice })
          }).catch(e => console.error("Price update failed:", e));
        }
      }
      
      // Re-render card with updated prices
      renderARCard(activeProduct);
    } else {
      console.warn(response.message);
    }

    setTimeout(() => {
      arReticle.classList.remove("locked");
    }, 1200);
  }

  // Populate Floating 3D AR Product Card with server data
  async function renderARCard(product, skipAiAnalysis = false) {
    arProdImg.src = product.image;
    arProdBrand.textContent = product.brand;
    arProdTitle.textContent = product.name;
    
    // Display dynamic pricing if competitor price is available
    if (product.competitors && product.competitors.length > 0) {
      const compsHtml = product.competitors.map(c => `${c.name}: ${c.price === "NA" ? "NA" : "₹" + c.price.toFixed(2)}`).join(' | ');
      arProdPrice.innerHTML = `<span style="color: #10b981;">₹${product.price.toFixed(2)}</span> <br><span style="font-size: 0.8rem; text-decoration: line-through; color: #64748b;">${compsHtml}</span>`;
    } else if (product.compPrice) {
      arProdPrice.innerHTML = `<span style="color: #10b981;">₹${product.price.toFixed(2)}</span> <span style="font-size: 0.9rem; text-decoration: line-through; color: #64748b; margin-left: 0.5rem;">Amazon: ${product.compPrice === "NA" ? "NA" : "₹" + product.compPrice.toFixed(2)}</span>`;
    } else {
      arProdPrice.textContent = `₹${product.price.toFixed(2)}`;
    }

    if (product.originalPrice && product.originalPrice > product.price) {
      arProdOldPrice.style.display = "inline";
      arProdOldPrice.textContent = `₹${product.originalPrice.toFixed(2)}`;
    } else {
      arProdOldPrice.style.display = "none";
    }

    if (product.discountBadge) {
      arProdDiscount.style.display = "inline";
      arProdDiscount.textContent = product.discountBadge;
    } else {
      arProdDiscount.style.display = "none";
    }

    arProdUnit.textContent = `Unit: ${product.unit}`;
    arProdStock.textContent = product.inStock ? "✓ In Stock" : "✕ Out of Stock";
    arProdRating.textContent = `★ ${product.rating} (${product.reviewsCount} reviews)`;

    // Highlights list
    arProdHighlights.innerHTML = "";
    if (product.specifications && product.specifications.features) {
      product.specifications.features.forEach(hl => {
        const li = document.createElement("li");
        li.textContent = hl;
        arProdHighlights.appendChild(li);
      });
    }

    // Auto-Fetch Front-and-Center OmniTag AI Analysis
    if (!skipAiAnalysis) {
      await updateMainAiTagAnalysis(product, selectAiPersona.value);
    } else {
      aiProviderBadgeMain.textContent = window.aiService.getProviderDisplayName();
      aiRecContentMain.innerHTML = `<span class="loading-pulse" style="font-size: 0.8rem; color: #34d399;">⚡ Checking live inventory and deals...</span>`;
    }

    // Specs Panel
    if (product.specifications) {
      arSpecWarranty.textContent = `Warranty: ${product.specifications.warranty}`;
      arSpecQuality.textContent = product.specifications.qualityScore || "A";

      arMacrosGrid.innerHTML = "";
      const macros = product.specifications.keySpecs || {};
      for (const [key, val] of Object.entries(macros)) {
        const macroBox = document.createElement("div");
        macroBox.className = "macro-item";
        macroBox.innerHTML = `
          <div class="macro-val">${val}</div>
          <div class="macro-lbl">${key.toUpperCase()}</div>
        `;
        arMacrosGrid.appendChild(macroBox);
      }
    }

    // Reviews Panel
    arReviewsContainer.innerHTML = "";
    if (product.reviews && product.reviews.length > 0) {
      product.reviews.forEach(rev => {
        const revCard = document.createElement("div");
        revCard.className = "alt-card";
        revCard.innerHTML = `
          <div style="font-size: 0.8rem; color: #fff; margin-bottom: 0.4rem; font-style: italic;">"${rev}"</div>
          <div style="font-size: 0.65rem; color: #f59e0b;">⭐⭐⭐⭐⭐ Verified Buyer</div>
        `;
        arReviewsContainer.appendChild(revCard);
      });
    }

    // Alternatives Panel (Placeholder)
    arAccessoriesContainer.innerHTML = "";
    const altItem = document.createElement("div");
    altItem.className = "alt-card";
    altItem.innerHTML = `
      <div class="alt-info">
        <h5 style="color: #38bdf8;">Generate AI Alternatives</h5>
        <p>Head to the 🤖 AI Studio tab to generate personalized product alternatives and deal comparisons!</p>
      </div>
    `;
    arAccessoriesContainer.appendChild(altItem);

    // Wayfinder Radar Panel
    if (product.location) {
      arWayfinderAisle.textContent = `${product.location.aisle} - ${product.location.section}`;
      const dist = window.arRenderer.calculateDistance(product.location.coordinates);
      arWayfinderText.textContent = `${product.location.guidance} (${dist}m away)`;

      window.arRenderer.drawRadarHUD(radarCanvas, product.location.coordinates, product.colorTheme || "#10b981");
    }

    // Reset GenAI Output
    aiReportOutput.style.display = "none";
    aiChatHistory.innerHTML = `
      <div style="font-size: 0.75rem; color: var(--text-muted); background: rgba(15, 23, 42, 0.6); padding: 0.5rem; border-radius: 6px;">
        🤖 <strong>OmniTag AI:</strong> Ask me about specs, comparisons, or review details for <strong>${product.name}</strong>!
      </div>
    `;

    // Show Card with animation
    arCard.style.display = "block";
    if (product.colorTheme) {
      arCard.style.borderColor = product.colorTheme;
    }
  }

  // Update Main AI Tag Analysis Banner based on Product & User Context
  async function updateMainAiTagAnalysis(product, userContext) {
    if (!product) return;
    
    // Show loading state
    aiProviderBadgeMain.textContent = window.aiService.getProviderDisplayName();
    aiRecContentMain.innerHTML = `
      <div style="color: #34d399; font-size: 0.75rem;">
        ⚡ OmniTag AI is analyzing reviews and deals for ${product.name}...
      </div>
    `;

    const aiData = await window.aiService.autoFetchTagAnalysis(product, userContext, product.compPrice, product.price);
    aiProviderBadgeMain.textContent = aiData.provider;
    aiRecContentMain.innerHTML = `
      <div style="margin-bottom: 0.4rem;">
        <strong>⭐ Review Verdict:</strong> <span style="color: #34d399; font-weight: 600;">${aiData.analysis.verdict}</span>
      </div>
      <div style="margin-bottom: 0.4rem;">
        <strong>💰 Deal Score:</strong> <span style="color: #38bdf8; font-weight: 600;">${aiData.analysis.dealScore}</span> — <em>"${aiData.analysis.compatibility}"</em>
      </div>
      <div style="font-size: 0.75rem; color: var(--text-muted);">
        💡 <strong>Specs Translation:</strong> ${aiData.analysis.specsTranslation}
      </div>
    `;
  }

  // Dynamic update when user context dropdown is changed
  selectAiPersona.addEventListener("change", () => {
    if (activeProduct) {
      updateMainAiTagAnalysis(activeProduct, selectAiPersona.value);
    }
  });

  // GenAI Detailed Report Trigger
  btnTriggerGenaiReport.addEventListener("click", async () => {
    if (!activeProduct) return;

    btnTriggerGenaiReport.disabled = true;
    btnTriggerGenaiReport.textContent = "🤖 Analyzing Deal...";
    aiReportOutput.style.display = "block";
    aiReportOutput.innerHTML = `
      <div style="padding: 0.8rem; background: rgba(15, 23, 42, 0.7); border-radius: 8px; color: #10b981; font-size: 0.8rem;">
        ⚡ ${window.aiService.getProviderDisplayName()} is generating a detailed purchase report for ${activeProduct.name}...
      </div>
    `;

    const aiData = await window.aiService.autoFetchTagAnalysis(activeProduct, selectAiPersona.value);
    const aiAnalysis = aiData.analysis;

    aiReportOutput.innerHTML = `
      <div class="alt-card" style="border-color: #10b981; background: rgba(16, 185, 129, 0.1);">
        <div style="font-size: 0.65rem; color: #34d399; font-weight: 700; text-transform: uppercase; margin-bottom: 0.2rem;">${aiAnalysis.aiNote || '✨ OmniTag Fine-Tuned Model'}</div>
        <div class="alt-title" style="color: #10b981;">Deep Dive: ${activeProduct.name}</div>
        <div class="alt-meta">
          <span>📉 Deal: ${aiAnalysis.dealScore}</span>
        </div>
        <div style="font-size: 0.75rem; color: #fff; margin-bottom: 0.4rem;"><strong>Compatibility:</strong></div>
        <div style="font-size: 0.75rem; color: var(--text-muted); margin-left: 1.2rem; margin-bottom: 0.6rem;">
          ${aiAnalysis.compatibility}
        </div>
        <div style="font-size: 0.75rem; color: #fff; margin-bottom: 0.4rem;"><strong>Simplified Specs:</strong></div>
        <div style="font-size: 0.75rem; color: var(--text-muted); margin-left: 1.2rem;">
          ${aiAnalysis.specsTranslation}
        </div>
      </div>
    `;

    btnTriggerGenaiReport.disabled = false;
    btnTriggerGenaiReport.textContent = "Generate Report";
  });

  // GenAI Assistant Chat Submit
  async function handleAiChat() {
    const query = inputAiChat.value.trim();
    if (!query || !activeProduct) return;

    inputAiChat.value = "";

    const userMsg = document.createElement("div");
    userMsg.style.cssText = "font-size: 0.75rem; color: #38bdf8; background: rgba(56, 189, 248, 0.1); padding: 0.5rem; border-radius: 6px; align-self: flex-end;";
    userMsg.innerHTML = `<strong>You:</strong> ${query}`;
    aiChatHistory.appendChild(userMsg);
    aiChatHistory.scrollTop = aiChatHistory.scrollHeight;

    const aiRes = await window.aiService.askAIAssistant(activeProduct, query);

    const aiMsg = document.createElement("div");
    aiMsg.style.cssText = "font-size: 0.75rem; color: #fff; background: rgba(16, 185, 129, 0.15); padding: 0.5rem; border-radius: 6px;";
    aiMsg.innerHTML = `🤖 <strong>${aiRes.providerBadge}:</strong> ${aiRes.answer}`;
    aiChatHistory.appendChild(aiMsg);
    aiChatHistory.scrollTop = aiChatHistory.scrollHeight;
  }

  btnSendAiChat.addEventListener("click", handleAiChat);
  inputAiChat.addEventListener("keypress", (e) => {
    if (e.key === "Enter") handleAiChat();
  });

  // AI Server Config Modal
  btnGenaiConfig.addEventListener("click", () => {
    selectOsProvider.value = window.aiService.provider;
    inputPythonUrl.value = window.aiService.pythonUrl;
    inputHfModel.value = window.aiService.modelName;
    inputHfToken.value = window.aiService.hfToken;
    inputOllamaUrl.value = window.aiService.ollamaUrl;
    inputGroqKey.value = window.aiService.groqKey;

    updateProviderFieldVisibility();
    modalGenaiConfig.classList.add("open");
  });

  function updateProviderFieldVisibility() {
    const provider = selectOsProvider.value;
    osConfigPythonFields.style.display = provider === "local_python" ? "block" : "none";
    osConfigHfFields.style.display = provider === "huggingface" ? "block" : "none";
    osConfigOllamaFields.style.display = provider === "ollama" ? "block" : "none";
    osConfigGroqFields.style.display = provider === "groq" ? "block" : "none";
  }

  selectOsProvider.addEventListener("change", updateProviderFieldVisibility);

  btnCloseGenaiModal.addEventListener("click", () => {
    modalGenaiConfig.classList.remove("open");
  });

  btnSaveGenaiSettings.addEventListener("click", () => {
    window.aiService.setProviderConfig({
      provider: selectOsProvider.value,
      pythonUrl: inputPythonUrl.value.trim(),
      modelName: inputHfModel.value,
      hfToken: inputHfToken.value.trim(),
      ollamaUrl: inputOllamaUrl.value.trim(),
      groqKey: inputGroqKey.value.trim()
    });
    aiProviderBadgeMain.textContent = window.aiService.getProviderDisplayName();
    modalGenaiConfig.classList.remove("open");
    if (activeProduct) {
      updateMainAiTagAnalysis(activeProduct, selectAiPersona.value);
    }
    alert(`Saved! Now connected to ${window.aiService.getProviderDisplayName()}`);
  });

  // AR Card Tab Switching
  document.querySelectorAll(".ar-tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".ar-tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".ar-tab-panel").forEach(p => p.classList.remove("active"));

      btn.classList.add("active");
      const targetTabId = btn.dataset.tab;
      document.getElementById(targetTabId).classList.add("active");
    });
  });

  // 3D Perspective Tilt on AR Card Mouse Movement
  arCard.addEventListener("mousemove", (e) => {
    window.arRenderer.applyCardTilt(arCard, e);
  });

  arCard.addEventListener("mouseleave", () => {
    window.arRenderer.resetCardTilt(arCard);
  });

  // Close AR Card
  btnCloseAr.addEventListener("click", () => {
    arCard.style.display = "none";
  });

  // Camera Controls
  async function toggleCamera() {
    if (window.qrEngine.isScanning) {
      window.qrEngine.stopCamera();
      cameraFallback.style.display = "flex";
      cameraBtnText.textContent = "Start Camera";
    } else {
      const success = await window.qrEngine.startCamera();
      if (success) {
        cameraFallback.style.display = "none";
        cameraBtnText.textContent = "Stop Camera";
      } else {
        alert("Camera permission denied or camera not available. You can test all AI features using the instant sample test chips below!");
      }
    }
  }

  btnToggleCamera.addEventListener("click", toggleCamera);
  btnStartCameraHero.addEventListener("click", toggleCamera);

  // Store Map Canvas
  function drawStoreMap() {
    if (!storeMapCanvas) return;
    const ctx = storeMapCanvas.getContext("2d");
    const w = storeMapCanvas.width;
    const h = storeMapCanvas.height;

    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#0f172a";
    ctx.fillRect(0, 0, w, h);

    ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
    ctx.lineWidth = 1;
    for (let x = 0; x < w; x += 30) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
    }
    for (let y = 0; y < h; y += 30) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
    }

    const numAisles = 6;
    const aisleWidth = 45;
    const aisleHeight = 160;
    const startX = 60;
    const startY = 50;
    const gapX = 65;

    for (let i = 0; i < numAisles; i++) {
      const ax = startX + i * gapX;
      ctx.fillStyle = "rgba(30, 41, 59, 0.8)";
      ctx.fillRect(ax, startY, aisleWidth, aisleHeight);
      ctx.strokeStyle = "rgba(255, 255, 255, 0.15)";
      ctx.strokeRect(ax, startY, aisleWidth, aisleHeight);

      ctx.fillStyle = "#94a3b8";
      ctx.font = "10px Inter";
      ctx.textAlign = "center";
      ctx.fillText(`Aisle ${i + 1}`, ax + aisleWidth / 2, startY + aisleHeight / 2);
    }

    const userX = currentUserCoords.x;
    const userY = currentUserCoords.y;
    ctx.beginPath();
    ctx.arc(userX, userY, 8, 0, 2 * Math.PI);
    ctx.fillStyle = "#38bdf8";
    ctx.fill();
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.fillStyle = "#ffffff";
    ctx.font = "bold 10px Inter";
    ctx.textAlign = "left";
    ctx.fillText(`You (${currentUserCoords.label})`, userX + 12, userY + 4);

    let targetX = 145;
    let targetY = 120;

    if (activeProduct && activeProduct.location && activeProduct.location.coordinates) {
      const coords = activeProduct.location.coordinates;
      targetX = startX + (coords.x / 40) * (numAisles * gapX);
      targetY = startY + (coords.z / 30) * aisleHeight;
    }

    ctx.beginPath();
    ctx.setLineDash([5, 5]);
    ctx.moveTo(userX, userY);
    // Draw L-shape route connecting user to target
    ctx.lineTo(userX, targetY);
    ctx.lineTo(targetX, targetY);
    ctx.strokeStyle = "#10b981";
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.beginPath();
    ctx.arc(targetX, targetY, 9, 0, 2 * Math.PI);
    ctx.fillStyle = "#10b981";
    ctx.fill();
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.fillStyle = "#10b981";
    ctx.font = "bold 11px Outfit";
    ctx.textAlign = "center";
    const prodName = activeProduct ? activeProduct.name : "Target Item";
    ctx.fillText("📍", targetX, targetY - 22);
    ctx.fillText(prodName, targetX, targetY - 10);
  }

  // Modals Event Listeners
  btnOpenMap.addEventListener("click", () => {
    modalStoreMap.classList.add("open");
    if (activeProduct) {
      mapTargetStatus.textContent = `Targeted Product: ${activeProduct.name} (${activeProduct.location.aisle})`;
    } else {
      mapTargetStatus.textContent = "Select/Scan a product to see guidance route.";
    }
    drawStoreMap();
  });

  btnView3dRoute.addEventListener("click", () => {
    modalStoreMap.classList.add("open");
    if (activeProduct && activeProduct.location) {
      mapTargetStatus.textContent = `Targeted Product: ${activeProduct.name} (${activeProduct.location.aisle})`;
    } else {
      mapTargetStatus.textContent = "Select/Scan a product to see guidance route.";
    }
    drawStoreMap();
  });

  btnCloseMapModal.addEventListener("click", () => {
    modalStoreMap.classList.remove("open");
  });

  // QR Generator Modal
  async function populateQRGenSelect() {
    selectQrProduct.innerHTML = "";
    const products = await window.productService.getAllProducts();
    products.forEach(p => {
      const opt = document.createElement("option");
      opt.value = p.qrCode;
      opt.textContent = `${p.name} (${p.qrCode})`;
      selectQrProduct.appendChild(opt);
    });
  }

  function updateQRCodeDisplay(code) {
    qrcodeDisplay.innerHTML = "";
    qrCodeLabel.textContent = code;

    if (window.QRCode) {
      new window.QRCode(qrcodeDisplay, {
        text: code,
        width: 160,
        height: 160,
        colorDark: "#090d16",
        colorLight: "#ffffff",
        correctLevel: window.QRCode.CorrectLevel.H
      });
    }
  }

  btnQrGenerator.addEventListener("click", () => {
    populateQRGenSelect();
    modalQrGen.classList.add("open");
    if (selectQrProduct.value) {
      updateQRCodeDisplay(selectQrProduct.value);
    }
  });

  selectQrProduct.addEventListener("change", (e) => {
    updateQRCodeDisplay(e.target.value);
  });

  btnScanThisQr.addEventListener("click", () => {
    const selectedCode = selectQrProduct.value;
    if (selectedCode) {
      modalQrGen.classList.remove("open");
      handleQRScanned(selectedCode, true);
    }
  });

  btnCloseGenModal.addEventListener("click", () => {
    modalQrGen.classList.remove("open");
  });

  // Initialize Sample Chips Bar
  renderSampleChips();
});
