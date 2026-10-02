import re
import time
from models.entities import timestamp
from services.config import secret
from services.http import post_json
from services.pricing import positive

CATALOGUE_QUERY = """
query EventCatalogue($after: String) {
  productVariants(first: 100, after: $after) {
    nodes {
      id title sku price inventoryQuantity
      product { id title productType status }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""


def fetch_catalogue():
    shop = secret("SHOPIFY_SHOP").strip().lower()
    token = secret("SHOPIFY_ACCESS_TOKEN")
    version = secret("SHOPIFY_API_VERSION", "2026-07")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*\.myshopify\.com", shop):
        raise ValueError("Set SHOPIFY_SHOP to your shop.myshopify.com hostname.")
    if not token:
        raise ValueError("Set SHOPIFY_ACCESS_TOKEN with read_products and read_inventory access.")
    if not re.fullmatch(r"20\d{2}-(01|04|07|10)", version):
        raise ValueError("Set a valid Shopify API version, for example 2026-07.")
    rows, after, seen = [], None, set()
    synced = timestamp()
    while True:
        response = None
        for retry in range(4):
            response = post_json(f"https://{shop}/admin/api/{version}/graphql.json", {"query": CATALOGUE_QUERY, "variables": {"after": after}}, {"X-Shopify-Access-Token": token})
            errors = response.get("errors", [])
            if errors and all(e.get("extensions", {}).get("code") == "THROTTLED" for e in errors) and retry < 3:
                time.sleep(2 ** retry)
                continue
            if errors:
                raise ValueError("Shopify rejected the catalogue query. Check API version and read_products/read_inventory scopes.")
            break
        try:
            page = response["data"]["productVariants"]
            for node in page["nodes"]:
                product = node["product"]
                rows.append({"shopify_variant_id": node["id"], "shopify_product_id": product["id"],
                             "product_title": product["title"], "variant_title": node["title"], "sku": node.get("sku") or "",
                             "retail_price_inc_vat": str(positive(node["price"])), "inventory": node.get("inventoryQuantity") or 0,
                             "product_type": product["productType"], "active": product["status"] == "ACTIVE", "last_synced": synced})
            if not page["pageInfo"]["hasNextPage"]:
                return rows
            after = page["pageInfo"]["endCursor"]
            if not after or after in seen:
                raise ValueError("Shopify pagination did not advance. No local products have been changed.")
            seen.add(after)
        except (KeyError, TypeError):
            raise ValueError("Shopify returned an incomplete catalogue. No local products have been changed.") from None
