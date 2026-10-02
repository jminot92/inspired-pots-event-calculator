from pathlib import Path
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest
from models.entities import Calculation
from services.calculations import save_calculation, get_calculation


def labelled(widgets, label):
    return next(w for w in widgets if w.label == label)


@pytest.fixture
def simple_app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'simple.sqlite3'}")
    monkeypatch.setenv("AUTH_MODE", "local")
    monkeypatch.setenv("APP_MODE", "simple")
    st.cache_resource.clear()
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30).run()
    assert not at.exception
    return at


def test_simple_calculator_spec_and_hidden_saving(simple_app):
    app = simple_app
    labelled(app.toggle, "Staff-generated enquiry").set_value(True).run()
    assert not any("PDF" in w.label or "Customer Quote" in w.label for w in app.button)
    assert not any(w.label == "Workspace" for w in app.radio)
    assert labelled(app.number_input, "Staff").value == 1
    labelled(app.number_input, "Staff").set_value(2)
    labelled(app.checkbox, "Use a reviewed pottery value").check().run()
    labelled(app.number_input, "Protected pottery / painter · ex VAT").set_value(12.5)
    labelled(app.number_input, "Miles to destination · one way").set_value(15.0)
    labelled(app.number_input, "Estimated travel time · minutes one way").set_value(30.0)
    labelled(app.text_input, "Destination / postcode").set_value("NE1 1AA")
    app.run()
    assert [m.label for m in app.metric] == ["Customer charge · ex VAT", "Staff commission", "Minimum to charge · ex VAT"]
    assert next(m.value for m in app.metric if m.label == "Minimum to charge · ex VAT") == "£516.83"
    assert next(m.value for m in app.metric if m.label == "Staff commission") == "£21.59"
    assert not any(w.label in ("Save calculation", "Reopen calculation") for w in app.button)
    assert not any(w.label == "Calculation name" for w in app.text_input)
    assert all(any(w.label.startswith(name) for w in app.button) for name in ("Keepsakes", "Everyday", "Favourites"))


def test_simple_private_and_assumptions(simple_app):
    app = simple_app
    labelled(app.toggle, "Staff-generated enquiry").set_value(True).run()
    labelled(app.get("button_group"), "Calculator navigation").set_value("Private Studio Hire").run()
    assert not app.exception
    assert labelled(app.number_input, "Staff").value == 1
    assert next(m.value for m in app.metric if m.label == "Minimum to charge · ex VAT") == "£451.33"
    labelled(app.radio, "Private studio price").set_value("Event fee + pottery on the day").run()
    assert not any(w.label == "Pottery package" for w in app.selectbox)
    assert not any(w.label.startswith("Keepsakes") for w in app.button)
    labelled(app.number_input, "Painters").set_value(15).run()
    assert next(m.value for m in app.metric if m.label == "Minimum to charge · ex VAT") == "£130.50"
    assert not any("Expected pottery spend" in w.label for w in app.number_input)
    labelled(app.number_input, "Studio hire charge · ex VAT").set_value(180.0).run()
    assert next(m.value for m in app.metric if m.label == "Staff commission") == "£24.75"
    assert not any("£250 target" in w.value for w in app.warning)
    labelled(app.number_input, "Painters").set_value(14).run()
    assert not any("£250 target" in w.value for w in app.warning)
    assert not app.exception


def test_private_package_surplus(simple_app):
    app = simple_app
    labelled(app.toggle, "Staff-generated enquiry").set_value(True).run()
    labelled(app.get("button_group"), "Calculator navigation").set_value("Private Studio Hire")
    next(w for w in app.button if w.label.startswith("Favourites")).click()
    labelled(app.number_input, "Painters").set_value(15)
    app.run()
    labelled(app.number_input, "Customer price per painter · ex VAT").set_value(40 / 1.2).run()
    assert not app.exception
    assert next(m.value for m in app.metric if m.label == "Minimum to charge · ex VAT") == "£443.00"
    assert next(m.value for m in app.metric if m.label == "Staff commission") == "£28.50"


def test_private_package_economics_do_not_depend_on_pottery_sales_target(simple_app):
    app = simple_app
    labelled(app.toggle, "Staff-generated enquiry").set_value(True).run()
    labelled(app.get("button_group"), "Calculator navigation").set_value("Private Studio Hire")
    labelled(app.number_input, "Painters").set_value(12)
    app.run()
    assert not app.exception
    assert next(m.value for m in app.metric if m.label == "Minimum to charge · ex VAT") == "£298.00"
    assert any("Good pricing" in w.value or "Low price" in w.value for w in app.markdown)
    assert next(m.value for m in app.metric if m.label == "Staff commission") == "£31.00"
    assert not any("£250" in w.value for w in app.caption)
    assert not any("pottery target" in w.value.lower() for w in app.warning)
    labelled(app.number_input, "Customer price per painter · ex VAT").set_value(20.0).run()
    assert any("Below minimum" in w.value for w in app.markdown)
    assert not app.success
    labelled(app.number_input, "Painters").set_value(14)
    labelled(app.number_input, "Customer price per painter · ex VAT").set_value(30.0).run()
    assert any("Good pricing" in w.value or "Low price" in w.value for w in app.markdown)
    assert not any("pottery target not met" in w.value for w in app.warning)


