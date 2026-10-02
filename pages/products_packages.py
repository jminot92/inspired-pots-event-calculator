from datetime import datetime, timezone, timedelta
import pandas as pd
import streamlit as st
from sqlalchemy import select
from models.entities import Product, User
from services.config import PACKAGES
from services.shopify import fetch_catalogue
from services.database import assign_products, sync_products, get_settings, package_context
from services.pricing import decimal
from components.ui import heading


def render(factory, user):
    heading("Products & packages", "CURATED POTTERY CHOICES · INDICATIVE SHOPIFY CATALOGUE")
    st.warning("Shopify is a starting point, not a verified price list. Its catalogue may contain stale or placeholder prices. Check the pieces and package safeguards before quoting.")
    admin = user.role == "Admin"
    if st.button("Sync Shopify Products", disabled=not admin, type="primary"):
        try:
            with st.spinner("Fetching the complete Shopify catalogue…"):
                rows = fetch_catalogue()
            with factory.begin() as db:
                sync_products(db, db.get(User, user.id), rows)
            st.success(f"Synced {len(rows)} variants. Manual eligibility, packages, upgrades and notes preserved.")
        except (ValueError, PermissionError) as error:
            st.error(str(error))
    with factory() as db:
        products = list(db.scalars(select(Product).order_by(Product.product_title)))
        settings = get_settings(db)
        packages = [package_context(db, p, settings) for p in PACKAGES]
    a, b, c = st.columns(3)
    for col, p in zip((a, b, c), packages):
        with col.container(border=True):
            st.subheader(p["name"])
            st.metric("Protected pottery / painter", f"£{decimal(p['override_ex_vat']):.2f} ex VAT" if p["override_ex_vat"] is not None else f"£{decimal(p['retail_inc_vat']):.2f} inc VAT")
            st.caption("Reviewed override" if p["override_ex_vat"] is not None else p["source"])
            st.caption(f"{len(p['variant_ids'])} assigned active eligible variants")
    a, b, c, d = st.columns(4)
    search = a.text_input("Search product / variant / SKU").strip().lower()
    package = b.selectbox("Package", ["All", "None", *PACKAGES, "Speciality"])
    eligible = c.selectbox("Event eligible", ["All", "Yes", "No"])
    product_type = d.selectbox("Product type", ["All"] + sorted({p.product_type for p in products}))
    filtered = [p for p in products if (not search or search in f"{p.product_title} {p.variant_title} {p.sku}".lower())
                and (package == "All" or p.event_package == package) and (eligible == "All" or p.event_eligible == (eligible == "Yes"))
                and (product_type == "All" or p.product_type == product_type)]
    def review(p):
        flags = []
        if decimal(p.retail_price_inc_vat) <= 1:
            flags.append("Possible placeholder price")
        if datetime.fromisoformat(p.last_synced) < datetime.now(timezone.utc) - timedelta(days=30):
            flags.append("Sync older than 30 days")
        if not p.active:
            flags.append("Inactive")
        if p.inventory <= 0:
            flags.append("Stock needs checking")
        return "; ".join(flags) or "Price remains indicative"
    rows = [{"ID": p.id, "Product": p.product_title, "Variant": p.variant_title, "SKU": p.sku,
             "Retail inc VAT": f"£{decimal(p.retail_price_inc_vat):.2f}", "Stock": p.inventory,
             "Event eligible": p.event_eligible, "Package": p.event_package, "Upgrade ex VAT": f"£{decimal(p.upgrade_amount):.2f}",
             "Last synced": p.last_synced[:10], "Review": review(p), "Admin notes": p.notes if admin else ""} for p in filtered]
    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    else:
        st.info("No variants in this view. Sync Shopify to populate the catalogue; configured package safeguards work before sync.")
    if admin and filtered:
        with st.container(border=True):
            st.subheader("Batch assignment")
            ids = st.multiselect("Variants to update", [p.id for p in filtered], format_func=lambda i: next(f"{p.product_title} — {p.variant_title} ({p.sku or p.id})" for p in filtered if p.id == i))
            a, b, c = st.columns(3)
            target = a.selectbox("Assign package", ["None", *PACKAGES, "Speciality"])
            allow = b.checkbox("Event eligible", value=True)
            upgrade = c.number_input("Upgrade / painter · ex VAT", min_value=0.0, value=0.0)
            replace_notes = st.checkbox("Replace admin notes for these variants")
            notes = st.text_area("Admin notes", disabled=not replace_notes)
            if st.button("Save assignments", disabled=not ids):
                with factory.begin() as db:
                    assign_products(db, db.get(User, user.id), ids, target, allow, str(upgrade), notes if replace_notes else None)
                st.rerun()
    if not admin:
        st.caption("Only admins can sync products or change eligibility and package assignments.")
