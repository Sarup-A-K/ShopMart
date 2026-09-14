import json

with open('mock_store_data.json', 'r') as f:
    products = json.load(f)

locations = [
    {
        "aisle": "Aisle 3",
        "section": "Electronics & Mobiles",
        "guidance": "Walk 15m ahead, turn right at the display.",
        "coordinates": {"x": 200, "y": 150, "z": -40}
    },
    {
        "aisle": "Aisle 4",
        "section": "Audio & Accessories",
        "guidance": "Straight down 10m on the left.",
        "coordinates": {"x": 100, "y": 80, "z": -20}
    },
    {
        "aisle": "Aisle 7",
        "section": "Men's Fashion",
        "guidance": "Take the escalator to 1st Floor, Aisle 7.",
        "coordinates": {"x": 350, "y": 200, "z": 10}
    },
    {
        "aisle": "Aisle 8",
        "section": "Women's Ethnic Wear",
        "guidance": "1st Floor, center aisle.",
        "coordinates": {"x": 300, "y": 250, "z": 20}
    },
    {
        "aisle": "Aisle 10",
        "section": "Sports & Running",
        "guidance": "Ground floor, back wall display.",
        "coordinates": {"x": 400, "y": 50, "z": -60}
    },
    {
        "aisle": "Aisle 11",
        "section": "Women's Footwear",
        "guidance": "Ground floor, near checkout counters.",
        "coordinates": {"x": 80, "y": 180, "z": -15}
    }
]

for i, p in enumerate(products):
    p["location"] = locations[i % len(locations)]

with open('mock_store_data.json', 'w') as f:
    json.dump(products, f, indent=2)

print("Added locations!")
