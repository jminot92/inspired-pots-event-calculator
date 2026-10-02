"""Session-only package choices; never changes the Shopify catalogue."""
import json
from pathlib import Path
from services.pricing import positive, money, remove_vat, rate

PACKAGES = ("Keepsakes", "Everyday", "Favourites")


def load_catalogue():
    return json.loads((Path(__file__).resolve().parents[1] / "data" / "pottery_catalogue.json").read_text(encoding="utf-8"))


def reviewed_price_inc_vat(displayed_ex_vat, original_inc_vat, vat_rate):
    """Keep source pennies intact when a rounded display value wasn't edited."""
    value = positive(displayed_ex_vat)
    if value == money(remove_vat(original_inc_vat, vat_rate)):
        return str(original_inc_vat)
    return str(money(value * (1 + rate(vat_rate))))


def selected_package(name, items, choices):
    selected = [item for item in items if choices.get(item["id"], {}).get("offer")]
    if not selected:
        return None
    prices = [positive(choices[item["id"]].get("price", item["price_inc_vat"])) for item in selected]
    if min(prices) <= 0:
        raise ValueError("Selected pottery needs a price greater than £0.")
    return {"name": name, "retail_inc_vat": str(max(prices)), "override_ex_vat": None,
            "choices": [item["title"] + (" — " + item["variant"] if item["variant"] != "Default Title" else "") for item in selected],
            "source": "Highest selected pottery price · reviewed session selection",
            "variant_ids": [item["id"] for item in selected]}
