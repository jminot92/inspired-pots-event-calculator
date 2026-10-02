from pathlib import Path
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest


def labelled(collection, label):
    return next(w for w in collection if w.label == label)


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'ui.sqlite3'}")
    monkeypatch.setenv("AUTH_MODE", "local")
    monkeypatch.setenv("APP_MODE", "advanced")
    st.cache_resource.clear()
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30).run()
    assert not at.exception
    return at


def test_pages_render_and_customer_export_flow(app):
    labelled(app.text_input, "Customer / company").set_value("UI Test Customer")
    labelled(app.text_input, "Event postcode").set_value("NE1 1AA")
    labelled(app.number_input, "Return road miles").set_value(30.0)
    labelled(app.number_input, "Return journey minutes").set_value(60.0)
    labelled(app.number_input, "Dedicated staff").set_value(2)
    app.run()
    assert not app.exception
    labelled(app.checkbox, "I have checked these return travel figures").check()
    labelled(app.number_input, "Price per painter · ex VAT").set_value(30.0)
    app.run()
    assert not app.exception
    assert next(m.value for m in app.metric if m.label == "Protected minimum · ex VAT") == "£566.83"
    assert next(m.value for m in app.metric if m.label == "Staff commission") == "£16.59"
    labelled(app.button, "Generate Customer Quote").click().run()
    assert not app.exception
    assert any("Customer quote ready" in message.value for message in app.success)
    for page in ["Saved Quotes", "Products & Packages", "Settings"]:
        labelled(app.radio, "Workspace").set_value(page).run()
        assert not app.exception
    labelled(app.radio, "Workspace").set_value("New Quote").run()
    assert not app.exception
    assert labelled(app.text_input, "Customer / company").value == "UI Test Customer"
    assert labelled(app.number_input, "Price per painter · ex VAT").value == 30


def test_total_and_per_person_stay_in_sync(app):
    labelled(app.number_input, "Total event price · ex VAT").set_value(800.0).run()
    assert labelled(app.number_input, "Price per painter · ex VAT").value == 40
    labelled(app.number_input, "Price per painter · ex VAT").set_value(30.0).run()
    assert labelled(app.number_input, "Total event price · ex VAT").value == 600
    labelled(app.number_input, "Number of painters").set_value(25).run()
    assert labelled(app.number_input, "Total event price · ex VAT").value == 750
    assert not app.exception


def test_private_modes_and_deposit_booking_lifecycle(app):
    labelled(app.get("button_group"), "Event type").set_value("Private Studio Hire").run()
    assert not app.exception
    assert next(m.value for m in app.metric if m.label == "Protected minimum · ex VAT") == "£434.33"
    labelled(app.text_input, "Customer / company").set_value("Private Booking Test")
    labelled(app.get("button_group"), "Private pricing model").set_value("Event fee + pottery on the day").run()
    assert not app.exception
    assert next(m.value for m in app.metric if m.label == "Protected minimum · ex VAT") == "£250.00"
    assert next(m.value for m in app.metric if m.label == "Customer price / painter · ex VAT") == "£8.33"
    labelled(app.number_input, "Price per painter · ex VAT").set_value(15.0)
    labelled(app.selectbox, "Quote status").set_value("Won")
    labelled(app.checkbox, "Deposit paid").check()
    app.run()
    labelled(app.button, "Generate Customer Quote").click().run()
    assert not app.exception
    assert any("Customer quote ready" in message.value for message in app.success)
    assert any("earned after Won + deposit paid" in message.value for message in app.caption)


def test_staff_password_login_hides_admin_pages(tmp_path, monkeypatch):
    from services.database import make_session_factory, initialize
    from services.auth import hash_password
    from models.entities import User
    url = f"sqlite:///{tmp_path / 'staff-ui.sqlite3'}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("APP_MODE", "advanced")
    monkeypatch.setenv("AUTH_MODE", "local")
    factory = make_session_factory(url)
    initialize(factory)
    with factory.begin() as db:
        db.add(User(name="Staff", email="staff@example.com", role="Staff", password_hash=hash_password("test staff password")))
    monkeypatch.setenv("AUTH_MODE", "password")
    st.cache_resource.clear()
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30).run()
    assert not at.exception
    labelled(at.text_input, "Email").set_value("staff@example.com")
    labelled(at.text_input, "Password").set_value("test staff password")
    labelled(at.button, "Sign in").click().run()
    assert not at.exception
    assert "Settings" not in labelled(at.radio, "Workspace").options
    assert not any(e.label == "Internal Pricing Breakdown" for e in at.expander)
    assert not any(w.label == "Salesperson" for w in at.selectbox)
