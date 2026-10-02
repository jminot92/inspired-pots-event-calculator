import pytest
from services import shopify, travel


def test_shopify_paginates_and_new_fields(monkeypatch):
    monkeypatch.setenv("SHOPIFY_SHOP", "test.myshopify.com")
    monkeypatch.setenv("SHOPIFY_ACCESS_TOKEN", "secret-never-print")
    calls = []
    def response(url, payload, headers):
        calls.append(payload["variables"]["after"])
        number = len(calls)
        return {"data": {"productVariants": {"nodes": [{"id": str(number), "title": "Default Title", "price": "15.00", "sku": None,
                  "inventoryQuantity": 2, "product": {"id": "p1", "title": "Mug", "productType": "Pottery", "status": "ACTIVE"}}],
                  "pageInfo": {"hasNextPage": number == 1, "endCursor": "cursor"}}}}
    monkeypatch.setattr(shopify, "post_json", response)
    rows = shopify.fetch_catalogue()
    assert calls == [None, "cursor"]
    assert len(rows) == 2
    assert "event_eligible" not in rows[0]


def test_shopify_partial_failure_raises_without_sync(monkeypatch):
    monkeypatch.setenv("SHOPIFY_SHOP", "test.myshopify.com")
    monkeypatch.setenv("SHOPIFY_ACCESS_TOKEN", "token")
    monkeypatch.setattr(shopify, "post_json", lambda *a: {"errors": [{"message": "Denied"}]})
    with pytest.raises(ValueError, match="rejected"):
        shopify.fetch_catalogue()


def test_routes_both_directions_not_double_outbound(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "token")
    calls = []
    def response(url, payload, headers):
        calls.append(payload)
        return {"routes": [{"distanceMeters": 16093.44 if len(calls) == 1 else 32186.88, "duration": "1800s" if len(calls) == 1 else "2400s"}]}
    monkeypatch.setattr(travel, "post_json", response)
    r = travel.calculate_travel("NE46 1BH", "NE1 1AA")
    assert len(calls) == 2
    assert calls[0]["origin"] == calls[1]["destination"]
    assert r["return_miles"] == "30"
    assert r["return_minutes"] == "70"


def test_missing_route_is_actionable(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "token")
    monkeypatch.setattr(travel, "post_json", lambda *a: {"routes": []})
    with pytest.raises(ValueError, match="No road route"):
        travel.calculate_travel("NE46 1BH", "INVALID")
