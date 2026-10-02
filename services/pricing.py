"""Pure Decimal commercial maths. Rates are fractions; money rounds half up.

Round each extended cost once, then sum. Never round the £5/1.2 unit
consumables value before multiplying by guests.
"""
from decimal import Decimal, ROUND_HALF_UP

ZERO = Decimal("0")
CENT = Decimal("0.01")


def decimal(value):
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("A finite number is required.")
    return result


def positive(value):
    result = decimal(value)
    if result < 0:
        raise ValueError("Amounts cannot be negative.")
    return result


def rate(value):
    result = positive(value)
    if result > 1:
        raise ValueError("Rates must be between 0 and 1.")
    return result


def money(value):
    return decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_vat(amount_ex_vat, vat_rate):
    return money(positive(amount_ex_vat) * rate(vat_rate))


def remove_vat(amount_inc_vat, vat_rate):
    return positive(amount_inc_vat) / (1 + rate(vat_rate))


def calculate_base_labour(staff_count, hours, hourly_cost):
    return money(positive(staff_count) * positive(hours) * positive(hourly_cost))


def calculate_travel_labour(return_hours, staff_count, hourly_cost):
    return calculate_base_labour(staff_count, return_hours, hourly_cost)


def calculate_vehicle_cost(return_miles, method="Mileage", mileage_rate="0.45",
                           vehicle_mpg="35", fuel_price_per_litre="1.50"):
    miles = positive(return_miles)
    if method == "Mileage":
        return money(miles * positive(mileage_rate))
    if method != "Fuel":
        raise ValueError("Choose Mileage or Fuel.")
    mpg = positive(vehicle_mpg)
    if mpg == 0:
        raise ValueError("Vehicle MPG must be greater than zero.")
    return money(miles / mpg * Decimal("4.54609") * positive(fuel_price_per_litre))


def calculate_consumables(painters, studio_fee_inc_vat, vat_rate):
    return money(positive(painters) * remove_vat(studio_fee_inc_vat, vat_rate))


def calculate_pottery_value(painters, retail_inc_vat, vat_rate, override_ex_vat=None):
    unit = positive(override_ex_vat) if override_ex_vat is not None else remove_vat(retail_inc_vat, vat_rate)
    return money(positive(painters) * unit)


def calculate_remote_protected_floor(pottery, consumables, event_labour, travel_labour,
                                     vehicle, extra_costs=ZERO):
    return money(sum((money(positive(v)) for v in
                      (pottery, consumables, event_labour, travel_labour, vehicle, extra_costs)), ZERO))


def calculate_private_protected_floor(consumables, staff_cost, minimum_booking="250",
                                      pottery=ZERO, extra_costs=ZERO):
    return money(max(positive(minimum_booking), sum((money(positive(v)) for v in
                                                   (consumables, staff_cost, pottery, extra_costs)), ZERO)))


def calculate_remote_commission(total_ex_vat, protected_floor, commission_rate="0.5", enabled=True):
    return money(max(ZERO, positive(total_ex_vat) - positive(protected_floor)) * rate(commission_rate)) if enabled else money(ZERO)


def calculate_private_commission(painters, method="Fixed", fixed_amount="25", tiers=None):
    if method == "Fixed":
        return money(positive(fixed_amount))
    if method != "Tiered":
        raise ValueError("Unknown private commission method.")
    tiers = tiers or [{"min_guests": 1, "amount": "20"}, {"min_guests": 15, "amount": "30"}, {"min_guests": 25, "amount": "40"}]
    eligible = [t for t in tiers if int(t["min_guests"]) <= int(painters)]
    return money(positive(max(eligible, key=lambda t: int(t["min_guests"]))["amount"])) if eligible else money(ZERO)


def calculate_deposit(amount_inc_vat, deposit_percentage="0.2"):
    return money(positive(amount_inc_vat) * rate(deposit_percentage))


def pricing_health(total_ex_vat, protected_floor, staff_commission):
    """Conservative retained headroom, not accounting net profit."""
    total = positive(total_ex_vat)
    retained = money(total - positive(protected_floor) - positive(staff_commission))
    margin = retained / total if total else ZERO
    if retained < 0:
        status, guidance = "Below minimum", "Increase the price to cover the protected costs."
    elif margin < Decimal("0.05"):
        status, guidance = "Close to break-even", "Very little headroom. Try a higher price before quoting."
    elif margin < Decimal("0.15"):
        status, guidance = "Low price", "Costs are covered, but there is room to improve the quote value."
    elif margin < Decimal("0.25"):
        status, guidance = "Good pricing", "A healthy balance of customer value and studio headroom."
    else:
        status, guidance = "Strong pricing", "Strong headroom. Focus on making the package worth the price."
    return {"status": status, "guidance": guidance, "retained": str(retained), "margin": str(margin)}


