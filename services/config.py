import os


DEFAULTS = {
    "vat_rate": "0.20", "deposit_percentage": "0.20", "private_booking_minimum": "250",
    "studio_fee_inc_vat": "5", "hourly_cost": "17", "remote_staff": 1, "remote_hours": "4",
    "private_staff": 1, "private_hours": "3", "origin_postcode": "NE46 1BH", "vehicle_method": "Mileage",
    "mileage_rate": "0.45", "fuel_price_per_litre": "1.50", "vehicle_mpg": "35",
    "remote_commission_enabled": True, "remote_commission_rate": "0.50", "private_commission_method": "Fixed",
    "private_fixed_commission": "25", "private_fee_inc_vat": "10", "amber_buffer": "1",
    "private_tiers": [{"min_guests": 1, "amount": "20"}, {"min_guests": 15, "amount": "30"}, {"min_guests": 25, "amount": "40"}],
    "package_defaults": {"Keepsakes": "15", "Everyday": "18", "Favourites": "25"},
    "package_overrides": {"Keepsakes": None, "Everyday": None, "Favourites": None},
    "terms": "Subject to availability and written booking confirmation. Finished pottery is glazed and fired after the event. Collection or delivery arrangements will be agreed when booking."
}
PACKAGES = ["Keepsakes", "Everyday", "Favourites"]
STATUSES = ["Draft", "Sent", "Won", "Lost", "Cancelled"]
TYPICAL_CHOICES = {"Keepsakes": "Tiles, coasters, ornaments and small decorations",
                   "Everyday": "Regular mugs, side plates and cereal bowls",
                   "Favourites": "Premium mugs, pasta bowls and dinner plates"}


def secret(name, default=""):
    if name in os.environ:
        return os.environ[name]
    try:
        import streamlit as st
        return str(st.secrets.get(name, default))
    except (FileNotFoundError, RuntimeError):
        return default
