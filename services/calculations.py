import copy
from sqlalchemy import select, update
from models.entities import Calculation, timestamp
from services.pricing import calculate_quote


def list_calculations(db, user):
    query = select(Calculation).order_by(Calculation.updated_at.desc())
    if user.role != "Admin":
        query = query.where(Calculation.owner_id == user.id)
    return list(db.scalars(query))


def get_calculation(db, user, calculation_id):
    row = db.get(Calculation, calculation_id)
    if not user.active or row is None or (user.role != "Admin" and row.owner_id != user.id):
        raise PermissionError("This saved calculation is not available to your account.")
    return row


def save_calculation(db, user, name, inputs, context, calculation_id=None, expected_version=None):
    if not user.active:
        raise PermissionError("This account is inactive.")
    if not name.strip():
        raise ValueError("Give this calculation a name before saving.")
    # Calculations are draft checks, never Sent/Won bookings or customer quotes.
    inputs = copy.deepcopy(inputs)
    inputs.update(status="Draft", deposit_paid=False)
    result = calculate_quote(inputs, context)
    if calculation_id:
        row = get_calculation(db, user, calculation_id)
        updated = db.execute(update(Calculation).where(Calculation.id == row.id, Calculation.version == expected_version).values(
            name=name.strip(), inputs=inputs, context=copy.deepcopy(context), result=result, updated_at=timestamp(), version=row.version + 1))
        if updated.rowcount != 1:
            raise ValueError("This calculation changed in another session. Reopen it before saving.")
        db.expire(row)
        return db.get(Calculation, row.id)
    row = Calculation(owner_id=user.id, name=name.strip(), inputs=inputs, context=copy.deepcopy(context), result=result)
    db.add(row)
    db.flush()
    return row
