import json

with open("mock_store_data.json", "r") as f:
    data = json.load(f)

for item in data:
    if "nutrition" in item:
        nutri = item.pop("nutrition")
        specs = {
            "warranty": "1 Year Limited",
            "qualityScore": nutri.get("nutriScore", "A"),
            "keySpecs": nutri.get("macros", {}),
            "features": nutri.get("highlights", [])
        }
        item["specifications"] = specs

with open("mock_store_data.json", "w") as f:
    json.dump(data, f, indent=2)

print("JSON updated successfully!")
