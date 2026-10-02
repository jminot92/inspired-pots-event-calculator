from decimal import Decimal
import pytest
from services.pricing import *


def test_exact_specification_example(q, context):
    r = calculate_quote(q, context)
    assert r["costs"] == {"pottery": "250.00", "consumables": "83.33", "event_labour": "136.00", "travel_labour": "34.00", "vehicle": "13.50", "additional": "0.00"}
    assert r["protected_floor"] == "516.83"
    assert r["total_ex_vat"] == "560.00"
    assert r["commissionable_surplus"] == "43.17"
    assert r["staff_commission"] == "21.59"
    assert r["vat_amount"] == "112.00"
    assert r["total_inc_vat"] == "672.00"
    assert r["deposit_amount"] == "134.40"


def test_vat_never_changes_remote_commission(q, context):
    context["package"]["override_ex_vat"] = "12.5"
    context["settings"]["studio_fee_inc_vat"] = "0"
    before = calculate_quote(q, context)
    context["settings"]["vat_rate"] = "0.25"
    after = calculate_quote(q, context)
    assert before["staff_commission"] == after["staff_commission"]
    assert before["total_inc_vat"] != after["total_inc_vat"]


def test_money_and_vat_functions():
    assert remove_vat("5", ".2") > Decimal("4.1666")
    assert calculate_vat("560", ".2") == Decimal("112.00")
    assert calculate_consumables(20, 5, ".2") == Decimal("83.33")
    assert calculate_pottery_value(20, 15, ".2") == Decimal("250.00")
    assert calculate_pottery_value(20, 999, ".2", "10") == Decimal("200.00")
    assert calculate_deposit("672", ".2") == Decimal("134.40")
    assert money("21.585") == Decimal("21.59")


def test_labour_vehicle_and_extra_floor():
    assert calculate_base_labour(2, 4, 17) == Decimal("136.00")
    assert calculate_travel_labour("1.5", 2, 17) == Decimal("51.00")
    assert calculate_vehicle_cost(30) == Decimal("13.50")
    assert calculate_vehicle_cost(35, "Fuel", vehicle_mpg=35, fuel_price_per_litre="1.50") == Decimal("6.82")
    assert calculate_remote_protected_floor(250, "83.33", 136, 34, "13.50", 10) == Decimal("526.83")


@pytest.mark.parametrize("total,floor,expected", [(800, 600, "100.00"), (600, 600, "0.00"), (500, 600, "0.00")])
def test_remote_commission(total, floor, expected):
    assert calculate_remote_commission(total, floor) == Decimal(expected)
    assert calculate_remote_commission(total, floor, enabled=False) == Decimal("0.00")


@pytest.mark.parametrize("guests,expected", [(1, 20), (14, 20), (15, 30), (24, 30), (25, 40), (80, 40)])
def test_private_tier_boundaries(guests, expected):
    assert calculate_private_commission(guests, "Tiered") == Decimal(expected)
    assert calculate_private_commission(guests) == Decimal(25)


def test_private_fee_floor_deposit_and_earned_conditions(q, context):
    q.update(event_type="Private Studio Hire", private_mode="Event fee + pottery on the day", duration_hours="3", selling_amount="10")
    r = calculate_quote(q, context)
    assert r["costs"]["pottery"] == "0.00"
    assert r["costs"]["event_labour"] == "102.00"
    assert r["costs"]["travel_labour"] == "0.00"
    assert r["protected_floor"] == "250.00"
    assert r["pricing_status"] == "Below minimum viable price"
    q.update(selling_amount="15", status="Won")
    r = calculate_quote(q, context)
    assert r["commission_status"] == "Potential"
    assert r["staff_commission"] == "25.00"
    assert r["deposit_amount"] == "72.00"
    q["deposit_paid"] = True
    assert calculate_quote(q, context)["commission_status"] == "Earned"
    q["customer_type"] = "Consumer"
    assert calculate_quote(q, context)["staff_commission"] == "0.00"


def test_private_package_and_booking_minimum(q, context):
    q.update(event_type="Private Studio Hire", duration_hours="3")
    assert calculate_quote(q, context)["protected_floor"] == "435.33"
    assert calculate_private_protected_floor("83.33", 102, 250) == Decimal("250.00")
    assert calculate_private_protected_floor(300, 102, 250) == Decimal("402.00")


def test_upgrade_preserves_retail_and_extra_costs(q, context):
    context["upgrade"] = {"retail_inc_vat": "60", "upgrade_amount": "15"}
    q["extra_costs"] = [{"description": "Parking", "amount_ex_vat": "12.50"}]
    r = calculate_quote(q, context)
    assert r["costs"]["pottery"] == "1000.00"
    assert r["protected_floor"] == "1279.33"


@pytest.mark.parametrize("status", ["Lost", "Cancelled"])
def test_unconverted_commission_zero(q, context, status):
    q["status"] = status
    assert calculate_quote(q, context)["staff_commission"] == "0.00"
    assert calculate_quote(q, context)["commission_status"] == "Not eligible"


@pytest.mark.parametrize("value", ["-1", "NaN", "Infinity"])
def test_invalid_money_rejected(value):
    with pytest.raises(ValueError):
        calculate_vat(value, ".2")


def test_invalid_rates_and_mpg():
    with pytest.raises(ValueError):
        calculate_remote_commission(100, 10, "1.01")
    with pytest.raises(ValueError):
        calculate_vehicle_cost(30, "Fuel", vehicle_mpg=0)
