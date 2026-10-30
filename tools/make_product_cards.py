"""
Generate an honest illustrated card for every product in seed_products.json.

Stock photos of "a phone" always look like some specific phone, which misleads shoppers. These cards show a simple
drawing of the product TYPE plus the real brand, model and key specs taken from the catalogue data. Real photos can
still be added per product in Admin > Photos.

    python3 tools/make_product_cards.py        # writes web/img/products/<qr_code>.svg
"""
import html
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "web", "img", "products")

INK, ACCENT, SOFT = "#10243a", "#ffc233", "#dbe9fb"
BACKGROUND = {"Electronics": ("#e9f2fd", "#cfe2f8"), "Fashion": ("#fdeee7", "#f8d9cb"), "Footwear": ("#e7f6ef", "#c9ebdb")}

# Short card titles and drawings are chosen from words in the product's own name, so the cards stay correct when the
# catalogue changes (a card is never matched by item number).
SHORT_TITLES = [
    ("Galaxy M34", "Galaxy M34 5G"), ("Airdopes", "Airdopes 141"), ("Redmi Note 13", "Note 13 5G"), ("iPhone 13", "iPhone 13"),
    ("Rockerz", "Rockerz 450 Headphones"), ("WH-CH520", "WH-CH520 Headphones"), ("Flip 6", "Flip 6 Speaker"),
    ("Textured Slim Fit Shirt", "Textured Slim Fit Shirt"), ("Washed Jeans", "Washed Regular Fit Jeans"),
    ("Stretch Printed T-Shirt", "Printed Slim Fit T-Shirt"), ("Co-Ord", "Embellished Co-Ord Set"), ("Salwar", "Embellished Salwar Suit"),
    ("V-Neck", "Printed V-Neck T-Shirt"), ("PROVE", "PROVE Running Shoes"), ("RAKE", "RAKE Running Shoes"),
    ("NORIKA", "NORIKA Running Shoes"), ("LUCK", "LUCK Sneakers"), ("SCALE", "SCALE CS Sneakers"), ("AZURA", "AZURA Sneakers"),
]
# First matching word wins, so more specific words come first
ICON_WORDS = [
    ("earbuds", "earbuds"), ("headphones", "headphones"), ("speaker", "speaker"), ("t-shirt", "tshirt"), ("jeans", "jeans"),
    ("co-ord", "dress"), ("dress", "dress"), ("salwar", "kurta"), ("kurta", "kurta"), ("shirt", "shirt"), ("sandal", "sandal"),
    ("heel", "heel"), ("shoes", "shoe"), ("sneakers", "shoe"),
]


def title_for(product):
    name = product["name"]
    return next((short for key, short in SHORT_TITLES if key.lower() in name.lower()), name)


def icon_for(product):
    name = product["name"].lower()
    for word, icon in ICON_WORDS:
        if word in name:
            return icon
    return "phone" if product.get("category") == "Electronics" else "shirt"


