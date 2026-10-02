import copy
import os
from pathlib import Path
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from models.entities import Base, Setting, User, Product
from services.auth import hash_password, require_admin
from services.config import DEFAULTS, PACKAGES, secret, TYPICAL_CHOICES
from services.pricing import positive, rate


def make_session_factory(url=None):
    if url is None:
        folder = Path(__file__).resolve().parents[1] / "data"
        folder.mkdir(exist_ok=True)
        url = os.environ.get("DATABASE_URL", f"sqlite:///{folder / 'quotes.sqlite3'}")
    engine = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def sqlite_setup(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=10000")
            connection.execute("PRAGMA journal_mode=WAL")
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


def initialize(factory):
    with factory.begin() as db:
        for key, value in DEFAULTS.items():
            if db.get(Setting, key) is None:
                db.add(Setting(key=key, value=copy.deepcopy(value)))
        if db.scalar(select(User).limit(1)) is None:
            mode = secret("AUTH_MODE", "local")
            password = secret("BOOTSTRAP_ADMIN_PASSWORD")
            if mode == "password" and not password:
                raise ValueError("Set BOOTSTRAP_ADMIN_PASSWORD to create the first admin account.")
            if mode not in ("local", "password"):
                raise ValueError("AUTH_MODE must be local or password.")
            db.add(User(name=secret("BOOTSTRAP_ADMIN_NAME", "Local administrator"),
                        email=secret("BOOTSTRAP_ADMIN_EMAIL", "local@inspiredpots.local").lower(), role="Admin",
                        password_hash=hash_password(password) if password else ""))


def get_settings(db):
    return {r.key: copy.deepcopy(r.value) for r in db.scalars(select(Setting))}


def save_settings(db, user, settings):
    require_admin(user)
    for key in ("vat_rate", "deposit_percentage", "remote_commission_rate"):
        rate(settings[key])
    for key in ("private_booking_minimum", "studio_fee_inc_vat", "hourly_cost", "remote_hours", "private_hours",
                "mileage_rate", "fuel_price_per_litre", "private_fixed_commission", "private_fee_inc_vat", "amber_buffer"):
        positive(settings[key])
    if positive(settings["vehicle_mpg"]) <= 0 or int(settings["remote_staff"]) < 1 or int(settings["private_staff"]) < 1:
        raise ValueError("MPG and staff counts must be positive.")
    if positive(settings["remote_hours"]) <= 0 or positive(settings["private_hours"]) <= 0:
        raise ValueError("Dedicated staffing hours must be positive.")
    if settings["vehicle_method"] not in ("Mileage", "Fuel") or settings["private_commission_method"] not in ("Fixed", "Tiered"):
        raise ValueError("Invalid commercial method.")
    thresholds = [int(t["min_guests"]) for t in settings["private_tiers"]]
    if not thresholds or thresholds[0] != 1 or thresholds != sorted(set(thresholds)):
        raise ValueError("Commission tiers must start at 1 with unique increasing guest thresholds.")
    for t in settings["private_tiers"]:
        positive(t["amount"])
    for p in PACKAGES:
        positive(settings["package_defaults"][p])
        if settings["package_overrides"][p] is not None:
            positive(settings["package_overrides"][p])
    if not settings["origin_postcode"].strip():
        raise ValueError("An origin postcode is required.")
    for key in DEFAULTS:
        db.get(Setting, key).value = copy.deepcopy(settings[key])


def package_context(db, package_name, settings):
    if package_name not in PACKAGES:
        raise ValueError("Choose a standard package.")
    pieces = list(db.scalars(select(Product).where(Product.active.is_(True), Product.event_eligible.is_(True), Product.event_package == package_name)))
    retail = max(positive(settings["package_defaults"][package_name]),
                 max((positive(p.retail_price_inc_vat) for p in pieces), default=positive("0")))
    choices = [f"{p.product_title}" + (f" — {p.variant_title}" if p.variant_title != "Default Title" else "") for p in pieces]
    return {"name": package_name, "retail_inc_vat": str(retail), "override_ex_vat": settings["package_overrides"][package_name],
            "choices": choices or [TYPICAL_CHOICES[package_name] + " (indicative; final selection subject to availability)"],
            "source": "Indicative Shopify catalogue / configured safeguard (higher value)" if pieces else "Configured safeguard · catalogue not assigned",
            "variant_ids": [p.shopify_variant_id for p in pieces]}


def pricing_context(db, q):
    settings = get_settings(db)
    context = {"settings": settings, "package": package_context(db, q["package"], settings)}
    if q.get("upgrade_id"):
        p = db.get(Product, int(q["upgrade_id"]))
        if p is None or not p.active or not p.event_eligible or p.event_package != "Speciality":
            raise ValueError("The selected speciality upgrade is no longer eligible.")
        context["upgrade"] = {"id": p.id, "label": f"{p.product_title} — {p.variant_title}",
                              "retail_inc_vat": p.retail_price_inc_vat, "upgrade_amount": p.upgrade_amount}
    return context


def sync_products(db, user, rows):
    """Upsert only Shopify-owned fields; classification and notes always survive."""
    require_admin(user)
    remote_fields = ("shopify_product_id", "product_title", "variant_title", "sku", "retail_price_inc_vat", "inventory", "product_type", "active", "last_synced")
    seen = set()
    for row in rows:
        positive(row["retail_price_inc_vat"])
        vid = row["shopify_variant_id"]
        seen.add(vid)
        product = db.scalar(select(Product).where(Product.shopify_variant_id == vid))
        if product is None:
            product = Product(shopify_variant_id=vid, **{k: row[k] for k in remote_fields})
            db.add(product)
        else:
            for key in remote_fields:
                setattr(product, key, row[key])
    # This function must receive a complete, successfully fetched catalogue.
    for product in db.scalars(select(Product)):
        if product.shopify_variant_id not in seen:
            product.active = False


def assign_products(db, user, ids, package, eligible, upgrade, notes=None):
    require_admin(user)
    if package not in ["None", *PACKAGES, "Speciality"]:
        raise ValueError("Invalid package assignment.")
    amount = str(positive(upgrade))
    for pid in ids:
        product = db.get(Product, int(pid))
        if product is None:
            raise ValueError("Product no longer exists.")
        product.event_eligible, product.event_package, product.upgrade_amount = bool(eligible), package, amount
        if notes is not None:
            product.notes = notes
