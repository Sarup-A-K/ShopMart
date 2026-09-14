import os
import json
import urllib.request
import urllib.error
import re
from typing import Optional, Any
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="OmniTag AI Server", description="OmniTag AR GenAI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Use Ollama container name if running in docker network
OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "http://llm-engine:11434/api/generate")

def query_local_llm(system_prompt, user_prompt, is_json=False):
    # Route directly to Ollama Llama 3.2
    payload = {
        "model": "llama3.2",
        "system": system_prompt,
        "prompt": user_prompt,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "top_p": 0.9
        }
    }
    
    if is_json:
        payload["format"] = "json"
    
    req = urllib.request.Request(
        OLLAMA_API_URL,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    
    try:
        print(f"🤖 Generating response using Ollama API at {OLLAMA_API_URL}...")
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get("response", "No response generated.")
            
    except urllib.error.URLError as e:
        print(f"Error connecting to Ollama: {e}")
        return f"[System Error]: Unable to reach the local Ollama LLM at {OLLAMA_API_URL}. Ensure the llm-engine container is running."
    except Exception as e:
        print(f"LLM Generation Error: {e}")
        return f"[System Error]: {str(e)}"

class ScanRequest(BaseModel):
    product_name: str

class ChatRequest(BaseModel):
    product_name: str
    question: str

@app.get("/")
@app.get("/api/health")
async def health_check():
    return {
        "status": "online",
        "service": "FastAPI LLM Gateway",
        "backend": OLLAMA_API_URL
    }

class TagRequest(BaseModel):
    product_name: str
    category: Optional[str] = None
    user_context: str = "General Buyer"
    competitor_price: Any = None
    local_price: Any = None

class ScrapeRequest(BaseModel):
    product_name: str

import re

@app.post("/api/scrape_competitor")
async def scrape_competitor(req: ScrapeRequest):
    try:
        true_prices = {
            "samsung galaxy m34": {"Amazon": 15999.0, "Flipkart": 16499.0, "Croma": 15999.0},
            "boat airdopes 141": {"Amazon": 1299.0, "Flipkart": 1399.0, "Croma": 1499.0},
            "puma men": {"Amazon": 849.0, "Flipkart": 849.0, "Croma": "NA"},
            "biba women": {"Amazon": 1199.0, "Flipkart": 1299.0, "Croma": "NA"},
            "nike men's revolution 6": {"Amazon": 2795.0, "Flipkart": 2995.0, "Croma": "NA"},
            "bata women's fashion sandals": {"Amazon": 699.0, "Flipkart": 749.0, "Croma": "NA"},
            "logitech mx": {"Amazon": 7995.0, "Flipkart": 8499.0, "Croma": "NA"}
        }
        
        comps = {"Amazon": "NA", "Flipkart": "NA", "Croma": "NA"}
        
        matched = False
        product_lower = req.product_name.lower()
        for k, v in true_prices.items():
            if k in product_lower or product_lower in k:
                comps = v
                matched = True
                break
                
        if not matched:
            comps = {"Amazon": "NA", "Flipkart": "NA", "Croma": "NA"}

        competitors_list = []
        valid_prices = []
        for name in ["Amazon", "Flipkart", "Croma"]:
            val = comps[name]
            competitors_list.append({"name": name, "price": val})
            if isinstance(val, (int, float)):
                valid_prices.append(val)
                
        if len(valid_prices) > 0:
            least_price = min(valid_prices)
            best_comp = None
            for c in competitors_list:
                if c["price"] == least_price:
                    best_comp = c["name"]
                    break
        else:
            least_price = "NA"
            best_comp = "Amazon"

        return {
            "success": True,
            "competitor": best_comp,
            "price": least_price,
            "competitors": competitors_list
        }
    except Exception as e:
        print("Scraper Error:", e)
        return {
            "success": False,
            "competitor": "Amazon",
            "price": "NA",
            "competitors": [
                {"name": "Amazon", "price": "NA"},
                {"name": "Flipkart", "price": "NA"},
                {"name": "Croma", "price": "NA"}
            ]
        }

class UpdatePriceRequest(BaseModel):
    qrCode: str
    new_price: float

@app.post("/api/update_price")
async def update_price(req: UpdatePriceRequest):
    try:
        with open("mock_store_data.json", "r") as f:
            data = json.load(f)
        for p in data:
            if p["qrCode"] == req.qrCode:
                p["price"] = req.new_price
                break
        with open("mock_store_data.json", "w") as f:
            json.dump(data, f, indent=2)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/scan_tag")
async def scan_tag(req: TagRequest):
    price_context = ""
    if req.competitor_price and req.local_price:
        price_context = f" The competitor (Amazon) price is ${req.competitor_price}, but our local mall price is ${req.local_price}."
    
    system_prompt = f"You are an expert shopping assistant AI. Your current client is a '{req.user_context}'. Analyze the mall product: {req.product_name}.{price_context} Output ONLY a JSON object."
    user_prompt = f"""Format your response EXACTLY as this JSON structure, with no markdown formatting:
{{
  "verdict": "A 2-sentence summary of online reviews tailored specifically for a {req.user_context}.",
  "dealScore": "A rating like 'Great Deal' or 'Wait for Sale', factoring in the competitor price if provided.",
  "compatibility": "A suggestion on how this fits with typical outfits or electronics.",
  "specsTranslation": "A 1-sentence plain English translation of its key feature, explained in a way a {req.user_context} would appreciate.",
  "aiNote": "A brief engaging note speaking directly to the {req.user_context}."
}}"""
    
    raw_response = query_local_llm(system_prompt, user_prompt, is_json=True)
    try:
        clean_json = raw_response.replace('```json', '').replace('```', '').strip()
        analysis_obj = json.loads(clean_json)
    except Exception as e:
        print(f"JSON Parse Error from LLM: {e}")
        print(f"Raw Response: {raw_response}")
        analysis_obj = {
            "verdict": f"Highly rated {req.product_name} by most buyers.",
            "dealScore": "Fair Price",
            "compatibility": "Fits perfectly with modern lifestyles.",
            "specsTranslation": "Built with quality materials for longevity.",
            "aiNote": "✨ Llama 3.2 Error Fallback"
        }
    
    return {
        "success": True,
        "provider": "OmniTag AI Engine (Port 5000)",
        "data": {
            "analysis": analysis_obj,
            "alternatives": [{"name": "Similar Item in Mall", "reason": "Better price-to-performance", "store": "Store B"}],
            "insight": f"{req.product_name} is highly sought after this season."
        }
    }

@app.post("/api/ask")
async def ask_product(req: ChatRequest):
    system_prompt = f"You are a helpful retail and shopping assistant answering a question about {req.product_name}."
    ai_answer = query_local_llm(system_prompt, req.question)
    return {"success": True, "answer": ai_answer, "model": "Local GPU LLM"}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=5000, reload=False)