S = f'stroke="{INK}" stroke-width="3.2" stroke-linejoin="round" stroke-linecap="round"'
ICONS = {
    "phone": f'''<rect x="30" y="6" width="40" height="88" rx="9" fill="#fff" {S}/>
      <rect x="35" y="16" width="30" height="64" rx="3" fill="{SOFT}"/>
      <rect x="44" y="10" width="12" height="3" rx="1.5" fill="{INK}"/>
      <rect x="38" y="20" width="10" height="10" rx="3" fill="{ACCENT}"/><rect x="52" y="20" width="10" height="10" rx="3" fill="{INK}" opacity=".75"/>
      <rect x="38" y="34" width="10" height="10" rx="3" fill="{INK}" opacity=".75"/><rect x="52" y="34" width="10" height="10" rx="3" fill="{ACCENT}"/>
      <line x1="42" y1="87" x2="58" y2="87" {S}/>''',
    "earbuds": f'''<rect x="20" y="50" width="60" height="38" rx="15" fill="#fff" {S}/>
      <line x1="20" y1="64" x2="80" y2="64" {S}/><circle cx="50" cy="57" r="2.4" fill="{ACCENT}" stroke="none"/>
      <circle cx="32" cy="26" r="10" fill="#fff" {S}/><rect x="38" y="28" width="6" height="20" rx="3" fill="#fff" {S}/>
      <circle cx="68" cy="26" r="10" fill="#fff" {S}/><rect x="56" y="28" width="6" height="20" rx="3" fill="#fff" {S}/>''',
    "headphones": f'''<path d="M20 60 C20 14 80 14 80 60" fill="none" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>
      <rect x="11" y="52" width="18" height="32" rx="9" fill="{ACCENT}" {S}/><rect x="71" y="52" width="18" height="32" rx="9" fill="{ACCENT}" {S}/>''',
    "speaker": f'''<rect x="10" y="34" width="80" height="38" rx="19" fill="#fff" {S}/>
      <path d="M38 34 C42 18 58 18 62 34" fill="none" {S}/>
      <line x1="30" y1="44" x2="30" y2="62" {S}/><line x1="40" y1="42" x2="40" y2="64" {S}/><line x1="50" y1="42" x2="50" y2="64" {S}/>
      <line x1="60" y1="42" x2="60" y2="64" {S}/><line x1="70" y1="44" x2="70" y2="62" {S}/><circle cx="82" cy="53" r="2.4" fill="{ACCENT}" stroke="none"/>''',
    "tshirt": f'''<path d="M34 14 L10 30 L20 46 L30 40 L30 88 L70 88 L70 40 L80 46 L90 30 L66 14 C62 24 38 24 34 14 Z" fill="#fff" {S}/>
      <path d="M34 14 C38 24 62 24 66 14" fill="none" stroke="{ACCENT}" stroke-width="4" stroke-linecap="round"/>''',
    "shirt": f'''<path d="M34 12 L10 34 L16 80 L27 78 L29 44 L30 90 L70 90 L71 44 L73 78 L84 80 L90 34 L66 12 L50 26 Z" fill="#fff" {S}/>
      <path d="M34 12 L50 32 L66 12" fill="none" {S}/><line x1="50" y1="32" x2="50" y2="90" {S}/>
      <circle cx="50" cy="46" r="2.4" fill="{ACCENT}" stroke="none"/><circle cx="50" cy="60" r="2.4" fill="{ACCENT}" stroke="none"/><circle cx="50" cy="74" r="2.4" fill="{ACCENT}" stroke="none"/>''',
    "jeans": f'''<path d="M26 8 H74 V22 L80 92 H54 L50 44 L46 92 H20 L26 22 Z" fill="#fff" {S}/>
      <line x1="26" y1="22" x2="74" y2="22" {S}/><path d="M30 28 C34 34 38 34 42 28" fill="none" stroke="{ACCENT}" stroke-width="3" stroke-linecap="round"/>
      <path d="M70 28 C66 34 62 34 58 28" fill="none" stroke="{ACCENT}" stroke-width="3" stroke-linecap="round"/>''',
    "dress": f'''<path d="M40 6 L44 24 L50 30 L56 24 L60 6 L66 8 L62 40 L84 92 H16 L38 40 L34 8 Z" fill="#fff" {S}/>
      <line x1="38" y1="40" x2="62" y2="40" stroke="{ACCENT}" stroke-width="5" stroke-linecap="round"/>''',
    "kurta": f'''<path d="M34 8 C42 16 58 16 66 8 L86 24 L78 42 L72 36 L74 94 L26 94 L28 36 L22 42 L14 24 Z" fill="#fff" {S}/>
      <path d="M42 11 L50 32 L58 11" fill="none" stroke="{ACCENT}" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round"/>
      <line x1="26" y1="84" x2="74" y2="84" stroke="{ACCENT}" stroke-width="3.6" stroke-linecap="round"/>''',
    "shoe": f'''<path d="M8 66 C8 54 16 50 24 48 L34 30 C42 32 48 42 58 46 C74 48 92 54 94 68 L94 72 L8 72 Z" fill="#fff" {S}/>
      <rect x="6" y="72" width="90" height="11" rx="5.5" fill="{ACCENT}" {S}/>
      <line x1="38" y1="38" x2="44" y2="46" {S}/><line x1="46" y1="44" x2="52" y2="52" {S}/><line x1="30" y1="46" x2="38" y2="52" {S}/>''',
    "sandal": f'''<path d="M6 76 C6 68 12 66 22 68 L86 74 C97 75 97 85 86 85 L18 85 C10 85 6 81 6 76 Z" fill="#fff" {S}/>
      <path d="M28 70 C28 44 58 44 60 74" fill="none" stroke="{ACCENT}" stroke-width="6" stroke-linecap="round"/>
      <path d="M48 72 C50 54 72 56 76 78" fill="none" stroke="{ACCENT}" stroke-width="6" stroke-linecap="round"/>
      <circle cx="29" cy="69" r="2.2" fill="{INK}" stroke="none"/><circle cx="60" cy="73" r="2.2" fill="{INK}" stroke="none"/>''',
    "heel": f'''<path d="M14 28 L30 28 C42 46 62 58 90 64 C99 66 99 76 90 77 C68 79 44 72 26 58 L14 28 Z" fill="#fff" {S}/>
      <path d="M22 56 L20 94" fill="none" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>
      <path d="M34 34 C46 50 64 60 88 66" fill="none" stroke="{ACCENT}" stroke-width="4.5" stroke-linecap="round"/>''',
}


def wrap(text, width):
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return lines + ([line] if line else [])


def chips(product):
    values = [str(v) for v in (product.get("specifications", {}).get("keySpecs", {}) or {}).values()]
    short = [v for v in values if len(v) <= 15][:3]
    return short


def card(product):
    qr = product["qrCode"]
    top, bottom = BACKGROUND.get(product.get("category"), ("#eef1f4", "#dde3ea"))
    title = wrap(title_for(product), 22)[:2]
    e = lambda t: html.escape(str(t), quote=True)
    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 600" role="img" aria-label="%s">' % e(product["name"]),
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/></linearGradient></defs>',
        '<rect width="600" height="600" fill="url(#g)"/>',
        f'<g transform="translate(130 40) scale(3.4)">{ICONS[icon_for(product)]}</g>',
        f'<text x="300" y="424" text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="22" font-weight="700" letter-spacing="4" fill="{INK}" opacity=".6">{e(product["brand"].upper())}</text>',
    ]
    y = 466
    for line in title:
        out.append(f'<text x="300" y="{y}" text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="36" font-weight="700" fill="{INK}">{e(line)}</text>')
        y += 42
    specs = chips(product)
    if specs:
        text = "  ·  ".join(specs)
        out.append(f'<text x="300" y="{max(y + 4, 556)}" text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="24" fill="{INK}" opacity=".72">{e(text)}</text>')
    out.append("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(ROOT, "seed_products.json"), encoding="utf-8") as f:
        products = json.load(f)
    for p in products:
        with open(os.path.join(OUT, f"{p['qrCode']}.svg"), "w", encoding="utf-8") as f:
            f.write(card(p))
    print(f"Wrote {len(products)} cards to {OUT}")
