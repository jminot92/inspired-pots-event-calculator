import copy
import hashlib
import json
import re
import uuid
from datetime import date
from sqlalchemy import select, update, delete
from models.entities import Quote, QuoteCost, Commission, Audit, User, timestamp
from services.auth import can_edit, require_admin
from services.config import STATUSES
from services.database import pricing_context
from services.pricing import calculate_quote, decimal, positive


def signature(q, context):
    # Customer/status/deposit edits don't invalidate approval; economic changes do.
    fields = ("customer_type", "event_type", "guest_count", "staff_count", "duration_hours", "package", "upgrade_id",
              "private_mode", "selling_mode", "selling_amount", "return_miles", "return_minutes", "extra_costs",
              "destination_address", "destination_postcode", "travel_confirmed")
    raw = json.dumps({"quote": {k: q.get(k) for k in fields}, "context": context}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def validate_quote(q):
    if q["status"] not in STATUSES or q["customer_type"] not in ("Business", "Consumer") or q["event_type"] not in ("Remote Event", "Private Studio Hire"):
        raise ValueError("Invalid quote type or status.")
    if q["selling_mode"] not in ("Per person", "Total event") or q["private_mode"] not in ("Package pricing", "Event fee + pottery on the day"):
        raise ValueError("Invalid selling mode.")
    if not q["customer_name"].strip():
        raise ValueError("Enter a customer or company name.")
    if int(q["guest_count"]) < 1 or int(q["staff_count"]) < 1 or positive(q["duration_hours"]) <= 0:
        raise ValueError("Guests, dedicated staff and event hours must be positive.")
    date.fromisoformat(q["event_date"])
    if q.get("contact_email") and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", q["contact_email"]):
        raise ValueError("Enter a valid contact email address.")
    if q.get("deposit_paid") and not q.get("deposit_paid_date"):
        raise ValueError("Enter the date the deposit was paid.")
    if q.get("deposit_paid_date"):
        date.fromisoformat(q["deposit_paid_date"])
    if q.get("deposit_requested_date"):
        date.fromisoformat(q["deposit_requested_date"])
    for cost in q.get("extra_costs", []):
        positive(cost["amount_ex_vat"])
        if not cost["description"].strip():
            raise ValueError("Every extra cost needs a description.")
    if q["event_type"] == "Remote Event":
        if not q["destination_postcode"].strip():
            raise ValueError("Enter the event postcode.")
        if not q.get("travel_confirmed"):
            raise ValueError("Calculate travel or confirm a manually checked return journey before saving.")
        positive(q["return_miles"])
        positive(q["return_minutes"])


def save_quote(db, user, q, quote_id=None, expected_version=None, override_reason="", refresh=False):
    """Single enforced write path for edits AND status actions. Recompute server-side."""
    if not user.active:
        raise PermissionError("This account is inactive.")
    validate_quote(q)
    existing = db.get(Quote, quote_id) if quote_id else None
    if quote_id and existing is None:
        raise ValueError("Quote no longer exists.")
    if existing and not can_edit(user, existing):
        raise PermissionError("You can only edit quotes assigned to you.")
    if existing and existing.version != expected_version:
        raise ValueError("This quote changed in another session. Reopen it before saving.")
    q = copy.deepcopy(q)
    salesperson = int(q.get("salesperson_id", user.id)) if user.role == "Admin" else user.id
    assigned = db.get(User, salesperson)
    if assigned is None or not assigned.active:
        raise ValueError("Choose an active salesperson.")
    q["salesperson_id"] = salesperson
    # Frozen commercial assumptions survive reopening; changing a package/upgrade
    # or explicit refresh uses current settings and catalogue.
    use_old = existing and not refresh and q["package"] == existing.data["package"] and q.get("upgrade_id") == existing.data.get("upgrade_id")
    context = copy.deepcopy(existing.context) if use_old else pricing_context(db, q)
    result = calculate_quote(q, context)
    sig = signature(q, context)
    prior_override = existing.data.get("override") if existing else None
    approval = prior_override if prior_override and prior_override["signature"] == sig else None
    if override_reason.strip():
        require_admin(user)
        approval = {"user_id": user.id, "user_name": user.name, "at": timestamp(), "reason": override_reason.strip(), "signature": sig}
    q.pop("override", None)
    if approval:
        q["override"] = approval
    if decimal(result["total_ex_vat"]) < decimal(result["protected_floor"]) and q["status"] in ("Sent", "Won") and not approval:
        raise ValueError("Below minimum viable price: an administrator must record an override reason before Sent or Won.")
    existing_commission = db.scalar(select(Commission).where(Commission.quote_id == quote_id)) if existing else None
    if existing_commission and existing_commission.status == "Paid":
        if sig != signature(existing.data, existing.context) or q["status"] != existing.data["status"] or q.get("deposit_paid") != existing.data.get("deposit_paid") or salesperson != existing.salesperson_id:
            raise ValueError("Paid commission locks commercial terms, salesperson and booking status. Ask an admin to reopen commission first.")
    now = timestamp()
    if existing:
        updated = db.execute(update(Quote).where(Quote.id == quote_id, Quote.version == expected_version).values(
            data=q, context=context, result=result, salesperson_id=salesperson, updated_at=now, version=expected_version + 1))
        if updated.rowcount != 1:
            raise ValueError("This quote changed in another session. Reopen it before saving.")
        db.expire(existing)
        saved = db.get(Quote, quote_id)
    else:
        saved = Quote(quote_number=f"IP-{date.today():%Y%m%d}-{uuid.uuid4().hex[:8].upper()}",
                      created_by=user.id, salesperson_id=salesperson, data=q, context=context, result=result)
        db.add(saved)
        db.flush()
    db.execute(delete(QuoteCost).where(QuoteCost.quote_id == saved.id))
    for kind, amount in result["costs"].items():
        if kind != "additional":
            db.add(QuoteCost(quote_id=saved.id, cost_type=kind, description=kind.replace("_", " "), amount_ex_vat=amount))
    for cost in q.get("extra_costs", []):
        db.add(QuoteCost(quote_id=saved.id, cost_type="additional", description=cost["description"], amount_ex_vat=str(positive(cost["amount_ex_vat"]))))
    commission = existing_commission or Commission(quote_id=saved.id, salesperson_id=salesperson, amount="0", status="Potential")
    if not existing_commission:
        db.add(commission)
    commission.amount, commission.salesperson_id = result["staff_commission"], salesperson
    if commission.status != "Paid":
        commission.status = result["commission_status"]
        commission.earned_date = (commission.earned_date or now) if commission.status == "Earned" else None
    db.add(Audit(quote_id=saved.id, user_id=user.id, action="quote_saved", detail={"version": saved.version, "status": q["status"]}))
    if override_reason.strip():
        db.add(Audit(quote_id=saved.id, user_id=user.id, action="pricing_override", detail=approval))
    db.flush()
    return saved


def list_quotes(db, user):
    query = select(Quote).order_by(Quote.updated_at.desc())
    if user.role != "Admin":
        query = query.where(Quote.salesperson_id == user.id)
    return list(db.scalars(query))


def customer_export_allowed(user, quote):
    if not can_edit(user, quote):
        raise PermissionError("You can only export your own quotes.")
    approval = quote.data.get("override")
    valid = approval and approval.get("signature") == signature(quote.data, quote.context)
    if decimal(quote.result["total_ex_vat"]) < decimal(quote.result["protected_floor"]) and not valid:
        raise ValueError("Customer export is blocked below the protected minimum until an admin approves this price.")


def duplicate_data(quote, user_id):
    q = copy.deepcopy(quote.data)
    q.update(status="Draft", deposit_paid=False, deposit_paid_date=None, deposit_requested_date=None, salesperson_id=user_id)
    q.pop("override", None)
    return q


def set_commission_paid(db, user, quote_id, paid=True):
    require_admin(user)
    commission = db.scalar(select(Commission).where(Commission.quote_id == quote_id))
    if commission is None:
        raise ValueError("Commission does not exist.")
    if paid:
        if commission.status != "Earned" or decimal(commission.amount) <= 0:
            raise ValueError("Only positive earned commission can be marked paid.")
        commission.status, commission.paid_date = "Paid", timestamp()
    else:
        if commission.status != "Paid":
            raise ValueError("Commission is not paid.")
        commission.status, commission.paid_date = "Earned", None
    db.add(Audit(quote_id=quote_id, user_id=user.id, action="commission_paid" if paid else "commission_reopened", detail={"amount": commission.amount}))
