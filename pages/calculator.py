"""Small first version: event inputs, protected minimum, sale and commission."""
import copy
import streamlit as st
from services.database import get_settings, pricing_context, package_context
from services.pricing import calculate_quote, decimal, money, pricing_health
from services.exports import currency
from services.travel import directions_link
from services.calculations import list_calculations, get_calculation, save_calculation
from models.entities import User
from pages import pottery_selection
from services.pottery_selection import load_catalogue, selected_package


def choose_package(name):
    st.session_state.simple_package = name


def render(factory, user, allow_save=False):
    # Keep calculator widget values while the pottery view is displayed.
    for key in list(st.session_state):
        if key.startswith("simple_") and not key.startswith("simple_choose_"):
            st.session_state[key] = st.session_state[key]
    st.markdown("""<style>
    .block-container{max-width:1760px;padding-left:2rem;padding-right:2rem}
    [data-testid=stAppViewContainer],[data-testid=stHeader]{background:#f4f1e8}
    [data-testid=stCaptionContainer],[data-testid=stCaptionContainer] p{color:#4d6169;opacity:1}
    [data-testid=stNumberInput] input,[data-testid=stTextInput] input{background:#fff;color:#1a2b33}
    [data-testid=stWidgetLabel] p{font-weight:600;color:#1a2b33}
    [data-baseweb=input],[data-baseweb=select]>div{background:#fff;border:1px solid #bbcaca;border-radius:8px}
    [data-baseweb=input]:focus-within{border-color:#3b9d9c;box-shadow:0 0 0 3px #3b9d9c22}
    .st-key-event-details,.st-key-summary-charge,.st-key-summary-commission,.st-key-summary-minimum{background:#fff;border-radius:14px}
    .st-key-event-details{border:1px solid #c4d4d3;box-shadow:0 3px 14px #1a2b3308}
    .st-key-customer-price{background:#3b9d9c;border:2px solid #3b9d9c;border-radius:14px;box-shadow:0 6px 20px #3b9d9c24;padding:20px 22px;gap:12px}
    .st-key-summary-charge,.st-key-summary-commission,.st-key-summary-minimum{padding:20px 22px;gap:12px}
    [data-testid=stColumn]:has(#quote-summary-anchor)>[data-testid=stVerticalBlock]{gap:20px}
    [data-testid=stElementContainer]:has(#quote-summary-anchor){display:none}
    .st-key-customer-price [data-testid=stMarkdownContainer] p,
    .st-key-customer-price [data-testid=stWidgetLabel] p,
    .st-key-customer-price [data-testid=stCaptionContainer],
    .st-key-customer-price [data-testid=stCaptionContainer] p{color:#fff;opacity:1}
    .st-key-customer-price [data-testid=stAlert] p{color:#1a2b33}
    .st-key-customer-price [data-testid=stAlertContainer]{background:#fff2de;border:1px solid #ffb25a;color:#1a2b33}
    .st-key-enquiry-source{background:#236d70;border:1px solid #ffffff80;border-radius:10px;padding:14px 16px;gap:6px}
    .st-key-enquiry-source [data-testid=stWidgetLabel] p{color:#fff;font-size:1.1rem;font-weight:750}
    .pricing-health{border:1px solid #c4d4d3;border-radius:10px;padding:14px 16px;margin-bottom:8px;background:#f4f1e8;color:#1a2b33}
    .pricing-health strong{display:block;font-size:1.1rem;margin:4px 0}
    .pricing-health.caution{background:#fff2de;border-color:#ffb25a}
    .pricing-health.low{background:#fff1f4;border-color:#f9c1ce}
    .pricing-health.healthy{background:#e3f3f1;border-color:#3b9d9c}
    .st-key-customer-price [data-testid=stNumberInput] input{font-size:32px;font-weight:750;color:#1a2b33;background:#fff;padding:10px 14px}
    .st-key-customer-price [data-baseweb=input]{border:2px solid #ffb25a;background:#fff;min-height:66px}
    .st-key-customer-price [data-testid=stNumberInput] button{background:#ffe1bc;color:#1a2b33;min-width:44px}
    .st-key-customer-price [data-testid=stNumberInput] button:hover{background:#ffb25a}
    .st-key-summary-charge{border-left:5px solid #3b9d9c}
    .st-key-summary-commission{border-left:5px solid #f9c1ce;background:#fff1f4}
    .st-key-summary-minimum{border-left:5px solid #1a2b33}
    .st-key-summary-charge [data-testid=stMetricValue]{font-size:2.4rem;color:#236d70}
    .st-key-summary-commission [data-testid=stMetricValue]{color:#1a2b33}
    .st-key-summary-minimum [data-testid=stMetricValue]{color:#1a2b33}
    .pottery-card{border:1px solid #c4d4d3;border-radius:9px;background:#faf8f2;padding:10px 12px;color:#1a2b33}
    .pottery-card.selected{border:2px solid #3b9d9c;background:#e3f3f1;padding:9px 11px}
    .pottery-card strong{display:block;font-size:.9rem}
    .pottery-card span{display:block;font-size:1.3rem;font-weight:700;margin-top:3px}
    .st-key-pottery-picker button{width:100%;min-height:84px;border-radius:10px;padding:12px;text-align:left;justify-content:flex-start}
    .st-key-pottery-picker button p{white-space:pre-line;font-weight:650;font-size:1rem}
    .st-key-pottery-picker button[kind=primary]{background:#3b9d9c;border:2px solid #3b9d9c;color:#fff}
    .st-key-pottery-picker button[kind=primary] p{color:#fff}
    .st-key-pottery-picker button[kind=secondary]{background:#faf8f2;color:#1a2b33;border:1px solid #c4d4d3}
    .st-key-pottery-picker button:hover{border-color:#3b9d9c;box-shadow:0 0 0 2px #3b9d9c20}
    .st-key-calculator-nav{margin-bottom:8px}
    .st-key-calculator-nav [data-testid=stButtonGroup]{background:#e7efec;padding:10px;border:1px solid #c4d4d3;border-radius:14px}
    .st-key-calculator-nav [role=radiogroup]{gap:10px!important}
    .st-key-calculator-nav button{min-height:52px;font-weight:650;border:1px solid #bbcaca!important;border-radius:8px!important;padding:12px 24px;margin:0!important;flex:1 1 0}
    .st-key-calculator-nav button p{font-weight:600}
    .st-key-calculator-nav [role=radio][aria-checked=true],.st-key-calculator-nav button[aria-pressed=true]{background:#3b9d9c!important;color:#fff!important;border-color:#3b9d9c!important}
    .st-key-calculator-nav [role=radio][aria-checked=true] p,.st-key-calculator-nav button[aria-pressed=true] p{color:#fff!important}
    @media(max-width:600px){.block-container{padding-left:1rem;padding-right:1rem}.st-key-calculator-nav [role=radiogroup]{gap:6px!important}.st-key-calculator-nav button{padding:10px 8px}.st-key-customer-price,.st-key-summary-charge,.st-key-summary-commission,.st-key-summary-minimum{padding:18px}}
    </style>""", unsafe_allow_html=True)
    if not st.session_state.get("simple_private_rules_v2"):
        for key, old_default in (("simple_staff_Private Studio Hire", 2), ("simple_duration_Private Studio Hire", 3.0)):
            if st.session_state.get(key) == old_default:
                del st.session_state[key]
        st.session_state.simple_private_rules_v2 = True
    if not st.session_state.get("simple_staff_defaults_v1"):
        for key in ("simple_staff_Remote Event", "simple_staff_Private Studio Hire"):
            if st.session_state.get(key) == 2:
                del st.session_state[key]
        st.session_state.simple_staff_defaults_v1 = True
    if st.session_state.pop("simple_reset", False):
        for key in list(st.session_state):
            if key.startswith("simple_"):
                del st.session_state[key]
    pending = st.session_state.pop("simple_open", None) if allow_save else None
    if pending:
        with factory() as db:
            row = get_calculation(db, user, pending)
        q, c = row.inputs, row.context
        st.session_state.simple_loaded_id, st.session_state.simple_loaded_version = row.id, row.version
        st.session_state.simple_loaded_context = copy.deepcopy(c)
        st.session_state.simple_name, st.session_state.simple_event, st.session_state.simple_guests = row.name, q["event_type"], q["guest_count"]
        st.session_state.simple_package, st.session_state.simple_private_mode = q["package"], q["private_mode"]
        st.session_state.simple_generated_enquiry = q.get("commission_enabled", False)
        st.session_state.simple_one_way_miles = float(decimal(q["return_miles"]) / 2)
        st.session_state.simple_one_way_minutes = float(decimal(q["return_minutes"]) / 2)
        st.session_state.simple_destination = q.get("destination", "")
        st.session_state["simple_price_" + q["event_type"] + q["private_mode"]] = float(q["selling_amount"])
        if q["event_type"] == "Private Studio Hire" and q["private_mode"] == "Event fee + pottery on the day":
            st.session_state.simple_hire_total = float(decimal(q["selling_amount"]) * (q["guest_count"] if q["selling_mode"] == "Per person" else 1))
        st.session_state["simple_staff_" + q["event_type"]] = q["staff_count"]
        st.session_state["simple_duration_" + q["event_type"]] = float(q["duration_hours"])
        st.session_state.simple_studio_fee, st.session_state.simple_hourly = float(c["settings"]["studio_fee_inc_vat"]), float(c["settings"]["hourly_cost"])
        st.session_state["simple_use_pottery_" + q["package"]] = c["package"].get("override_ex_vat") is not None
        if c["package"].get("override_ex_vat") is not None:
            st.session_state["simple_pottery_" + q["package"]] = float(c["package"]["override_ex_vat"])
    st.title("Inspired Pots · Event calculator")
    st.caption("Inspired Pots · Find a sensible event price and see your commission.")
    with st.container(key="calculator-nav"):
        event = st.segmented_control("Calculator navigation", ["Remote Event", "Private Studio Hire", "Pottery selection"], default="Remote Event", selection_mode="single", required=True, width="stretch", label_visibility="collapsed", key="simple_event")
    if event == "Pottery selection":
        pottery_selection.render(factory)
        return
    remote = event == "Remote Event"
    with factory() as db:
        settings = get_settings(db)
        packages = [package_context(db, name, settings) for name in ("Keepsakes", "Everyday", "Favourites")]
    selected = st.session_state.get("pottery_selections", {})
    if selected:
        items = load_catalogue()["items"]
        for i, item in enumerate(packages):
            try:
                chosen = selected_package(item["name"], items, selected.get(item["name"], {}))
            except ValueError as error:
                st.error(f"Review {item['name']} in Pottery selection: {error}")
                return
            if chosen:
                packages[i] = chosen
    settings.update(remote_staff=1, private_staff=1, private_hours="4", private_pricing_model="Pottery target and surplus")
    loaded_context = st.session_state.get("simple_loaded_context") if allow_save else None
    if loaded_context:
        settings = copy.deepcopy(loaded_context["settings"])
        st.caption("Reopened calculation · original pricing assumptions retained")
    left, right = st.columns([1.25, 1], gap="large")
    with right:
        st.markdown('<span id="quote-summary-anchor"></span>', unsafe_allow_html=True)
    with left:
        with st.container(border=True, key="event-details"):
            st.markdown("### Event details")
            mode = "Package pricing"
            if not remote:
                mode = st.radio("Private studio price", ["Package pricing", "Event fee + pottery on the day"], horizontal=False, key="simple_private_mode")
                st.caption("Private hire includes dedicated staff and exclusive use of the studio. Package pricing also includes pottery.")
            fee_mode = not remote and mode == "Event fee + pottery on the day"
            a, b = st.columns(2)
            guests = a.number_input("Painters", min_value=1, max_value=10000, value=20, step=1, key="simple_guests")
            if fee_mode:
                package = "Everyday"  # Internal context only; pottery is excluded from the fee.
            else:
                package = st.session_state.get("simple_package", "Everyday")
                st.caption("Pottery value per painter · ex VAT (pottery only)")
                with st.container(key="pottery-picker"):
                    for column, item in zip(st.columns(3), packages):
                        amount = decimal(item["retail_inc_vat"]) / (1 + decimal(settings["vat_rate"])) if item.get("override_ex_vat") is None else decimal(item["override_ex_vat"])
                        column.button(f"{item['name']}  \n{currency(amount)}", key="package_pick_" + item["name"], type="primary" if item["name"] == package else "secondary", width="stretch", on_click=choose_package, args=(item["name"],))
                st.caption("Indicative pottery values; the full event price also covers staffing and event costs.")
            return_miles, return_minutes, destination = "0", "0", ""
            if remote:
                st.markdown("**Travel to the event**")
                destination = st.text_input("Destination / postcode", placeholder="Venue, address or postcode", key="simple_destination")
                st.link_button("Open directions from Inspired Pots", directions_link(settings["origin_postcode"], destination), disabled=not destination.strip(), width="stretch")
                st.caption("Check the route in Google Maps, then enter the distance and estimated time below.")
                a, b = st.columns(2)
                miles = a.number_input("Miles to destination · one way", min_value=0.0, step=1.0, value=0.0, key="simple_one_way_miles")
                minutes = b.number_input("Estimated travel time · minutes one way", min_value=0.0, step=5.0, value=0.0, key="simple_one_way_minutes")
                return_miles, return_minutes = str(decimal(miles) * 2), str(decimal(minutes) * 2)
                st.caption(f"Return allowance: {decimal(return_miles):g} miles / {decimal(return_minutes):g} minutes.")
        with right:
            with st.container(border=True, key="customer-price"):
                with st.container(key="enquiry-source"):
                    generated = st.toggle("Staff-generated enquiry", value=False, key="simple_generated_enquiry")
                    st.caption("ON · Staff commission applies to the surplus." if generated else "OFF · Inbound enquiry — no staff commission.")
                st.markdown("**Set your studio hire fee**" if fee_mode else "**Set your customer price**")
                if fee_mode:
                    price = st.number_input("Studio hire charge · ex VAT", min_value=0.0, value=200.0, step=10.0, format="%.2f", key="simple_hire_total")
                    st.caption("Total charge for exclusive studio hire. Pottery is paid separately on the day.")
                else:
                    price = st.number_input("Customer price per painter · ex VAT", min_value=0.0, value=28.0 if remote else 30.0, step=1.0, format="%.2f", key="simple_price_" + event + mode)
                    st.caption("Adjust this price to see the charge and commission update below.")
                if remote and (decimal(return_miles) == 0 or decimal(return_minutes) == 0):
                    st.warning("Add both travel distance and estimated time to include travel in this price.")
        q = {"customer_type": "Business", "event_type": event, "guest_count": guests, "package": package, "upgrade_id": None,
             "staff_count": settings["remote_staff"] if remote else settings["private_staff"],
             "duration_hours": settings["remote_hours"] if remote else settings["private_hours"], "private_mode": mode,
             "return_miles": return_miles, "return_minutes": return_minutes, "extra_costs": [], "selling_mode": "Total" if fee_mode else "Per person",
             "selling_amount": str(price), "status": "Draft", "deposit_paid": False, "destination": destination}
        q["commission_enabled"] = generated
        with factory() as db:
            context = copy.deepcopy(loaded_context) if loaded_context and loaded_context["package"]["name"] == package else pricing_context(db, q)
        context["settings"].update(private_pricing_model="Pottery target and surplus")
        chosen_package = next(item for item in packages if item["name"] == package)
        selection_signature = (chosen_package["retail_inc_vat"], tuple(chosen_package["variant_ids"])) if chosen_package["source"].startswith("Highest selected") else None
        signature_key = "simple_selection_signature_" + package
        if st.session_state.get(signature_key) != selection_signature:
            st.session_state["simple_use_pottery_" + package] = False
            st.session_state.pop("simple_pottery_" + package, None)
            st.session_state[signature_key] = selection_signature
        if chosen_package["source"].startswith("Highest selected"):
            context["package"] = copy.deepcopy(chosen_package)
        with st.expander("Check pricing assumptions"):
            st.caption("These values are for this calculation. Shopify is only indicative; check the pottery value yourself.")
            c = copy.deepcopy(context)
            default_pottery = context["package"].get("override_ex_vat")
            if default_pottery is None:
                default_pottery = decimal(context["package"]["retail_inc_vat"]) / (1 + decimal(settings["vat_rate"]))
            if not fee_mode and not c["package"]["source"].startswith("Highest selected"):
                custom_pottery = st.checkbox("Use a reviewed pottery value", value=context["package"].get("override_ex_vat") is not None, key="simple_use_pottery_" + package)
                pottery = st.number_input("Protected pottery / painter · ex VAT", min_value=0.0, value=float(money(default_pottery)), key="simple_pottery_" + package, disabled=not custom_pottery)
                c["package"]["override_ex_vat"] = str(pottery) if custom_pottery else None
                st.caption("Default protects the higher of the configured package safeguard and indicative assigned catalogue values.")
            elif not fee_mode:
                st.caption("Pottery value comes from the highest selected price. Change pieces or review their prices in Pottery selection.")
            studio_fee = st.number_input("Consumables / painter · inc VAT", min_value=0.0, value=float(settings["studio_fee_inc_vat"]), key="simple_studio_fee")
            c["settings"]["studio_fee_inc_vat"] = str(studio_fee)
            a, b = st.columns(2)
            staff = a.number_input("Staff", min_value=1, value=int(q["staff_count"]), key="simple_staff_" + event)
            duration = b.number_input("Paid event hours / staff", min_value=0.25, value=float(q["duration_hours"]), step=0.25, key="simple_duration_" + event)
            q["staff_count"], q["duration_hours"] = staff, str(duration)
            hourly = st.number_input("Hourly staff cost · £", min_value=0.0, value=float(settings["hourly_cost"]), key="simple_hourly")
            c["settings"]["hourly_cost"] = str(hourly)
            st.caption(f"VAT {decimal(settings['vat_rate']) * 100:g}% · {'Mileage £' + settings['mileage_rate'] + ' / mile' if settings['vehicle_method'] == 'Mileage' else 'Fuel method'} · Remote commission {decimal(settings['remote_commission_rate']) * 100:g}% · Private commission 50% of surplus")
            if mode == "Event fee + pottery on the day":
                st.caption("Pottery is paid for separately on the day and is excluded from this event fee.")
        result = calculate_quote(q, c)
        health = pricing_health(result["total_ex_vat"], result["protected_floor"], result["staff_commission"])
        if fee_mode:
            st.caption("Pottery chosen on the day: aim for £250 total pottery sales (inc VAT), separate from the studio hire fee.")
        if allow_save:
            with st.container(border=True):
                name = st.text_input("Calculation name", placeholder="e.g. Acme team event", key="simple_name")
                a, b = st.columns(2)
                if a.button("Save calculation", type="primary", width="stretch"):
                    try:
                        with factory.begin() as db:
                            row = save_calculation(db, db.get(User, user.id), name, q, c, st.session_state.get("simple_loaded_id"), st.session_state.get("simple_loaded_version"))
                        st.session_state.simple_loaded_id, st.session_state.simple_loaded_version = row.id, row.version
                        st.session_state.simple_loaded_context = copy.deepcopy(c)
                        st.success("Calculation saved.")
                    except (ValueError, PermissionError) as error:
                        st.error(str(error))
                if b.button("New calculation", width="stretch"):
                    st.session_state.simple_reset = True
                    st.rerun()
    with right:
        with st.container(border=True, key="summary-charge"):
            st.metric("Customer charge · ex VAT", currency(result["total_ex_vat"]))
            st.caption(("Studio hire only · " if fee_mode else f"{currency(result['price_per_person_ex_vat'])} per painter ex VAT · ") + f"{currency(result['total_inc_vat'])} total inc VAT (VAT {currency(result['vat_amount'])})")
            colour = "low" if health["status"] == "Below minimum" else "caution" if health["status"] in ("Close to break-even", "Low price") else "healthy"
            st.markdown(f'<div class="pricing-health {colour}">Pricing health<strong>{health["status"]}</strong>{health["guidance"]}</div>', unsafe_allow_html=True)
            st.caption(f"Studio headroom after commission: {currency(health['retained'])} ex VAT · {decimal(health['margin']) * 100:.2f}% of the charge. Based on protected values, not net profit.")
            with st.expander("What makes a healthy price?"):
                st.write("After protected costs and any staff commission: below £0 = Below minimum; under 5% of the charge = Close to break-even; 5–15% = Low price; 15–25% = Good pricing; 25% or more = Strong pricing.")
                st.caption("Working guide for quote value, rather than a required selling price. Pottery is protected at its retail value; rent and other overheads are not separately calculated.")
        if generated:
            with st.container(border=True, key="summary-commission"):
                st.metric("Staff commission", currency(result["staff_commission"]))
                st.caption("Potential commission. Private business bookings earn this after confirmation and deposit payment." if not remote else "Potential commission, earned when the booking is won. VAT is excluded.")
        with st.container(border=True, key="summary-minimum"):
            st.metric("Minimum to charge · ex VAT", currency(result["protected_floor"]))
            st.caption(f"Minimum per painter: {currency(decimal(result['protected_floor']) / guests)} ex VAT")
            with st.expander("How the minimum is calculated"):
                labels = {"pottery": "Protected pottery", "consumables": "Consumables", "event_labour": "Event staff", "travel_labour": "Travel staff", "vehicle": "Vehicle"}
                for key, label in labels.items():
                    if remote or key not in ("travel_labour", "vehicle"):
                        st.write(f"{label}: {currency(result['costs'][key])}")
                if not remote:
                    st.caption("Studio hire protects consumables and staff. Pottery is paid separately on the day." if fee_mode else "Private packages protect pottery, consumables and staff. Staff-generated enquiries earn commission on half the surplus above these costs.")
    st.caption("Shopify prices are indicative. This is an internal price check; confirm pottery values and travel before quoting a customer.")
    if allow_save:
        with st.expander("Saved calculations"):
            with factory() as db:
                rows = list_calculations(db, user)
            if rows:
                by_id = {row.id: row for row in rows}
                chosen = st.selectbox("Choose a calculation", list(by_id), format_func=lambda i: f"{by_id[i].name} · {by_id[i].updated_at[:10]}")
                if st.button("Reopen calculation"):
                    st.session_state.simple_open = chosen
                    st.rerun()
            else:
                st.caption("Your saved price checks will appear here.")