def calculate_quote(q, context):
    """context is a server-created commercial snapshot, stored with each quote."""
    s, package = context["settings"], context["package"]
    guests = int(q["guest_count"])
    if guests < 1:
        raise ValueError("At least one painter is required.")
    vat = rate(s["vat_rate"])
    fee_mode = q["event_type"] == "Private Studio Hire" and q["private_mode"] == "Event fee + pottery on the day"
    pottery = ZERO if fee_mode else calculate_pottery_value(guests, package["retail_inc_vat"], vat, package.get("override_ex_vat"))
    # Upgrades protect the larger of the extra retail value and the manual upgrade.
    upgrade = context.get("upgrade")
    if upgrade and not fee_mode:
        base_unit = positive(package["override_ex_vat"]) if package.get("override_ex_vat") is not None else remove_vat(package["retail_inc_vat"], vat)
        increment = max(ZERO, remove_vat(upgrade["retail_inc_vat"], vat) - base_unit, positive(upgrade["upgrade_amount"]))
        pottery = money(pottery + increment * guests)
    costs = {"pottery": money(pottery), "consumables": calculate_consumables(guests, s["studio_fee_inc_vat"], vat),
             "event_labour": calculate_base_labour(q["staff_count"], q["duration_hours"], s["hourly_cost"]),
             "travel_labour": money(ZERO), "vehicle": money(ZERO),
             "additional": money(sum((positive(c["amount_ex_vat"]) for c in q.get("extra_costs", [])), ZERO))}
    if q["event_type"] == "Remote Event":
        costs["travel_labour"] = calculate_travel_labour(decimal(q["return_minutes"]) / 60, q["staff_count"], s["hourly_cost"])
        costs["vehicle"] = calculate_vehicle_cost(q["return_miles"], s["vehicle_method"], s["mileage_rate"], s["vehicle_mpg"], s["fuel_price_per_litre"])
        floor = calculate_remote_protected_floor(*costs.values())
    else:
        if s.get("private_pricing_model") == "Pottery target and surplus":
            floor = calculate_private_protected_floor(costs["consumables"], costs["event_labour"], ZERO, costs["pottery"], costs["additional"])
        else:
            floor = calculate_private_protected_floor(costs["consumables"], costs["event_labour"], s["private_booking_minimum"], costs["pottery"], costs["additional"])
    total = money(positive(q["selling_amount"]) * guests) if q["selling_mode"] == "Per person" else money(positive(q["selling_amount"]))
    if q["event_type"] == "Remote Event":
        commission = calculate_remote_commission(total, floor, s["remote_commission_rate"], s["remote_commission_enabled"])
    else:
        if s.get("private_pricing_model") == "Pottery target and surplus":
            commission = calculate_remote_commission(total, floor, "0.50")
        else:
            commission = calculate_private_commission(guests, s["private_commission_method"], s["private_fixed_commission"], s["private_tiers"]) if q["customer_type"] == "Business" and total >= floor else money(ZERO)
    vat_amount = calculate_vat(total, vat)
    inc = total + vat_amount
    earned = q["status"] == "Won" and (q["event_type"] == "Remote Event" or q.get("deposit_paid", False))
    commission_status = "Earned" if earned else "Potential"
    if not q.get("commission_enabled", True):
        commission, commission_status = money(ZERO), "Not eligible"
    if q["status"] in ("Lost", "Cancelled"):
        commission, commission_status = money(ZERO), "Not eligible"
    surplus = money(max(ZERO, total - floor))
    status = "Below minimum viable price" if total < floor else ("Commission generated" if q["event_type"] == "Remote Event" and commission > 0 and surplus > positive(s["amber_buffer"]) else "Base economics protected")
    return {"costs": {k: str(v) for k, v in costs.items()}, "protected_floor": str(floor), "total_ex_vat": str(total),
            "price_per_person_ex_vat": str(money(total / guests)), "vat_amount": str(vat_amount), "total_inc_vat": str(inc),
            "deposit_amount": str(calculate_deposit(inc, s["deposit_percentage"])), "commissionable_surplus": str(surplus),
            "staff_commission": str(commission), "commission_status": commission_status, "pricing_status": status}
