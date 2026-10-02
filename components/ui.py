import hashlib
import json
from html import escape
import streamlit as st
import streamlit.components.v1 as components
from services.exports import currency, customer_view, email_text, printable_html
from services.pdf import generate_pdf
from services.quotes import customer_export_allowed


def heading(title, subtitle):
    st.title(title)
    st.caption(subtitle)


def pricing_status(result):
    status = result["pricing_status"]
    if status == "Below minimum viable price":
        from services.pricing import decimal
        st.error(f"**{status}** · under by {currency(decimal(result['protected_floor']) - decimal(result['total_ex_vat']))}")
    elif status == "Commission generated":
        st.success(f"**{status}**")
    else:
        st.warning(f"**{status}**")


def quote_summary(q, context, result):
    with st.container(border=True):
        st.markdown("### Your quote at a glance")
        st.markdown(f"**{escape(q['customer_name']) if q['customer_name'] else 'Your next event'}**")
        st.caption(f"{q['event_date']} · {q['guest_count']} painters")
        st.caption(q["destination_postcode"] if q["event_type"] == "Remote Event" else "Inspired Pots · Hexham · NE46 1BH")
        fee = q["event_type"] == "Private Studio Hire" and q["private_mode"] == "Event fee + pottery on the day"
        st.markdown("**Event fee + pottery on the day**" if fee else f"**{context['package']['name']} package**")
        if not fee:
            with st.expander("Included pottery choices"):
                st.caption(" · ".join(context["package"]["choices"]))
            if context.get("upgrade"):
                st.caption("Upgrade: " + context["upgrade"]["label"])
        st.divider()
        st.metric("Staff commission", currency(result["staff_commission"]))
        st.caption(result["commission_status"] + (" · earned after Won + deposit paid" if q["event_type"] == "Private Studio Hire" else " · earned when Won"))
        st.divider()
        st.metric("Customer price / painter · ex VAT", currency(result["price_per_person_ex_vat"]))
        a, b = st.columns(2)
        a.metric("Total · ex VAT", currency(result["total_ex_vat"]))
        b.metric("Total · inc VAT", currency(result["total_inc_vat"]))
        st.caption(f"VAT: {currency(result['vat_amount'])} · Deposit: {currency(result['deposit_amount'])}")
        st.divider()
        st.metric("Protected minimum · ex VAT", currency(result["protected_floor"]))
        pricing_status(result)


def export_controls(user, quote):
    try:
        customer_export_allowed(user, quote)
    except (ValueError, PermissionError) as error:
        st.warning(str(error))
        return
    v = customer_view(quote)
    st.success(f"Customer quote ready · {quote.quote_number}")
    a, b = st.columns(2)
    a.download_button("Download customer PDF", generate_pdf(v), file_name=quote.quote_number + ".pdf", mime="application/pdf", type="primary")
    b.download_button("Download printable page", printable_html(v), file_name=quote.quote_number + ".html", mime="text/html")
    with st.expander("Customer email & printable preview"):
        text = email_text(v)
        st.code(text, language=None)
        # Clipboard needs a user gesture. A selectable fallback remains available.
        payload = json.dumps(text).replace("<", "\\u003c")
        components.html(f"""<button id="copy" style="background:#267366;color:white;border:0;padding:12px 18px;border-radius:6px;cursor:pointer">Copy Email</button><span id="feedback" style="font:13px Arial;margin-left:10px"></span><script>document.getElementById('copy').onclick=async()=>{{try{{await navigator.clipboard.writeText({payload});document.getElementById('feedback').textContent='Copied';}}catch(e){{document.getElementById('feedback').textContent='Use the copy icon above or select the text.';}}}};</script>""", height=55)
        components.html(printable_html(v), height=720, scrolling=True)


def draft_hash(q, context):
    return hashlib.sha256(json.dumps([q, context], sort_keys=True).encode()).hexdigest()
