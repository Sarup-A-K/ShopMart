import json

with open('mock_store_data.json', 'r') as f:
    products = json.load(f)

urls = [
    "https://images.unsplash.com/photo-1610945415295-d9bbf067e59c?q=80&w=600&auto=format&fit=crop", # Phone
    "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?q=80&w=600&auto=format&fit=crop", # Earbuds
    "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?q=80&w=600&auto=format&fit=crop", # T-Shirt
    "https://images.unsplash.com/photo-1583391733958-d25e07fac0fa?q=80&w=600&auto=format&fit=crop", # Ethnic
    "https://images.unsplash.com/photo-1542291026-7eec264c27ff?q=80&w=600&auto=format&fit=crop", # Sneakers
    "https://images.unsplash.com/photo-1603487742131-4160ec999306?q=80&w=600&auto=format&fit=crop"  # Sandals
]

for i, p in enumerate(products):
    p["image"] = urls[i % len(urls)]

with open('mock_store_data.json', 'w') as f:
    json.dump(products, f, indent=2)

print("Images replaced with Unsplash equivalents.")
