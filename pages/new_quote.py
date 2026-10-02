import copy
import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from sqlalchemy import select
from models.entities import Quote, User, Product
from services.auth import can_edit
from services.database import get_settings, pricing_context
from services.pricing import calculate_quote, decimal, money, remove_vat
from services.quotes import save_quote
from services.travel import calculate_travel
from services.config import PACKAGES, STATUSES
from components.ui import heading, quote_summary, export_controls, draft_hash


def today():
    return datetime.now(ZoneInfo("Europe/London")).date()


def open_editor(quote=None, data=None):
    st.session_state.editor_nonce = uuid.uuid4().hex
    st.session_state.editor_id = quote.id if quote else None
    st.session_state.editor_version = quote.version if quote else None
    st.session_state.editor_data = copy.deepcopy(data if data is not None else quote.data if quote else {})
    st.session_state.pop("export_hash", None)
    st.session_state.pending_nav = "New Quote"


def render(factory, user):
    heading("Create something memorable", "EVENT QUOTING · INSPIRED POTS")
    if "editor_nonce" not in st.session_state:
        open_editor()
    seed = st.session_state.editor_data
    prefix = "q_" + st.session_state.editor_nonce + "_"
    def key(name):
        return prefix + name
    with factory() as db:
        settings = get_settings(db)
        existing = db.get(Quote, st.session_state.editor_id) if st.session_state.editor_id else None
        if existing and not can_edit(user, existing):
            st.error("This quote is not assigned to you.")
            return
        users = list(db.scalars(select(User).where(User.active.is_(True))))
        upgrades = list(db.scalars(select(Product).where(Product.active.is_(True), Product.event_eligible.is_(True), Product.event_package == "Speciality")))
    a, b, c = st.columns([1, 1.6, 1])
    customer_type = a.segmented_control("Customer type", ["Business", "Consumer"], default=seed.get("customer_type", "Business"), key=key("customer_type")) or "Business"
    event_type = b.segmented_control("Event type", ["Remote Event", "Private Studio Hire"], default=seed.get("event_type", "Remote Event"), key=key("event_type")) or "Remote Event"
    if c.button("Start a fresh quote", width="stretch"):
        open_editor()
        st.rerun()
    if existing:
        st.caption(f"{existing.quote_number} · Created {existing.created_at[:10]} · Version {st.session_state.editor_version}")
        if existing.data.get("override"):
            st.info(f"Recorded override by {existing.data['override']['user_name']}: {existing.data['override']['reason']}. Changes to pricing require new approval.")
    else:
        st.caption(f"New draft · Created {today()} · {user.name} · Quote number assigned on save")
    if customer_type == "Consumer":
        st.info("Consumer quotes currently use the same commercial rules as business quotes. Private consumer bookings have no staff commission preset.")
    left, right = st.columns([1.65, 1], gap="large")
    with left:
        with st.container(border=True):
            st.subheader("1 · Customer & event")
            customer = st.text_input("Customer / company", seed.get("customer_name", ""), key=key("customer"))
            x, y = st.columns(2)
            contact = x.text_input("Contact name", seed.get("contact_name", ""), key=key("contact"))
            email = y.text_input("Contact email", seed.get("contact_email", ""), key=key("email"))
            phone = x.text_input("Contact telephone", seed.get("contact_phone", ""), key=key("phone"))
            event_date = y.date_input("Event date", date.fromisoformat(seed["event_date"]) if seed.get("event_date") else today(), key=key("date"))
            guests = int(x.number_input("Number of painters", 1, 10000, int(seed.get("guest_count", 20)), key=key("guests")))
            status = y.selectbox("Quote status", STATUSES, index=STATUSES.index(seed.get("status", "Draft")), key=key("status"))
            if user.role == "Admin":
                ids = [u.id for u in users]
                labels = {u.id: u.name for u in users}
                salesperson = st.selectbox("Salesperson", ids, index=ids.index(seed.get("salesperson_id", user.id)) if seed.get("salesperson_id", user.id) in ids else 0, format_func=labels.get, key=key("salesperson"))
            else:
                salesperson = user.id
                st.caption(f"Salesperson: {user.name}")
        address, postcode, return_miles, return_minutes, confirmed = "", "", "0", "0", True
        route_data = None
        remote = event_type == "Remote Event"
        kind = "remote" if remote else "private"
        if remote:
            with st.container(border=True):
                st.subheader("2 · Travel to your customer")
                address = st.text_input("Event address", seed.get("destination_address", ""), key=key("address"))
                postcode = st.text_input("Event postcode", seed.get("destination_postcode", ""), key=key("postcode")).strip().upper()
                origin = existing.context["settings"]["origin_postcode"] if existing else settings["origin_postcode"]
                destination = ", ".join(filter(None, [address.strip(), postcode]))
                st.caption(f"Origin: {origin} · Travel time is paid in addition to event hours.")
                route_key = key("route")
                if st.button("Calculate road distance & time", key=key("calculate_route"), disabled=not postcode):
                    try:
                        with st.spinner("Checking outward and return road journeys…"):
                            route_data = calculate_travel(origin, destination)
                        route_data["return_miles"] = str(money(route_data["return_miles"]))
                        route_data["return_minutes"] = str(money(route_data["return_minutes"]))
                        st.session_state[route_key] = route_data
                        st.session_state[key("miles")] = float(route_data["return_miles"])
                        st.session_state[key("minutes")] = float(route_data["return_minutes"])
                    except ValueError as error:
                        st.error(str(error))
                x, y = st.columns(2)
                return_miles = str(x.number_input("Return road miles", min_value=0.0, value=float(seed.get("return_miles", 0)), step=1.0, key=key("miles")))
                return_minutes = str(y.number_input("Return journey minutes", min_value=0.0, value=float(seed.get("return_minutes", 0)), step=5.0, key=key("minutes")))
                route_data = st.session_state.get(route_key)
                auto = bool(route_data and route_data["destination"] == destination and route_data["origin"] == origin and decimal(route_data["return_miles"]) == decimal(return_miles) and decimal(route_data["return_minutes"]) == decimal(return_minutes))
                if auto:
                    confirmed = True
                    st.success(f"Road route checked · {float(route_data['one_way_miles']):.1f} miles / {float(route_data['one_way_minutes']):.0f} min one way · {float(return_miles):.1f} miles / {float(return_minutes):.0f} min return")
                else:
                    binding = f"{address}|{postcode}|{return_miles}|{return_minutes}"
                    saved_match = seed.get("travel_confirmed", False) and address == seed.get("destination_address") and postcode == seed.get("destination_postcode") and decimal(return_miles) == decimal(seed.get("return_miles", 0)) and decimal(return_minutes) == decimal(seed.get("return_minutes", 0))
                    confirmed = st.checkbox("I have checked these return travel figures", value=bool(saved_match), key=key("travel_checked_" + binding))
                    st.caption("Manual values are supported when Maps is unavailable. Changes to location or travel figures require confirmation again.")
                    route_data = {"source": "Manually verified return journey", "origin": origin, "destination": destination}
        with st.container(border=True):
            st.subheader("3 · Pottery & dedicated hosts" if remote else "2 · Private studio & pottery")
            private_mode = "Package pricing"
            if not remote:
                st.caption("Inspired Pots · Hexham · NE46 1BH. All private events take place outside normal opening hours.")
                private_mode = st.segmented_control("Private pricing model", ["Package pricing", "Event fee + pottery on the day"], default=seed.get("private_mode", "Package pricing"), key=key("private_mode")) or "Package pricing"
            fee_mode = not remote and private_mode == "Event fee + pottery on the day"
            package = st.selectbox("Pottery package", PACKAGES, index=PACKAGES.index(seed.get("package", "Everyday")), key=key("package"), disabled=fee_mode)
            upgrade_ids = [None] + [p.id for p in upgrades]
            upgrade_names = {p.id: f"{p.product_title} — {p.variant_title} (+£{decimal(p.upgrade_amount):.2f} ex VAT / painter)" for p in upgrades}
            upgrade_id = st.selectbox("Optional speciality upgrade · all painters", upgrade_ids, index=upgrade_ids.index(seed.get("upgrade_id")) if seed.get("upgrade_id") in upgrade_ids else 0, format_func=lambda i: upgrade_names.get(i, "No upgrade"), key=key("upgrade"), disabled=fee_mode)
            x, y = st.columns(2)
            staff = int(x.number_input("Dedicated staff", 1, 50, int(seed.get("staff_count", settings[kind + "_staff"])) if seed.get("event_type", event_type) == event_type else int(settings[kind + "_staff"]), key=key(kind + "_staff")))
            hours = str(y.number_input("Paid event hours / staff (travel excluded)" if remote else "Event duration · hours", min_value=0.25, max_value=240.0, value=float(seed.get("duration_hours", settings[kind + "_hours"])) if seed.get("event_type", event_type) == event_type else float(settings[kind + "_hours"]), step=0.25, key=key(kind + "_hours")))
            st.caption("Remote default: 4 paid hours includes prep, packing and unpacking; around 2.5–3 hours on site." if remote else "Dedicated staffing is always included in the protected minimum.")
            with st.expander("Additional internal costs · ex VAT"):
                extras = st.data_editor(pd.DataFrame(seed.get("extra_costs", []), columns=["description", "amount_ex_vat"]), num_rows="dynamic", key=key("extras"), width="stretch",
                                        column_config={"description": st.column_config.TextColumn("Description"), "amount_ex_vat": st.column_config.TextColumn("Amount · ex VAT")})
                st.caption("Parking, tolls, delivery, accommodation or special materials. Internal only.")
        extra_costs = [{"description": str(row["description"] or ""), "amount_ex_vat": str(row["amount_ex_vat"] or "0")} for row in extras.fillna("").to_dict("records") if row["description"] or row["amount_ex_vat"]]
        q = {"customer_type": customer_type, "event_type": event_type, "customer_name": customer, "contact_name": contact, "contact_email": email,
             "contact_phone": phone, "event_date": event_date.isoformat(), "guest_count": guests, "status": status, "salesperson_id": salesperson,
             "destination_address": address, "destination_postcode": postcode, "return_miles": return_miles, "return_minutes": return_minutes,
             "travel_confirmed": confirmed, "travel": route_data, "package": package, "upgrade_id": None if fee_mode else upgrade_id,
             "staff_count": staff, "duration_hours": hours, "private_mode": private_mode, "extra_costs": extra_costs}
        refresh = False
        if existing:
            refresh = st.checkbox("Refresh pricing assumptions from current settings & indicative catalogue", key=key("refresh"))
            st.caption("Saved quotes retain their original commercial snapshot unless you refresh or change the pottery package/upgrade.")
        try:
            with factory() as db:
                context = copy.deepcopy(existing.context) if existing and not refresh and package == existing.data["package"] and q["upgrade_id"] == existing.data.get("upgrade_id") else pricing_context(db, q)
            st.caption("Pottery values: " + context["package"]["source"] + ". Shopify is indicative and may contain outdated or placeholder prices; review package safeguards in Settings.")
            provisional = calculate_quote({**q, "selling_mode": "Per person", "selling_amount": "0", "deposit_paid": False}, context)
        except (ValueError, ArithmeticError) as error:
            st.error(f"Check your amounts: {error}")
            return
        with st.container(border=True):
            st.subheader("4 · Customer price" if remote else "3 · Customer price")
            st.caption("Edit either price. VAT is calculated separately and never earns commission.")
            price_suffix = kind + "_" + private_mode
            pp_key, total_key, basis_key = key(price_suffix + "_pp"), key(price_suffix + "_total"), key(price_suffix + "_basis")
            if any(k not in st.session_state for k in (basis_key, pp_key, total_key)):
                use_seed = seed and seed.get("event_type") == event_type and seed.get("private_mode", "Package pricing") == private_mode
                initial = decimal(seed["selling_amount"]) if use_seed else (money(remove_vat(context["settings"]["private_fee_inc_vat"], context["settings"]["vat_rate"])) if fee_mode else money(decimal(provisional["protected_floor"]) / guests * decimal("1.20")))
                basis = seed.get("selling_mode", "Per person") if use_seed else "Per person"
                st.session_state[basis_key] = basis
                st.session_state[pp_key] = float(initial if basis == "Per person" else money(initial / guests))
                st.session_state[total_key] = float(money(initial * guests) if basis == "Per person" else initial)
            basis = st.session_state[basis_key]
            if basis == "Per person":
                st.session_state[total_key] = float(money(decimal(st.session_state[pp_key]) * guests))
            else:
                st.session_state[pp_key] = float(money(decimal(st.session_state[total_key]) / guests))
            def edit_price(mode):
                st.session_state[basis_key] = mode
            x, y = st.columns(2)
            x.number_input("Price per painter · ex VAT", min_value=0.0, step=1.0, key=pp_key, on_change=edit_price, args=("Per person",))
            y.number_input("Total event price · ex VAT", min_value=0.0, step=10.0, key=total_key, on_change=edit_price, args=("Total event",))
            q["selling_mode"] = st.session_state[basis_key]
            q["selling_amount"] = str(st.session_state[pp_key] if q["selling_mode"] == "Per person" else st.session_state[total_key])
            st.caption("Price basis: " + q["selling_mode"] + ". Per-person display is rounded when the total event price is the basis.")
            if fee_mode:
                st.info("This quote covers the private hire fee only. Attendees pay for their pottery on the day; pottery revenue is excluded from this quote.")
            with st.expander("Deposit administration & notes"):
                requested = st.checkbox("Deposit requested", value=bool(seed.get("deposit_requested_date")), key=key("deposit_requested"))
                requested_date = st.date_input("Deposit requested date", date.fromisoformat(seed["deposit_requested_date"]) if seed.get("deposit_requested_date") else today(), key=key("requested_date"), disabled=not requested)
                deposit_paid = st.checkbox("Deposit paid", value=bool(seed.get("deposit_paid", False)), key=key("deposit_paid"))
                paid_date = st.date_input("Deposit paid date", date.fromisoformat(seed["deposit_paid_date"]) if seed.get("deposit_paid_date") else today(), key=key("paid_date"), disabled=not deposit_paid)
                customer_notes = st.text_area("Customer-facing notes", seed.get("customer_notes", ""), key=key("customer_notes"))
                notes = st.text_area("Internal notes · never exported", seed.get("notes", ""), key=key("internal_notes"))
            q.update(deposit_paid=deposit_paid, deposit_paid_date=paid_date.isoformat() if deposit_paid else None,
                     deposit_requested_date=requested_date.isoformat() if requested else None, customer_notes=customer_notes, notes=notes)
    result = calculate_quote(q, context)
    # Streamlit cleans up widgets when navigating to another screen. Preserve
    # their canonical draft values independently so a return can rebuild them.
    st.session_state.editor_data = copy.deepcopy(q)
    with right:
        st.markdown('<span id="quote-summary-anchor"></span>', unsafe_allow_html=True)
        if remote and not confirmed:
            st.info("Travel pending · minimum and commission are provisional until the return journey is checked.")
        quote_summary(q, context, result)
        if user.role == "Admin":
            with st.expander("Internal Pricing Breakdown"):
                st.table(pd.DataFrame([{"Cost": k.replace("_", " ").title(), "Ex VAT": f"£{decimal(v):,.2f}"} for k, v in result["costs"].items()]))
                st.caption(f"Protected floor £{result['protected_floor']} · Selling price £{result['total_ex_vat']} · Commissionable surplus £{result['commissionable_surplus']} · Staff commission £{result['staff_commission']}")
                if not remote:
                    st.caption(f"Private minimum booking charge: £{context['settings']['private_booking_minimum']} ex VAT (applied as a minimum, not an additional fee).")
        override_reason = ""
        if user.role == "Admin" and decimal(result["total_ex_vat"]) < decimal(result["protected_floor"]):
            with st.expander("Admin Override"):
                override_reason = st.text_area("Reason for approving this below-minimum price", key=key("override_reason"))
                st.caption("Approval records your user, timestamp, reason and the exact economic terms.")
        save, generate = st.columns(2)
        save_clicked = save.button("Save quote", width="stretch", type="primary")
        generate_clicked = generate.button("Generate Customer Quote", width="stretch")
        if save_clicked or generate_clicked:
            try:
                with factory.begin() as db:
                    fresh_user = db.get(User, user.id)
                    saved = save_quote(db, fresh_user, q, st.session_state.editor_id, st.session_state.editor_version, override_reason, refresh)
                st.session_state.editor_id, st.session_state.editor_version = saved.id, saved.version
                st.session_state.editor_data = copy.deepcopy(saved.data)
                st.session_state.export_hash = draft_hash(q, context) if generate_clicked else None
                existing = saved
                st.success(f"Saved {saved.quote_number}")
            except (ValueError, PermissionError) as error:
                st.error(str(error))
        if existing and st.session_state.get("export_hash") == draft_hash(q, context):
            export_controls(user, existing)
