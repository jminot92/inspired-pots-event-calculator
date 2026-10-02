import copy
from io import BytesIO
import pytest
from sqlalchemy import select
from pypdf import PdfReader
from models.entities import Quote, Commission, Audit, Product, User
from services.database import get_settings, save_settings, assign_products, sync_products, package_context
from services.quotes import save_quote, customer_export_allowed, duplicate_data, set_commission_paid
from services.exports import customer_view, printable_html, email_text
from services.pdf import generate_pdf
from services.auth import hash_password, check_password


def test_staff_cannot_send_win_or_export_underquote(factory, users, q):
    q["selling_amount"] = "1"
    with factory.begin() as db:
        saved = save_quote(db, users[1], q)
        for status in ["Sent", "Won"]:
            with pytest.raises(ValueError, match="administrator"):
                save_quote(db, users[1], {**q, "status": status}, saved.id, saved.version)
        with pytest.raises(ValueError, match="export is blocked"):
            customer_export_allowed(users[1], saved)
        with pytest.raises(PermissionError):
            save_quote(db, users[1], {**q, "status": "Sent"}, saved.id, saved.version, "I override")


def test_admin_override_audit_and_economic_invalidation(factory, users, q):
    q.update(selling_amount="1", status="Sent")
    with factory.begin() as db:
        saved = save_quote(db, users[0], q, override_reason="Approved exceptional charity booking")
        assert saved.data["override"]["user_id"] == users[0].id
        assert db.scalar(select(Audit).where(Audit.action == "pricing_override"))
        customer_export_allowed(users[1], saved)
        # Staff cannot carry approval to another price.
        with pytest.raises(ValueError):
            save_quote(db, users[1], {**saved.data, "selling_amount": "2"}, saved.id, saved.version)
        draft = save_quote(db, users[1], {**saved.data, "status": "Draft", "selling_amount": "2"}, saved.id, saved.version)
        assert "override" not in draft.data


def test_ownership_and_recompute_not_user_input(factory, users, q):
    q["total_ex_vat"] = "9999999"
    q["override"] = {"user_id": 1, "reason": "forged"}
    q["salesperson_id"] = users[2].id
    with factory.begin() as db:
        saved = save_quote(db, users[1], q)
        assert saved.result["total_ex_vat"] == "560.00"
        assert saved.salesperson_id == users[1].id
        assert "override" not in saved.data
        with pytest.raises(PermissionError):
            save_quote(db, users[2], q, saved.id, saved.version)
        with pytest.raises(PermissionError):
            customer_export_allowed(users[2], saved)


def test_optimistic_lock_and_snapshot(factory, users, q):
    with factory.begin() as db:
        saved = save_quote(db, users[1], q)
        original_floor = saved.result["protected_floor"]
        settings = get_settings(db)
        settings["hourly_cost"] = "30"
        save_settings(db, users[0], settings)
        edited = save_quote(db, users[1], saved.data, saved.id, saved.version)
        assert edited.result["protected_floor"] == original_floor
        with pytest.raises(ValueError, match="another session"):
            save_quote(db, users[1], edited.data, saved.id, 1)
        refreshed = save_quote(db, users[1], edited.data, saved.id, edited.version, refresh=True)
        assert refreshed.result["protected_floor"] != original_floor


def test_commission_lifecycle_and_paid_lock(factory, users, q):
    q["selling_amount"] = "30"
    with factory.begin() as db:
        saved = save_quote(db, users[1], {**q, "status": "Won"})
        commission = db.scalar(select(Commission).where(Commission.quote_id == saved.id))
        assert commission.status == "Earned"
        with pytest.raises(PermissionError):
            set_commission_paid(db, users[1], saved.id)
        set_commission_paid(db, users[0], saved.id)
        assert commission.status == "Paid"
        assert commission.paid_date
        with pytest.raises(ValueError, match="Paid commission locks"):
            save_quote(db, users[1], {**saved.data, "status": "Lost"}, saved.id, saved.version)
        set_commission_paid(db, users[0], saved.id, paid=False)
        lost = save_quote(db, users[1], {**saved.data, "status": "Lost"}, saved.id, saved.version)
        assert commission.status == "Not eligible"
        assert commission.amount == "0.00"
        assert commission.earned_date is None


