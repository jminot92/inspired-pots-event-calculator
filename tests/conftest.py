import copy
import sys
from pathlib import Path
import pytest
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models.entities import User
from services.database import make_session_factory, initialize
from services.config import DEFAULTS, TYPICAL_CHOICES


@pytest.fixture(autouse=True)
def local_test_server():
    from streamlit import config
    previous = config.get_option("server.address")
    config.set_option("server.address", "127.0.0.1")
    yield
    config.set_option("server.address", previous)


@pytest.fixture
def factory(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "local")
    f = make_session_factory(f"sqlite:///{tmp_path / 'test.sqlite3'}")
    initialize(f)
    with f.begin() as db:
        db.add(User(name="Salesperson", email="staff@example.com", role="Staff"))
        db.add(User(name="Other staff", email="other@example.com", role="Staff"))
    return f


@pytest.fixture
def users(factory):
    with factory() as db:
        return list(db.scalars(select(User).order_by(User.id)))


@pytest.fixture
def q():
    return {"customer_type": "Business", "event_type": "Remote Event", "customer_name": "Example customer", "contact_name": "Alex",
            "contact_email": "alex@example.com", "contact_phone": "", "event_date": "2026-12-01", "guest_count": 20,
            "status": "Draft", "salesperson_id": 2, "destination_address": "Venue", "destination_postcode": "NE1 1AA",
            "return_miles": "30", "return_minutes": "60", "travel_confirmed": True, "travel": {"source": "Manual"},
            "package": "Everyday", "upgrade_id": None, "staff_count": 2, "duration_hours": "4", "private_mode": "Package pricing",
            "extra_costs": [], "selling_mode": "Per person", "selling_amount": "28", "deposit_paid": False,
            "deposit_paid_date": None, "deposit_requested_date": None, "notes": "INTERNAL SECRET DO NOT EXPORT", "customer_notes": "Customer note"}


@pytest.fixture
def context():
    return {"settings": copy.deepcopy(DEFAULTS), "package": {"name": "Everyday", "retail_inc_vat": "15", "override_ex_vat": None,
                                                              "choices": [TYPICAL_CHOICES["Everyday"]], "source": "Configured safeguard"}}
