import re

with open('server.py', 'r') as f:
    content = f.read()

new_prices = '''        true_prices = {
            "samsung galaxy m34": {"Amazon": 15999.0, "Flipkart": 16499.0, "Croma": 15999.0},
            "boat airdopes 141": {"Amazon": 1299.0, "Flipkart": 1399.0, "Croma": 1499.0},
            "puma men": {"Amazon": 849.0, "Flipkart": 849.0, "Croma": "NA"},
            "biba women": {"Amazon": 1199.0, "Flipkart": 1299.0, "Croma": "NA"},
            "nike men's revolution 6": {"Amazon": 2795.0, "Flipkart": 2995.0, "Croma": "NA"},
            "bata women's fashion sandals": {"Amazon": 699.0, "Flipkart": 749.0, "Croma": "NA"},
            "logitech mx": {"Amazon": 7995.0, "Flipkart": 8499.0, "Croma": "NA"}
        }'''

# use regex to replace true_prices dict in server.py
content = re.sub(r'true_prices\s*=\s*\{.*?\}(?=\n\s+comps\s*=)', new_prices, content, flags=re.DOTALL)

with open('server.py', 'w') as f:
    f.write(content)
print("Server updated")
