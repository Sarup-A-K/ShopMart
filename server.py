import os
import json
import urllib.request
import urllib.error
import re
from typing import Optional
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
    competitor_price: Optional[float] = None
    local_price: Optional[float] = None

class ScrapeRequest(BaseModel):
    product_name: str

import re

@app.post("/api/scrape_competitor")
async def scrape_competitor(req: ScrapeRequest):
    try:
        # Smart Fallback mock prices to act as a baseline for filtering bad scrapes (like cases/cables)
        mock_prices = {
            "sony wh-1000xm5": 26990, "levi's 501": 4500, "dyson v15": 54900,
            "apple ipad pro": 85000, "nike air max": 12995, "nespresso": 17500,
            "samsung 65": 129990, "ray-ban": 8500, "philips hue": 13500, "logitech mx": 9995
        }
        baseline = 29990.0
        for k, v in mock_prices.items():
            if k in req.product_name.lower():
                baseline = v
                break

        # Live scrape DuckDuckGo for Amazon/Flipkart prices in India
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        url = f"https://html.duckduckgo.com/html/?q={req.product_name}+price+in+india"
        
        import requests
        res = requests.get(url, headers=headers, timeout=5)
        
        valid_prices = []
        if res.status_code == 200:
            matches = re.findall(r'[R₹][sS]?\.?\s?([0-9,]{4,})', res.text)
            for m in matches:
                p = float(m.replace(',', ''))
                # Filter out absurdly low/high prices (e.g. accessories)
                if baseline * 0.5 < p < baseline * 1.5:
                    valid_prices.append(p)
                    
        # Remove duplicates and sort
        valid_prices = sorted(list(set(valid_prices)))
        
        if len(valid_prices) == 0:
            valid_prices = [baseline, baseline * 1.05, baseline * 1.1]
        
        # Ensure we have at least 3 prices
        while len(valid_prices) < 3:
            valid_prices.append(valid_prices[-1] * 1.05)
            
        least_price = valid_prices[0]
        
        competitors = [
            {"name": "Amazon", "price": valid_prices[0]},
            {"name": "Flipkart", "price": valid_prices[1]},
            {"name": "Croma", "price": valid_prices[2]}
        ]

        return {"success": True, "competitor": "Amazon", "price": least_price, "competitors": competitors}
    except Exception as e:
        print(f"Scraper Error: {e}")
        return {"success": False, "competitor": "Amazon", "price": 29990.0, "competitors": []}

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