def test_directions_url():
    from urllib.parse import urlparse, parse_qs
    from services.travel import directions_link
    parsed = urlparse(directions_link("NE46 1BH", "  Venue & Hall, NE1 1AA  "))
    assert parsed.netloc == "www.google.com"
    assert parse_qs(parsed.query) == {"api": ["1"], "origin": ["Inspired Pots, Hexham, NE46 1BH, UK"],
                                      "destination": ["Venue & Hall, NE1 1AA"], "travelmode": ["driving"]}


def test_travel_warning_clears_when_both_values_entered(simple_app):
    app = simple_app
    assert any("Add both travel distance" in w.value for w in app.warning)
    assert any("Provisional pricing" in w.value for w in app.markdown)
    assert next(w for w in app.button if w.label.startswith("Use suggested price")).disabled
    assert not any("Base economics protected" in w.value for w in app.success)
    labelled(app.number_input, "Miles to destination · one way").set_value(10.0).run()
    assert any("Add both travel distance" in w.value for w in app.warning)
    labelled(app.number_input, "Estimated travel time · minutes one way").set_value(20.0).run()
    assert not any("Add both travel distance" in w.value for w in app.warning)
    assert not any("Provisional pricing" in w.value for w in app.markdown)
    assert not any("Travel estimate incomplete" in w.value for w in app.caption)
    labelled(app.get("button_group"), "Calculator navigation").set_value("Private Studio Hire").run()
    assert not any("Add both travel distance" in w.value for w in app.warning)


def test_suggested_price_handles_commission_and_total_hire(simple_app):
    app = simple_app
    labelled(app.number_input, "Customer price per painter · ex VAT").set_value(20.0)
    labelled(app.number_input, "Miles to destination · one way").set_value(10.0)
    labelled(app.number_input, "Estimated travel time · minutes one way").set_value(20.0)
    app.run()
    next(w for w in app.button if w.label.startswith("Use suggested price")).click().run()
    first_price = labelled(app.number_input, "Customer price per painter · ex VAT").value
    assert any("Good pricing" in w.value for w in app.markdown)
    assert next(w for w in app.button if w.label.startswith("Price already meets suggestion")).disabled
    labelled(app.toggle, "Staff-generated enquiry").set_value(True).run()
    next(w for w in app.button if w.label.startswith("Use suggested price")).click().run()
    assert labelled(app.number_input, "Customer price per painter · ex VAT").value > first_price
    assert any("Good pricing" in w.value for w in app.markdown)
    labelled(app.get("button_group"), "Calculator navigation").set_value("Private Studio Hire").run()
    assert any(w.label == "See pottery in packages" for w in app.expander)
    labelled(app.radio, "Private studio price").set_value("Event fee + pottery on the day").run()
    assert not any(w.label == "See pottery in packages" for w in app.expander)
    next(w for w in app.button if w.label.startswith("Use suggested price")).click().run()
    assert any("Good pricing" in w.value for w in app.markdown)
    assert not app.exception


@pytest.mark.parametrize("painters,share", [(1, "0"), (12, "0"), (20, "0.5"), (15, "0.5")])
def test_suggested_price_reaches_retained_margin_after_rounding(painters, share):
    from services.pricing import suggested_price, calculate_remote_commission, decimal, pricing_health
    floor = decimal("298.01")
    amount = suggested_price(floor, painters, share)
    total = amount * painters
    commission = calculate_remote_commission(total, floor, share)
    assert decimal(pricing_health(total, floor, commission)["margin"]) >= decimal("0.15")
    previous_total = (amount - decimal("0.01")) * painters
    previous_commission = calculate_remote_commission(previous_total, floor, share)
    assert decimal(pricing_health(previous_total, floor, previous_commission)["margin"]) < decimal("0.15")


def test_inbound_default_and_commission_switch(simple_app):
    app = simple_app
    assert labelled(app.toggle, "Staff-generated enquiry").value is False
    labelled(app.get("button_group"), "Calculator navigation").set_value("Private Studio Hire")
    labelled(app.number_input, "Painters").set_value(12)
    app.run()
    assert not any(m.label == "Staff commission" for m in app.metric)
    assert any("Good pricing" in w.value for w in app.markdown)
    floor = next(m.value for m in app.metric if m.label == "Minimum to charge · ex VAT")
    labelled(app.toggle, "Staff-generated enquiry").set_value(True).run()
    assert next(m.value for m in app.metric if m.label == "Staff commission") == "£31.00"
    assert any("Low price" in w.value for w in app.markdown)
    assert next(m.value for m in app.metric if m.label == "Minimum to charge · ex VAT") == floor
    labelled(app.get("button_group"), "Calculator navigation").set_value("Remote Event").run()
    assert labelled(app.toggle, "Staff-generated enquiry").value is True
    labelled(app.toggle, "Staff-generated enquiry").set_value(False).run()
    assert not any(m.label == "Staff commission" for m in app.metric)
    assert not app.exception


