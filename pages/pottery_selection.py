import hashlib
import pandas as pd
import streamlit as st
from services.pottery_selection import load_catalogue, selected_package, reviewed_price_inc_vat, PACKAGES
from services.exports import currency
from services.config import DEFAULTS
from services.database import get_settings
from services.pricing import remove_vat, money


def render(factory):
    with factory() as db:
        settings = get_settings(db)
    vat = settings["vat_rate"]
    st.markdown('<style>.block-container{max-width:2000px}</style>', unsafe_allow_html=True)
    catalogue = load_catalogue()
    items = catalogue["items"]
    selections = st.session_state.setdefault("pottery_selections", {name: {} for name in PACKAGES})
    st.subheader("Choose the pottery for each package")
    st.write("Tick the pieces you want to offer. The highest selected price sets that package’s pottery value per painter.")
    st.caption(f"Prices are ex VAT, converted from the indicative Shopify retail catalogue · loaded {catalogue['checked_date']}. You can correct a price in the table. These choices last for this session.")
    search = st.text_input("Find pottery", placeholder="Search a shape, size or product", key="pottery_search").strip().lower()
    filtered = [item for item in items if search in f"{item['title']} {item['variant']} {item['type']}".lower()]
    filtered.sort(key=lambda item: (item["title"].lower(), item["variant"].lower()))
    signature = hashlib.sha256(search.encode()).hexdigest()[:12]
    for column, name in zip(st.columns(3, gap="medium"), PACKAGES):
        with column.container(border=True):
            st.markdown(f"### {name}")
            choices = selections[name]
            rows = [{"Offer": bool(choices.get(item["id"], {}).get("offer")),
                     "Pottery": item["title"] + (" · " + item["variant"] if item["variant"] != "Default Title" else ""),
                     "Price": float(money(remove_vat(choices.get(item["id"], {}).get("price", item["price_inc_vat"]), vat)))} for item in filtered]
            if rows:
                edited = st.data_editor(pd.DataFrame(rows), hide_index=True, width="stretch", height=440,
                    disabled=["Pottery"], key=f"pottery_editor_{name}_{signature}_ex",
                    column_config={"Offer": st.column_config.CheckboxColumn("Offer", width=48),
                                   "Pottery": st.column_config.TextColumn("Pottery", width=160),
                                   "Price": st.column_config.NumberColumn("£ ex VAT", min_value=0.01, format="£%.2f", step=0.5, width=82, required=True)})
                for item, row in zip(filtered, edited.to_dict("records")):
                    original = choices.get(item["id"], {}).get("price", item["price_inc_vat"])
                    choices[item["id"]] = {"offer": bool(row["Offer"]), "price": reviewed_price_inc_vat(row["Price"], original, vat)}
            else:
                st.info("No pottery matches this search.")
            try:
                package = selected_package(name, items, choices)
                if package:
                    st.metric("Pottery value / painter · ex VAT", currency(remove_vat(package["retail_inc_vat"], vat)))
                    st.caption(f"{len(package['choices'])} choices · highest selected price")
                else:
                    st.metric("Pottery value / painter · ex VAT", currency(remove_vat(settings["package_defaults"][name], vat)))
                    st.caption("Default value · select pieces to use the highest selected price instead.")
            except ValueError as error:
                st.error(str(error))
