# OmniTag AR: Smart Price Tags & GenAI Retail Assistant

OmniTag is a next-generation brick-and-mortar retail solution. It replaces static, outdated paper price tags with an interactive **Augmented Reality (AR)** interface and a localized **Generative AI** shopping assistant.

Instead of fighting "showrooming" (where customers check online prices while in-store), OmniTag embraces it. When a customer scans a product's QR code, the system scrapes the internet for live competitive pricing, displays the top competitors in an AR popup, and dynamically undercuts the lowest online price by 5%. Additionally, a locally hosted Llama 3.2 AI provides real-time product insights and answers customer questions.

---

## 🌟 Key Features

* **Augmented Reality UI**: A futuristic "Deep Space" glassmorphism interface that tracks physical QR codes using the device camera (via WebRTC & jsQR).
* **Live Competitor Scraping**: A custom Python web scraper that reads DuckDuckGo HTML results to extract real-world, live Indian Rupee (₹) prices from major retailers (Amazon, Flipkart, Croma) while bypassing bot protections.
* **Smart Dynamic Pricing**: Automatically filters out accessory prices (using a smart baseline) and dynamically updates the store's local price to be exactly 5% cheaper than the lowest online competitor.
* **Spatial Routing**: Interactive 2D store map that draws an L-shaped routing path from the user's physical location to the scanned product's aisle.
* **Generative AI Sales Assistant**: 
  * Integrates with a locally hosted **Llama 3.2 Large Language Model** (via Ollama).
  * Automatically generates structured JSON insights (`Deal Score`, `Verdict`, `Compatibility`) for scanned products.
  * Provides a conversational AI chat interface for shoppers to ask specific product questions.

---

## 📁 Project Structure

* `index.html` - The main entry point for the AR Web Application.
* `styles.css` - Custom styling, animations, and the "Deep Space" theme.
* `js/`
  * `app.js` - Core application logic, QR handling, and pricing algorithms.
  * `arRenderer.js` - Handles the 3D augmented reality floating cards.
  * `aiService.js` - Frontend service to communicate with the Python backend.
  * `qrEngine.js` - WebRTC camera integration and QR code scanning.
  * `database.js` - In-memory store data handling.
* `server.py` - The FastAPI Python backend handling web scraping and LLM routing.
* `mock_store_data.json` - The local database storing product info, coordinates, and prices.
* `docker-compose.yml` - Docker configuration to spin up the backend and the Ollama LLM engine.
* `Dockerfile` - Docker instructions for building the Python FastAPI backend.

---

## 🚀 How to Run the Project

The entire stack is containerized for ease of use. You will need [Docker](https://www.docker.com/) installed on your machine.

### 1. Start the Backend & AI Engine
Open your terminal in the project root folder and run:
```bash
docker compose up -d
```
This single command will:
1. Spin up the `local_llm_engine` container, start the Ollama server, and pull the **Llama 3.2** model automatically.
2. Spin up the `local_web_app` container, install Python dependencies, and start the FastAPI server on port `5000` (Backend API) and a static file server on port `8000` (Frontend).

### 2. Access the Application
Once the containers are running, open your web browser and navigate to:
```
http://localhost:8000
```
*Note: You must grant the browser permission to access your webcam for the AR QR scanner to function.*

### 3. Stopping the Application
To safely power down the backend and AI engine, run:
```bash
docker compose down
```

---

## 🛠️ API Endpoints Reference

The FastAPI backend (`http://localhost:5000`) exposes the following core endpoints:
* `POST /api/scrape_competitor`: Scrapes the live web for competitor prices (Amazon, Flipkart) based on the product name and returns the lowest valid price.
* `POST /api/update_price`: Updates the local `mock_store_data.json` database with the newly calculated dynamic price.
* `POST /api/scan_tag`: Prompts the Llama 3.2 LLM to generate structured product insights (Verdict, Deal Score).
* `POST /api/ask`: A conversational endpoint to chat with Llama 3.2 about a specific product.