def test_hosted_shared_username_login(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'hosted.sqlite3'}")
    monkeypatch.setenv("AUTH_MODE", "password")
    monkeypatch.setenv("APP_MODE", "simple")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "ipots")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "studio123")
    st.cache_resource.clear()
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30).run()
    assert not app.exception
    assert not app.metric
    assert not any(w.label == "Email" for w in app.text_input)
    labelled(app.text_input, "Username").set_value("ipots")
    labelled(app.text_input, "Password").set_value("studio123")
    labelled(app.button, "Sign in").click().run()
    assert not app.exception
    assert any(m.label == "Customer charge · ex VAT" for m in app.metric)


@pytest.mark.parametrize("floor,commission,status", [
    (101, 0, "Below minimum"), (100, 0, "Close to break-even"),
    (95.01, 0, "Close to break-even"), (95, 0, "Low price"),
    (85.01, 0, "Low price"), (85, 0, "Good pricing"),
    (75.01, 0, "Good pricing"), (75, 0, "Strong pricing"),
    (70, 15, "Good pricing"),
])
def test_pricing_health_boundaries(floor, commission, status):
    from services.pricing import pricing_health
    assert pricing_health(100, floor, commission)["status"] == status


def test_pottery_selection_updates_price_and_keeps_inputs(simple_app):
    app = simple_app
    labelled(app.number_input, "Painters").set_value(15)
    labelled(app.number_input, "Customer price per painter · ex VAT").set_value(31.0)
    labelled(app.get("button_group"), "Calculator navigation").set_value("Pottery selection").run()
    assert not app.exception
    app.session_state["pottery_editor_Everyday_e3b0c44298fc_ex"] = {
        "edited_rows": {0: {"Offer": True, "Price": 12.0}, 1: {"Offer": True, "Price": 9.0}},
        "added_rows": [], "deleted_rows": []}
    app.run()
    assert not app.exception
    assert any(m.value == "£12.00" for m in app.metric)
    labelled(app.get("button_group"), "Calculator navigation").set_value("Remote Event").run()
    assert not app.exception
    assert labelled(app.number_input, "Painters").value == 15
    assert labelled(app.number_input, "Customer price per painter · ex VAT").value == 31.0
    assert next(m.value for m in app.metric if m.label == "Minimum to charge · ex VAT") == "£310.50"
    labelled(app.get("button_group"), "Calculator navigation").set_value("Pottery selection").run()
    assert any(m.value == "£12.00" for m in app.metric)


def test_package_highest_selection_and_invalid_price():
    from services.pottery_selection import selected_package
    items = [{"id": "a", "title": "Plate", "variant": "Small", "price_inc_vat": "9"},
             {"id": "b", "title": "Mug", "variant": "Default Title", "price_inc_vat": "12"}]
    assert selected_package("Everyday", items, {}) is None
    choices = {"a": {"offer": True, "price": "9"}, "b": {"offer": True, "price": "12"}}
    assert selected_package("Everyday", items, choices)["retail_inc_vat"] == "12"
    choices["b"]["offer"] = False
    assert selected_package("Everyday", items, choices)["retail_inc_vat"] == "9"
    choices["a"]["price"] = "0"
    with pytest.raises(ValueError, match="greater than"):
        selected_package("Everyday", items, choices)


def test_vat_display_conversion_preserves_unedited_retail_prices():
    from services.pottery_selection import reviewed_price_inc_vat
    assert reviewed_price_inc_vat("1.03", "1.23", "0.20") == "1.23"
    assert reviewed_price_inc_vat("1.04", "1.23", "0.20") == "1.25"
    assert reviewed_price_inc_vat("20.83", "25", "0.20") == "25"


def test_saved_calculation_owner_version_and_snapshot(factory, users, q, context):
    with factory.begin() as db:
        saved = save_calculation(db, users[1], "First estimate", q, context)
        assert saved.result["staff_commission"] == "21.59"
        with pytest.raises(PermissionError):
            get_calculation(db, users[2], saved.id)
        with pytest.raises(ValueError, match="another session"):
            save_calculation(db, users[1], "Changed", q, context, saved.id, 0)
        edited = save_calculation(db, users[1], "Updated name", q, context, saved.id, saved.version)
        assert edited.version == 2
        assert edited.context["settings"]["vat_rate"] == "0.20"
        assert edited.inputs["status"] == "Draft"

