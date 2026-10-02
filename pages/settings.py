import copy
import pandas as pd
import streamlit as st
from sqlalchemy import select
from models.entities import User, Audit
from services.auth import require_admin, hash_password
from services.config import PACKAGES, secret
from services.database import get_settings, save_settings
from services.pricing import decimal
from components.ui import heading


def render(factory, user):
    require_admin(user)
    heading("Settings", "COMMERCIAL ASSUMPTIONS & ACCESS · ADMIN ONLY")
    with factory() as db:
        original = get_settings(db)
        users = list(db.scalars(select(User).order_by(User.name)))
    s = copy.deepcopy(original)
    general, staffing, travel, commission, packages = st.tabs(["General", "Staffing", "Travel", "Commission", "Packages"])
    def number(key, label, minimum=0.0, percentage=False):
        value = float(decimal(original[key]) * (100 if percentage else 1))
        chosen = st.number_input(label, min_value=minimum, value=value, max_value=100.0 if percentage else None, key="setting_" + key)
        s[key] = str(decimal(chosen) / 100) if percentage else str(chosen)
    with general:
        a, b = st.columns(2)
        with a:
            number("vat_rate", "VAT rate · %", percentage=True)
            number("studio_fee_inc_vat", "Studio / consumables fee per painter · inc VAT")
            number("private_booking_minimum", "Private minimum booking charge · ex VAT")
        with b:
            number("deposit_percentage", "Deposit · %", percentage=True)
            number("private_fee_inc_vat", "Suggested private hire fee / attendee · inc VAT")
            number("amber_buffer", "Remote amber band above floor · ex VAT")
        s["terms"] = st.text_area("Customer quote terms", original["terms"], height=150)
        st.caption("The £250 booking minimum is an ex-VAT floor. The suggested £10 private fee is inc VAT; the app still checks it against staffing and consumables.")
    with staffing:
        number("hourly_cost", "Staff hourly cost · ex VAT")
        a, b = st.columns(2)
        with a:
            s["remote_staff"] = st.number_input("Remote default staff", min_value=1, value=int(original["remote_staff"]))
            number("remote_hours", "Remote paid base hours per staff member", minimum=0.25)
        with b:
            s["private_staff"] = st.number_input("Private default staff", min_value=1, value=int(original["private_staff"]))
            number("private_hours", "Private duration · hours", minimum=0.25)
        st.caption("Remote travel hours are additional. Private studio bookings always have dedicated out-of-hours staffing.")
    with travel:
        s["origin_postcode"] = st.text_input("Studio origin postcode", original["origin_postcode"])
        s["vehicle_method"] = st.radio("Vehicle cost method", ["Mileage", "Fuel"], index=["Mileage", "Fuel"].index(original["vehicle_method"]), horizontal=True)
        number("mileage_rate", "Mileage rate · £ per return mile")
        number("fuel_price_per_litre", "Fuel price · £ per litre")
        number("vehicle_mpg", "Vehicle MPG · UK imperial gallons", minimum=0.01)
    with commission:
        s["remote_commission_enabled"] = st.checkbox("Remote commission enabled", value=original["remote_commission_enabled"])
        number("remote_commission_rate", "Remote commission rate · % of ex-VAT surplus", percentage=True)
        s["private_commission_method"] = st.radio("Private business commission method", ["Fixed", "Tiered"], index=["Fixed", "Tiered"].index(original["private_commission_method"]), horizontal=True)
        number("private_fixed_commission", "Fixed private booking commission · £")
        tiers = st.data_editor(pd.DataFrame(original["private_tiers"]), num_rows="dynamic", hide_index=True, key="commission_tiers",
                               column_config={"min_guests": st.column_config.NumberColumn("From this many painters", min_value=1, step=1), "amount": st.column_config.TextColumn("Commission · £")})
        s["private_tiers"] = [{"min_guests": int(r["min_guests"]), "amount": str(r["amount"])} for r in tiers.dropna().to_dict("records")]
        st.caption("One private method is active at a time. Private business commission is earned only after Won + deposit paid. Consumer private commission is zero for this MVP.")
    with packages:
        st.warning("Shopify is indicative. Package safeguards protect against an incomplete catalogue. Defaults use the higher of this safeguard and assigned catalogue retail values. A reviewed ex-VAT override replaces that value.")
        for name in PACKAGES:
            with st.container(border=True):
                st.subheader(name)
                s["package_defaults"][name] = str(st.number_input("Retail safeguard / painter · inc VAT", min_value=0.0, value=float(original["package_defaults"][name]), key="fallback_" + name))
                use_override = st.checkbox("Use reviewed protected pottery override", value=original["package_overrides"][name] is not None, key="use_override_" + name)
                override = st.number_input("Protected pottery / painter · ex VAT", min_value=0.0, value=float(original["package_overrides"][name] or 0), key="override_" + name, disabled=not use_override)
                s["package_overrides"][name] = str(override) if use_override else None
    if st.button("Save commercial settings", type="primary"):
        try:
            with factory.begin() as db:
                save_settings(db, db.get(User, user.id), s)
                changed = {k: {"before": original[k], "after": s[k]} for k in original if original[k] != s[k]}
                db.add(Audit(user_id=user.id, action="settings_changed", detail=changed))
            st.success("Settings saved. Existing quotes keep their stored assumptions unless explicitly refreshed.")
        except (ValueError, PermissionError, ArithmeticError) as error:
            st.error(str(error))
    st.divider()
    st.subheader("Integration status")
    st.write("Shopify credentials: " + ("Configured" if secret("SHOPIFY_SHOP") and secret("SHOPIFY_ACCESS_TOKEN") else "Not configured"))
    st.write("Google Routes key: " + ("Configured" if secret("GOOGLE_MAPS_API_KEY") else "Not configured"))
    st.caption("Use environment variables or .streamlit/secrets.toml. Credentials are never stored in the quote database or displayed here.")
    st.subheader("Users & access")
    st.dataframe(pd.DataFrame([{"Name": u.name, "Email": u.email, "Role": u.role, "Active": u.active} for u in users]), hide_index=True, width="stretch")
    with st.form("add_user", clear_on_submit=True):
        st.markdown("**Add an account**")
        name = st.text_input("Name")
        email = st.text_input("Email")
        password = st.text_input("Initial password · at least 12 characters", type="password")
        role = st.selectbox("Role", ["Staff", "Admin"])
        if st.form_submit_button("Create user"):
            try:
                with factory.begin() as db:
                    require_admin(db.get(User, user.id))
                    if not name.strip() or "@" not in email:
                        raise ValueError("Name and a valid email are required.")
                    if db.scalar(select(User).where(User.email == email.strip().lower())):
                        raise ValueError("An account with this email already exists.")
                    db.add(User(name=name.strip(), email=email.strip().lower(), password_hash=hash_password(password), role=role))
                    db.add(Audit(user_id=user.id, action="user_created", detail={"email": email.strip().lower(), "role": role}))
                st.success("Account created.")
            except (ValueError, PermissionError) as error:
                st.error(str(error))
    with st.expander("Reset password or deactivate an account"):
        ids = [u.id for u in users]
        chosen = st.selectbox("Account", ids, format_func=lambda i: next(u.email for u in users if u.id == i))
        new_password = st.text_input("New password", type="password")
        if st.button("Reset password"):
            try:
                encoded = hash_password(new_password)
                with factory.begin() as db:
                    require_admin(db.get(User, user.id))
                    db.get(User, chosen).password_hash = encoded
                    db.add(Audit(user_id=user.id, action="password_reset", detail={"user_id": chosen}))
                st.success("Password reset.")
            except (ValueError, PermissionError) as error:
                st.error(str(error))
        if st.button("Toggle active status", disabled=chosen == user.id):
            with factory.begin() as db:
                require_admin(db.get(User, user.id))
                account = db.get(User, chosen)
                account.active = not account.active
                db.add(Audit(user_id=user.id, action="user_active_changed", detail={"user_id": chosen, "active": account.active}))
            st.rerun()
