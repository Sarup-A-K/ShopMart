/**
 * Open-Source Generative AI Service Module
 * Sends real HTTP POST API requests to the Local Python AI Server (http://localhost:5000)
 */

class AIService {
  constructor() {
    this.provider = localStorage.getItem("os_ai_provider") || "local_python"; // default local_python
    this.pythonUrl = localStorage.getItem("python_ai_url") || "http://localhost:5000";
  }

  setProviderConfig({ provider, pythonUrl }) {
    if (provider) { this.provider = provider; localStorage.setItem("os_ai_provider", provider); }
    if (pythonUrl) { this.pythonUrl = pythonUrl; localStorage.setItem("python_ai_url", pythonUrl); }
  }

  /**
   * Scrape competitor price via backend LLM agent
   */
  async scrapeCompetitor(product) {
    try {
      const res = await fetch(`${this.pythonUrl}/api/scrape_competitor`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ product_name: product.name })
      });
      if (res.ok) {
        const json = await res.json();
        if (json.success && json.price) {
          return { price: json.price, competitors: json.competitors || [] };
        }
      }
    } catch (e) {
      console.warn("Python AI Scraper error:", e);
    }
    return null;
  }

  /**
   * Auto-fetch AI tag analysis for product on QR Scan
   */
  async autoFetchTagAnalysis(product, userContext = "General Buyer", compPrice = null, locPrice = null) {
    try {
      const res = await fetch(`${this.pythonUrl}/api/scan_tag`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          product_name: product.name,
          category: product.category,
          user_context: userContext,
          competitor_price: compPrice,
          local_price: locPrice
        })
      });
      if (res.ok) {
        const json = await res.json();
        if (json.success && json.data) {
          const data = json.data;
          return {
            provider: `OmniTag AI Engine (Port 5000)`,
            analysis: data.analysis,
            alternative: data.alternatives[0],
            insight: data.insight
          };
        }
      }
    } catch (e) {
      console.warn("Python AI Server (Port 5000) connection error:", e);
    }

    return {
      provider: "OmniTag AI Engine (Offline)",
      analysis: {
        verdict: `Great product for ${userContext}`,
        dealScore: "Fair Price",
        compatibility: "Fits perfectly with your existing items.",
        specsTranslation: "High-quality specs.",
        aiNote: "Local Python AI Server (Offline)"
      },
      alternative: {
        name: "Alternative Brand",
        reason: "Similar features",
        store: "Store B"
      },
      insight: `Please ensure 'python3 server.py' is running on port 5000.`
    };
  }

  /**
   * Send Question to Python AI Server (POST /api/ask)
   */
  async askAIAssistant(product, userQuery) {
    try {
      const res = await fetch(`${this.pythonUrl}/api/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          product_name: product.name,
          question: userQuery
        })
      });

      if (res.ok) {
        const json = await res.json();
        if (json.success && json.answer) {
          return {
            question: userQuery,
            answer: json.answer,
            providerBadge: "OmniTag AI Engine (Port 5000)",
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          };
        }
      }
    } catch (e) {
      console.warn("Python AI Server POST /api/ask failed:", e);
    }

    return {
      question: userQuery,
      answer: `Unable to connect to OmniTag AI Engine at ${this.pythonUrl}. Please check server!`,
      providerBadge: "Server Disconnected",
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
  }

  getProviderDisplayName() {
    return `OmniTag AI Engine (Port 5000)`;
  }
}

window.aiService = new AIService();