def test_private_commission_requires_deposit(factory, users, q):
    q.update(event_type="Private Studio Hire", private_mode="Event fee + pottery on the day", duration_hours="3", selling_amount="15", status="Won")
    with factory.begin() as db:
        saved = save_quote(db, users[1], q)
        c = db.scalar(select(Commission).where(Commission.quote_id == saved.id))
        assert c.status == "Potential"
        saved = save_quote(db, users[1], {**saved.data, "deposit_paid": True, "deposit_paid_date": "2026-10-01"}, saved.id, saved.version)
        assert c.status == "Earned"
        assert c.amount == "25.00"


def test_customer_allowlist_in_pdf_html_email(factory, users, q):
    with factory.begin() as db:
        saved = save_quote(db, users[1], q)
        view = customer_view(saved)
        pdf = generate_pdf(view)
        text = " ".join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages)
        for output in [text, printable_html(view), email_text(view)]:
            for forbidden in ["INTERNAL SECRET", "protected_floor", "Protected Floor", "commission", "travel_labour", "pottery margin", "fuel cost"]:
                assert forbidden not in output
            assert "672.00" in output
        assert "560.00" in text
        assert len(pdf) > 1000


def test_quote_duplicate_resets_deposit_and_approval(factory, users, q):
    with factory.begin() as db:
        saved = save_quote(db, users[0], {**q, "deposit_paid": True, "deposit_paid_date": "2026-10-01"}, override_reason="Admin approval")
        duplicate = duplicate_data(saved, users[1].id)
        assert duplicate["status"] == "Draft"
        assert not duplicate["deposit_paid"]
        assert "override" not in duplicate


def remote_product(price="1"):
    return {"shopify_variant_id": "gid://shopify/ProductVariant/1", "shopify_product_id": "gid://shopify/Product/1",
            "product_title": "Mug", "variant_title": "Default Title", "sku": "MUG", "retail_price_inc_vat": price,
            "inventory": 10, "product_type": "Pottery", "active": True, "last_synced": "2026-10-01T10:00:00+00:00"}


def test_sync_never_classifies_and_preserves_manual_fields(factory, users):
    with factory.begin() as db:
        sync_products(db, users[0], [remote_product()])
        p = db.scalar(select(Product))
        assert not p.event_eligible and p.event_package == "None"
        assign_products(db, users[0], [p.id], "Everyday", True, "15", "Checked by admin")
        sync_products(db, users[0], [remote_product("18")])
        assert p.event_eligible and p.event_package == "Everyday"
        assert p.notes == "Checked by admin" and p.upgrade_amount == "15"
        assert p.retail_price_inc_vat == "18"
        settings = get_settings(db)
        assert package_context(db, "Everyday", settings)["retail_inc_vat"] == "18"
        sync_products(db, users[0], [remote_product("1")])
        assert package_context(db, "Everyday", settings)["retail_inc_vat"] == "18"
        sync_products(db, users[0], [])
        assert not p.active and p.event_package == "Everyday"


def test_staff_cannot_change_settings_or_assignments(factory, users):
    with factory.begin() as db:
        with pytest.raises(PermissionError):
            save_settings(db, users[1], get_settings(db))
        with pytest.raises(PermissionError):
            assign_products(db, users[1], [], "Everyday", True, "0")
        with pytest.raises(PermissionError):
            sync_products(db, users[1], [])


def test_manual_travel_must_be_confirmed_and_deposit_date_required(factory, users, q):
    with factory.begin() as db:
        with pytest.raises(ValueError, match="travel"):
            save_quote(db, users[1], {**q, "travel_confirmed": False})
        with pytest.raises(ValueError, match="deposit"):
            save_quote(db, users[1], {**q, "deposit_paid": True})


def test_password_hashes_are_salted_and_checked():
    a = hash_password("correct horse battery staple")
    b = hash_password("correct horse battery staple")
    assert a != b
    assert check_password("correct horse battery staple", a)
    assert not check_password("incorrect", a)
    with pytest.raises(ValueError):
        hash_password("short")
