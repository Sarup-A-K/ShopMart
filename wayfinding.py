"""
In-store directions. This is a Python port of web/js/wayfinding.js (computeRoute) so the AI agent can
give the same directions the product-page map shows. If you change the store layout, change both.

Map canvas is 500x280 px; product coordinates are in metres (x 0-40 across aisles, z 0-30 deep).
"""
import math
import re

MAP = {"startX": 60, "startY": 50, "gapX": 65, "aisleWidth": 45, "aisleHeight": 160, "numAisles": 6, "corridorY": 235}
STORE_DEPTH_M = 30
STORE_WIDTH_M = 40
M_PER_PX_X = STORE_WIDTH_M / (MAP["numAisles"] * MAP["gapX"])
M_PER_PX_Y = STORE_DEPTH_M / MAP["aisleHeight"]


def _round(x):
    """JavaScript's Math.round (half up), so results match the website exactly."""
    return int(math.floor(x + 0.5))


def _walkway_x(aisle_idx):
    return MAP["startX"] + aisle_idx * MAP["gapX"] - 10


def normalise_checkpoint(value):
    """Accept 'entrance', 'aisle-3', 'Aisle 3', '3' ... and return 'entrance' or 'aisle-N'."""
    text = str(value or "entrance").strip().lower()
    m = re.search(r"(\d+)", text)
    if m and "entrance" not in text and "entry" not in text:
        n = int(m.group(1))
        if 1 <= n <= MAP["numAisles"]:
            return f"aisle-{n}"
    return "entrance"


def checkpoint_coords(checkpoint):
    if checkpoint.startswith("aisle-"):
        n = int(checkpoint.split("-")[1])
        return {"x": _walkway_x(n - 1), "y": MAP["corridorY"], "label": f"Aisle {n}"}
    return {"x": 30, "y": 260, "label": "Entrance"}


def product_target(product):
    loc = product.get("location") or {}
    coords = loc.get("coordinates")
    if not coords:
        return None
    m = re.search(r"\d+", str(loc.get("aisle", "")))
    aisle_num = int(m.group(0)) if m else 1
    return {
        "aisleIdx": aisle_num - 1,
        "x": MAP["startX"] + (coords["x"] / STORE_WIDTH_M) * (MAP["numAisles"] * MAP["gapX"]),
        "y": MAP["startY"] + (coords["z"] / STORE_DEPTH_M) * MAP["aisleHeight"],
        "z": coords["z"],
    }


def directions(product, from_checkpoint="entrance"):
    """Return {aisle, section, from, distance_m, steps} or None if the product has no location."""
    target = product_target(product)
    if not target:
        return None
    start = checkpoint_coords(normalise_checkpoint(from_checkpoint))
    wx = _walkway_x(target["aisleIdx"])
    raw = [
        (start["x"], start["y"]),
        (start["x"], MAP["corridorY"]),
        (wx, MAP["corridorY"]),
        (wx, target["y"]),
        (target["x"], target["y"]),
    ]
    points = [p for i, p in enumerate(raw) if i == 0 or abs(p[0] - raw[i - 1][0]) + abs(p[1] - raw[i - 1][1]) > 1]
    meters = sum(
        abs(points[i][0] - points[i - 1][0]) * M_PER_PX_X + abs(points[i][1] - points[i - 1][1]) * M_PER_PX_Y
        for i in range(1, len(points))
    )

    loc = product["location"]
    aisle_name = f"Aisle {target['aisleIdx'] + 1}"
    corridor_m = _round(abs(wx - start["x"]) * M_PER_PX_X)
    steps = []
    if start["label"] == "Entrance":
        steps.append(f"From the Entrance, walk {corridor_m} m right along the front corridor to {aisle_name}.")
    elif corridor_m > 0:
        side = "right" if wx > start["x"] else "left"
        steps.append(f"From {start['label']}, walk {corridor_m} m {side} along the front corridor to {aisle_name}.")
    else:
        steps.append(f"You're already at the front of {aisle_name}.")
    depth = "front" if target["z"] < 8 else "middle" if target["z"] < 18 else "back"
    aisle_m = _round((MAP["corridorY"] - target["y"]) * M_PER_PX_Y)
    steps.append(f"Turn into {aisle_name} and walk {aisle_m} m to the {depth} of the aisle.")
    steps.append(f"{loc.get('section', 'The')} shelf is on your right; look for {product.get('brand')}.")
    return {
        "aisle": aisle_name,
        "section": loc.get("section"),
        "from": start["label"],
        "distance_m": _round(meters),
        "steps": steps,
    }
