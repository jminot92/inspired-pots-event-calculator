from urllib.parse import urlencode
from services.config import secret
from services.http import post_json
from services.pricing import decimal


def directions_link(origin_postcode, destination):
    return "https://www.google.com/maps/dir/?" + urlencode({
        "api": "1", "origin": f"Inspired Pots, Hexham, {origin_postcode}, UK",
        "destination": destination.strip(), "travelmode": "driving"})


def _leg(origin, destination, api_key):
    response = post_json("https://routes.googleapis.com/directions/v2:computeRoutes",
                         {"origin": {"address": origin + ", UK"}, "destination": {"address": destination + ", UK"}, "travelMode": "DRIVE", "routingPreference": "TRAFFIC_UNAWARE"},
                         {"X-Goog-Api-Key": api_key, "X-Goog-FieldMask": "routes.distanceMeters,routes.duration"})
    try:
        route = response["routes"][0]
        return decimal(route["distanceMeters"]) / decimal("1609.344"), decimal(route["duration"].removesuffix("s")) / 60
    except (KeyError, IndexError, TypeError, ValueError):
        raise ValueError("No road route was found. Check the postcode/address or enter a manually verified return journey.") from None


def calculate_travel(origin, destination):
    key = secret("GOOGLE_MAPS_API_KEY")
    if not key:
        raise ValueError("Set GOOGLE_MAPS_API_KEY with Routes API enabled, or use manually checked travel figures.")
    outward_miles, outward_minutes = _leg(origin, destination, key)
    back_miles, back_minutes = _leg(destination, origin, key)
    return {"one_way_miles": format(outward_miles, "f"), "one_way_minutes": format(outward_minutes, "f"),
            "return_miles": format(outward_miles + back_miles, "f"), "return_minutes": format(outward_minutes + back_minutes, "f"),
            "origin": origin, "destination": destination, "source": "Google Routes · both directions"}
