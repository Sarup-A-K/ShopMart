import requests, re, urllib.parse

def get_price(product, site, baseline):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"}
    query = urllib.parse.quote(f"site:{site} {product} price in india")
    url = f"https://www.bing.com/search?q={query}"
    res = requests.get(url, headers=headers, timeout=5)
    
    matches = re.findall(r"(?:₹|Rs\.?)\s*([0-9,]{3,})", res.text)
    valid_prices = []
    for m in matches:
        try:
            p = float(m.replace(',', ''))
            if baseline * 0.5 < p < baseline * 1.5:
                valid_prices.append(p)
        except:
            pass
    
    if valid_prices:
        return min(valid_prices)
    return "NA"

baseline = 9995
print("Amazon:", get_price("Logitech MX Master 3S Mouse", "amazon.in", baseline))
print("Flipkart:", get_price("Logitech MX Master 3S Mouse", "flipkart.com", baseline))
print("Croma:", get_price("Logitech MX Master 3S Mouse", "croma.com", baseline))
