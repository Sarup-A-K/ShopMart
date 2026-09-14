import json

new_products = [
  {
    "qrCode": "item-1",
    "name": "Samsung Galaxy M34 5G (Prism Silver, 6GB RAM, 128GB Storage)",
    "brand": "Samsung",
    "price": 15999,
    "originalPrice": 18999,
    "category": "Electronics",
    "image": "https://m.media-amazon.com/images/I/91ItZJh1F-L._SX679_.jpg",
    "description": "A powerful mid-range 5G smartphone with a massive battery and a vibrant Super AMOLED display.",
    "specifications": {
      "warranty": "1 Year Manufacturer Warranty",
      "qualityScore": "A+",
      "keySpecs": {
        "RAM": "6GB",
        "Storage": "128GB",
        "Display": "6.5-inch Super AMOLED",
        "Battery": "6000 mAh"
      },
      "features": [
        "50MP No Shake Cam",
        "120Hz Refresh rate",
        "4 Gen OS Upgrades"
      ]
    },
    "reviews": [
      "Great battery life and the display is stunning. Camera is decent for the price.",
      "Phone is slightly bulky due to the large battery, but performance is smooth."
    ]
  },
  {
    "qrCode": "item-2",
    "name": "boAt Airdopes 141 Bluetooth Truly Wireless in Ear Earbuds",
    "brand": "boAt",
    "price": 1299,
    "originalPrice": 2990,
    "category": "Electronics",
    "image": "https://m.media-amazon.com/images/I/51nOzqGtw2L._SX522_.jpg",
    "description": "Lightweight and stylish truly wireless earbuds offering long playtime and clear audio quality.",
    "specifications": {
      "warranty": "1 Year Warranty",
      "qualityScore": "A",
      "keySpecs": {
        "Playtime": "Up to 42 hours",
        "Driver Size": "8mm",
        "Bluetooth": "5.1",
        "Water Res.": "IPX4"
      },
      "features": [
        "ENx Tech for clear calls",
        "ASAP Charge",
        "Touch Controls"
      ]
    },
    "reviews": [
      "Awesome sound quality and bass. Battery backup is just amazing.",
      "Very comfortable to wear for long hours. Mic quality is okay for regular calls."
    ]
  },
  {
    "qrCode": "item-3",
    "name": "Puma Men's Regular Fit T-Shirt",
    "brand": "Puma",
    "price": 849,
    "originalPrice": 1299,
    "category": "Fashion",
    "image": "https://m.media-amazon.com/images/I/71cFlRq1X-L._SX569._SX._UX._SY._UY_.jpg",
    "description": "A comfortable and breathable everyday cotton t-shirt featuring the classic Puma logo.",
    "specifications": {
      "warranty": "Not Available",
      "qualityScore": "B+",
      "keySpecs": {
        "Material": "100% Cotton",
        "Fit": "Regular Fit",
        "Neck Style": "Crew Neck",
        "Sleeve": "Short Sleeve"
      },
      "features": [
        "Soft and breathable fabric",
        "Durable stitching",
        "Easy machine wash"
      ]
    },
    "reviews": [
      "Perfect fit and the material feels very soft. Good value for money.",
      "Color fades slightly after a few washes, but still looks good."
    ]
  },
  {
    "qrCode": "item-4",
    "name": "Biba Women's Cotton Straight Printed Kurta",
    "brand": "Biba",
    "price": 1199,
    "originalPrice": 1999,
    "category": "Fashion",
    "image": "https://m.media-amazon.com/images/I/71O15wU5L8L._SY741._SX._UX._SY._UY_.jpg",
    "description": "An elegant cotton straight kurta with vibrant prints, perfect for casual and festive wear.",
    "specifications": {
      "warranty": "Not Available",
      "qualityScore": "A",
      "keySpecs": {
        "Material": "Cotton",
        "Style": "Straight",
        "Length": "Calf Length",
        "Pattern": "Printed"
      },
      "features": [
        "Lightweight and comfortable",
        "Vibrant, fade-resistant prints",
        "Easy to style"
      ]
    },
    "reviews": [
      "Beautiful print and exact fitting. The cotton is of premium quality.",
      "Very comfortable for summer wear. Looks exactly like the picture."
    ]
  },
  {
    "qrCode": "item-5",
    "name": "Nike Men's Revolution 6 Running Shoes",
    "brand": "Nike",
    "price": 2795,
    "originalPrice": 3695,
    "category": "Footwear",
    "image": "https://m.media-amazon.com/images/I/61m1hIARZ-L._SY695._SX._UX._SY._UY_.jpg",
    "description": "Versatile and comfortable running shoes designed for maximum cushioning and flexibility.",
    "specifications": {
      "warranty": "30 Days Manufacturer Warranty",
      "qualityScore": "A",
      "keySpecs": {
        "Outer": "Mesh",
        "Sole": "Rubber",
        "Closure": "Lace-Up",
        "Width": "Regular"
      },
      "features": [
        "Breathable mesh upper",
        "Foam midsole",
        "Recycled materials"
      ]
    },
    "reviews": [
      "Extremely lightweight and great for daily jogging. True to size.",
      "Good support for the arch, but needs a few days to break in."
    ]
  },
  {
    "qrCode": "item-6",
    "name": "Bata Women's Fashion Sandals",
    "brand": "Bata",
    "price": 699,
    "originalPrice": 999,
    "category": "Footwear",
    "image": "https://m.media-amazon.com/images/I/81P8N8fC9qL._SY695._SX._UX._SY._UY_.jpg",
    "description": "Stylish and durable sandals featuring a comfortable footbed for all-day wear.",
    "specifications": {
      "warranty": "90 Days Warranty",
      "qualityScore": "B+",
      "keySpecs": {
        "Material": "Synthetic",
        "Sole": "Polyurethane",
        "Heel": "1.5 inches",
        "Closure": "Buckle"
      },
      "features": [
        "Cushioned footbed",
        "Anti-slip sole",
        "Elegant design"
      ]
    },
    "reviews": [
      "Very soft and comfortable for daily wear. Fits perfectly.",
      "Looks stylish and the quality is excellent for the price."
    ]
  }
]

with open('mock_store_data.json', 'w') as f:
    json.dump(new_products, f, indent=2)

print("Database updated!")
