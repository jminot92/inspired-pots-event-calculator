from datetime import date
import pandas as pd
import streamlit as st
from sqlalchemy import select
from models.entities import Quote, User, Commission, Audit
from services.quotes import list_quotes, save_quote, duplicate_data, set_commission_paid
from services.pricing import decimal
from services.exports import currency
from pages.new_quote import open_editor
from components.ui import heading, export_controls


def date_filter(label, key):
    enabled = st.checkbox(label, key=key + "_enabled")
    return st.date_input(label + " range", value=(date(2026, 1, 1), date.today()), key=key, disabled=not enabled) if enabled else None


def in_range(day, selection):
    return not selection or (len(selection) == 2 and selection[0] <= date.fromisoformat(day[:10]) <= selection[1])


def render(factory, user):
    heading("Saved quotes", "YOUR EVENTS, BOOKINGS & COMMISSION")
    with factory() as db:
        quotes = list_quotes(db, user)
        names = {u.id: u.name for u in db.scalars(select(User))}
        commissions = {c.quote_id: c for c in db.scalars(select(Commission))}
    with st.container(border=True):
        search = st.text_input("Search customer, contact or quote number", key="saved_search").lower().strip()
        a, b, c, d = st.columns(4)
        salesperson = a.selectbox("Salesperson", ["All"] + sorted({names[q.salesperson_id] for q in quotes}), key="filter_salesperson")
        status = b.selectbox("Status", ["All", "Draft", "Sent", "Won", "Lost", "Cancelled"], key="filter_status")
        customer_type = c.selectbox("Customer type", ["All", "Business", "Consumer"], key="filter_customer")
        event_type = d.selectbox("Event type", ["All", "Remote Event", "Private Studio Hire"], key="filter_event")
        a, b = st.columns(2)
        with a:
            events = date_filter("Filter event dates", "filter_event_dates")
        with b:
            created = date_filter("Filter created dates", "filter_created_dates")
    filtered = [q for q in quotes if (not search or search in " ".join([q.quote_number, q.data["customer_name"], q.data["contact_name"]]).lower())
                and (salesperson == "All" or names[q.salesperson_id] == salesperson)
                and (status == "All" or q.data["status"] == status)
                and (customer_type == "All" or q.data["customer_type"] == customer_type)
                and (event_type == "All" or q.data["event_type"] == event_type)
                and in_range(q.data["event_date"], events) and in_range(q.created_at, created)]
    a, b, c = st.columns(3)
    a.metric("Quotes in view", len(filtered))
    b.metric("Quoted value · ex VAT", currency(sum((decimal(q.result["total_ex_vat"]) for q in filtered), decimal("0"))))
    c.metric("Won events", sum(q.data["status"] == "Won" for q in filtered))
    rows = [{"Quote ID": q.quote_number, "Created": q.created_at[:10], "Event date": q.data["event_date"], "Customer": q.data["customer_name"],
             "Customer type": q.data["customer_type"], "Event type": q.data["event_type"], "Guests": q.data["guest_count"], "Salesperson": names[q.salesperson_id],
             "Quote ex VAT": currency(q.result["total_ex_vat"]), "Quote inc VAT": currency(q.result["total_inc_vat"]),
             "Staff commission": currency(q.result["staff_commission"]), "Status": q.data["status"]} for q in filtered]
    if filtered:
        selection = st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True, on_select="rerun", selection_mode="single-row", key="quotes_table")
        # Selection opens full customer details and actions below the table.
        chosen_index = selection.selection.rows[0] if selection.selection.rows else 0
        chosen = filtered[min(chosen_index, len(filtered) - 1)]
        with st.container(border=True):
            st.subheader(f"{chosen.quote_number} · {chosen.data['customer_name']}")
            st.caption(f"{chosen.data['event_date']} · {chosen.data['guest_count']} painters · {chosen.data['event_type']} · Created by {names.get(chosen.created_by, 'Unknown')}")
            st.write(f"Contact: {chosen.data['contact_name']} · {chosen.data['contact_email']} · {chosen.data['contact_phone']}")
            st.write(f"Price: {currency(chosen.result['total_ex_vat'])} ex VAT / {currency(chosen.result['total_inc_vat'])} inc VAT")
            if chosen.data.get("notes"):
                st.caption("Internal notes: " + chosen.data["notes"])
            a, b = st.columns(2)
            if a.button("Open & edit full quote", key=f"edit_{chosen.id}"):
                open_editor(chosen)
                st.rerun()
            if b.button("Duplicate quote", key=f"duplicate_{chosen.id}"):
                open_editor(data=duplicate_data(chosen, user.id))
                st.rerun()
            status_cols = st.columns(4)
            for col, target in zip(status_cols, ["Sent", "Won", "Lost", "Cancelled"]):
                if col.button("Mark " + target, key=f"status_{chosen.id}_{target}", disabled=target == chosen.data["status"]):
                    try:
                        with factory.begin() as db:
                            save_quote(db, db.get(User, user.id), {**chosen.data, "status": target}, chosen.id, chosen.version)
                        st.rerun()
                    except (ValueError, PermissionError) as error:
                        st.error(str(error))
            if st.button("Generate Customer Quote", key=f"export_{chosen.id}"):
                st.session_state.saved_export_id = chosen.id
            if st.session_state.get("saved_export_id") == chosen.id:
                export_controls(user, chosen)
            if user.role == "Admin":
                with st.expander("Quote audit trail"):
                    with factory() as db:
                        audits = list(db.scalars(select(Audit).where(Audit.quote_id == chosen.id).order_by(Audit.id.desc())))
                    st.dataframe(pd.DataFrame([{"Timestamp UTC": a.at, "User": names.get(a.user_id, a.user_id), "Action": a.action, "Detail": str(a.detail)} for a in audits]), hide_index=True, width="stretch")
    else:
        st.info("No quotes match these filters. Create your first quote or adjust the filters.")
    st.divider()
    st.subheader("Staff commission")
    st.caption("Uses the salesperson and event date filters above. Remote: Won. Private business: Won + deposit paid. Lost/cancelled bookings do not earn commission.")
    commission_quotes = [q for q in quotes if (salesperson == "All" or names[q.salesperson_id] == salesperson) and in_range(q.data["event_date"], events)]
    report = [{"Quote": q.quote_number, "Customer": q.data["customer_name"], "Event": q.data["event_type"], "Event date": q.data["event_date"],
               "Salesperson": names[q.salesperson_id], "Staff commission": currency(commissions[q.id].amount), "Commission status": commissions[q.id].status,
               "Earned date": (commissions[q.id].earned_date or "")[:10], "Paid date": (commissions[q.id].paid_date or "")[:10]} for q in commission_quotes if q.id in commissions]
    if report:
        st.dataframe(pd.DataFrame(report), hide_index=True, width="stretch")
        a, b, c = st.columns(3)
        for col, label in zip((a, b, c), ("Potential", "Earned", "Paid")):
            col.metric(label, currency(sum((decimal(commissions[q.id].amount) for q in commission_quotes if q.id in commissions and commissions[q.id].status == label), decimal("0"))))
    if user.role == "Admin":
        eligible = [q for q in commission_quotes if q.id in commissions and commissions[q.id].status in ("Earned", "Paid") and decimal(commissions[q.id].amount) > 0]
        if eligible:
            chosen_id = st.selectbox("Commission administration", [q.id for q in eligible], format_func=lambda i: next(q.quote_number for q in eligible if q.id == i))
            paid = commissions[chosen_id].status == "Paid"
            if st.button("Reopen paid commission" if paid else "Mark commission Paid"):
                try:
                    with factory.begin() as db:
                        set_commission_paid(db, db.get(User, user.id), chosen_id, paid=not paid)
                    st.rerun()
                except (ValueError, PermissionError) as error:
                    st.error(str(error))
