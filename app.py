from pathlib import Path
import time
import streamlit as st
from sqlalchemy import select
from models.entities import User
from services.auth import check_password
from services.config import secret
from services.pricing import decimal, money
from services.database import make_session_factory, initialize
from pages import new_quote, saved_quotes, products_packages, settings, calculator

st.set_page_config(page_title="Inspired Pots · Event Calculator", page_icon="🏺", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>
.block-container{padding-top:2rem;padding-bottom:3rem;max-width:1500px}
h1,h2,h3{letter-spacing:-.035em}h1{font-family:Georgia,serif;font-weight:500!important}
[data-testid=stMetricValue]{font-weight:650;color:#236d70;font-size:clamp(1.2rem,2vw,2rem)}
[data-testid=stSidebar]{border-right:1px solid #deded6}
[data-testid=stVerticalBlockBorderWrapper]{border-radius:14px}
.stButton button,.stDownloadButton button{border-radius:8px;min-height:42px}
@media(min-width:1000px){[data-testid=stColumn]:has(#quote-summary-anchor){position:sticky;top:5rem;align-self:flex-start}}
</style>""", unsafe_allow_html=True)


@st.cache_resource
def database(schema_version=2):
    factory = make_session_factory()
    initialize(factory)
    return factory


def authenticate(factory):
    mode = secret("AUTH_MODE", "local")
    if mode == "local":
        if st.get_option("server.address") not in ("127.0.0.1", "localhost", "::1"):
            st.error("Local setup access requires a loopback server address. Set AUTH_MODE=password before sharing or hosting.")
            st.stop()
        with factory() as db:
            user = db.scalar(select(User).where(User.role == "Admin", User.active.is_(True)).order_by(User.id))
        st.sidebar.warning("Local setup mode · admin access. Enable password mode before sharing or hosting.")
        return user
    if mode != "password":
        st.error("AUTH_MODE must be local or password.")
        st.stop()
    uid = st.session_state.get("authenticated_user")
    if uid:
        with factory() as db:
            user = db.get(User, uid)
        if user and user.active:
            if st.sidebar.button("Sign out"):
                st.session_state.clear()
                st.rerun()
            return user
        st.session_state.pop("authenticated_user", None)
    st.title("Inspired Pots")
    st.caption("Sign in to build your next event quote.")
    with st.form("login"):
        email = st.text_input("Username" if secret("APP_MODE", "simple") == "simple" else "Email")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Sign in", type="primary")
    if submit:
        if time.monotonic() < st.session_state.get("login_retry_at", 0):
            st.error("Please wait a few seconds before trying again.")
        else:
            with factory() as db:
                user = db.scalar(select(User).where(User.email == email.strip().lower(), User.active.is_(True)))
            if user and check_password(password, user.password_hash):
                st.session_state.authenticated_user = user.id
                st.rerun()
            st.session_state.login_retry_at = time.monotonic() + 3
            st.error("Username or password was not recognised." if secret("APP_MODE", "simple") == "simple" else "Email or password was not recognised.")
    st.stop()


try:
    factory = database(2)
except ValueError as error:
    st.error(str(error))
    st.stop()
user = authenticate(factory)
if user is None:
    st.error("No active administrator is available.")
    st.stop()
if secret("APP_MODE", "simple") == "simple":
    if st.session_state.pop("simple_apply_route", False):
        route = st.session_state.simple_route
        st.session_state.simple_one_way_miles = float(decimal(route["return_miles"]) / 2)
        st.session_state.simple_one_way_minutes = float(decimal(route["return_minutes"]) / 2)
    calculator.render(factory, user, allow_save=False)
    st.stop()
st.sidebar.markdown("## Inspired Pots")
st.sidebar.caption("EVENT QUOTING STUDIO")
st.sidebar.markdown(f"**{user.name}** · {user.role}")
navigation = ["New Quote", "Saved Quotes", "Products & Packages"] + (["Settings"] if user.role == "Admin" else [])
if st.session_state.get("pending_nav"):
    st.session_state.nav = st.session_state.pop("pending_nav")
page = st.sidebar.radio("Workspace", navigation, key="nav", label_visibility="collapsed")
st.sidebar.divider()
st.sidebar.caption("Protect the pottery.\nPrice the experience.\nSee your commission.")
renderers = {"New Quote": new_quote.render, "Saved Quotes": saved_quotes.render, "Products & Packages": products_packages.render, "Settings": settings.render}
renderers[page](factory, user)
