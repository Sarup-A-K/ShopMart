import json

with open('mock_store_data.json', 'r') as f:
    products = json.load(f)

# The radar draws Aisles 1 to 6.
# If coords.x = 0, targetX = startX (Aisle 1)
# targetX = startX + (coords.x / 40) * (numAisles * gapX);
# To land exactly on Aisle i (1-indexed):
# We want targetX = startX + (i-1) * gapX
# So: (coords.x / 40) * (6 * 65) = (i-1) * 65
# (coords.x / 40) * 6 = i-1
# coords.x = (i-1) / 6 * 40
# Wait, numAisles * gapX = 390.
# So coords.x should be: Aisle 1 -> 0. Aisle 2 -> 6.66, Aisle 3 -> 13.33, Aisle 4 -> 20, Aisle 5 -> 26.66, Aisle 6 -> 33.33

locations = [
    {
        "aisle": "Aisle 1",
        "section": "Mobiles",
        "guidance": "Walk 5m ahead on the left.",
        "coordinates": {"x": 0, "y": 0, "z": 5} # Aisle 1
    },
    {
        "aisle": "Aisle 2",
        "section": "Audio",
        "guidance": "Aisle 2, halfway down.",
        "coordinates": {"x": 6.66, "y": 0, "z": 15} # Aisle 2
    },
    {
        "aisle": "Aisle 3",
        "section": "Men's Apparel",
        "guidance": "Aisle 3, front display.",
        "coordinates": {"x": 13.33, "y": 0, "z": 2} # Aisle 3
    },
    {
        "aisle": "Aisle 4",
        "section": "Women's Apparel",
        "guidance": "Aisle 4, middle section.",
        "coordinates": {"x": 20.0, "y": 0, "z": 10} # Aisle 4
    },
    {
        "aisle": "Aisle 5",
        "section": "Sports Footwear",
        "guidance": "Aisle 5, back wall.",
        "coordinates": {"x": 26.66, "y": 0, "z": 20} # Aisle 5
    },
    {
        "aisle": "Aisle 6",
        "section": "Women's Footwear",
        "guidance": "Aisle 6, near checkout.",
        "coordinates": {"x": 33.33, "y": 0, "z": 10} # Aisle 6
    }
]

for i, p in enumerate(products):
    p["location"] = locations[i % len(locations)]

with open('mock_store_data.json', 'w') as f:
    json.dump(products, f, indent=2)

print("Aisles updated.")
