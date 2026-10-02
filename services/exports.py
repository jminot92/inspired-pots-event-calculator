"""An explicit customer allowlist shared by PDF, printable HTML and email.

Never pass ORM objects, internal costs or staff notes to a renderer.
"""
from html import escape
from services.pricing import decimal


def currency(value):
    return f"£{decimal(value):,.2f}"


def customer_view(quote):
    q, r, c = quote.data, quote.result, quote.context
    fee_mode = q["event_type"] == "Private Studio Hire" and q["private_mode"] == "Event fee + pottery on the day"
    included = ["Private studio outside normal opening hours", "Dedicated Inspired Pots hosts", "Paints and materials", "Glazing and firing"] if fee_mode else ["One pottery item per painter", "Paints and materials", "Inspired Pots event hosts", "Setup and pack-down", "Glazing and firing"]
    location = ", ".join(filter(None, [q["destination_address"], q["destination_postcode"]])) if q["event_type"] == "Remote Event" else "Inspired Pots, Hexham, NE46 1BH"
    choices = ["Attendees choose and pay for their pottery separately on the day."] if fee_mode else c["package"]["choices"]
    package = "Private hire fee + pottery on the day" if fee_mode else c["package"]["name"] + " package"
    if c.get("upgrade") and not fee_mode:
        package += " with " + c["upgrade"]["label"]
        choices = [c["upgrade"]["label"]]
    return {"quote_number": quote.quote_number, "created": quote.created_at[:10], "customer": q["customer_name"],
            "contact": q["contact_name"], "event_date": q["event_date"], "event_type": q["event_type"],
            "location": location, "guests": q["guest_count"], "package": package, "choices": choices,
            "included": included, "per_person": r["price_per_person_ex_vat"], "subtotal": r["total_ex_vat"],
            "vat": r["vat_amount"], "vat_percentage": str(decimal(c["settings"]["vat_rate"]) * 100),
            "total": r["total_inc_vat"], "deposit": r["deposit_amount"], "deposit_percentage": str(decimal(c["settings"]["deposit_percentage"]) * 100),
            "terms": c["settings"]["terms"], "customer_notes": q.get("customer_notes", ""),
            "travel_note": "Travel is included in the quoted amount." if q["event_type"] == "Remote Event" else "Private hire is outside our normal opening hours.",
            "fee_mode": fee_mode}


def email_text(v):
    return (f"Hi {v['contact'] or v['customer']},\n\nThank you for getting in touch.\n\n"
            f"For {v['guests']} painters on {v['event_date']}, we have put together the following option:\n\n"
            f"{v['package']}\n{currency(v['per_person'])} per person excluding VAT.\n\n"
            f"This includes: {', '.join(v['included']).lower()}.\n"
            + ("Pottery is selected and paid for separately by attendees on the day.\n" if v["fee_mode"] else "")
            + f"\nTotal: {currency(v['subtotal'])} excluding VAT / {currency(v['total'])} including VAT.\n"
            f"To secure the booking, we request a {decimal(v['deposit_percentage']):g}% deposit of {currency(v['deposit'])}.\n\n"
            f"Venue: {v['location']}. {v['travel_note']}\n\n{v['customer_notes']}\n{v['terms']}\n\nThanks,\nInspired Pots")


def printable_html(v):
    e = lambda x: escape(str(x))
    prices = [("Per painter ex VAT", v["per_person"]), ("Subtotal ex VAT", v["subtotal"]),
              (f"VAT ({v['vat_percentage']}%)", v["vat"]), ("Total inc VAT", v["total"]), ("Deposit required", v["deposit"])]
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{e(v['quote_number'])}</title>
    <style>body{{font:16px Arial;color:#253b37;max-width:800px;margin:48px auto;padding:24px}}h1{{font:42px Georgia;color:#267366}}h2{{margin-top:32px}}.meta{{color:#65736b}}table{{width:100%;border-collapse:collapse}}td{{padding:12px;border-bottom:1px solid #deded6}}td:last-child{{text-align:right}}button{{padding:12px 20px;background:#267366;color:white;border:0;border-radius:6px}}@media print{{button{{display:none}}body{{margin:0}}}}</style></head>
    <body><button onclick="window.print()">Print quote</button><h1>Inspired Pots</h1><p class="meta">POTTERY PAINTING · HEXHAM</p>
    <h2>Your event quote</h2><p>{e(v['quote_number'])} · Created {e(v['created'])}</p><h2>{e(v['customer'])}</h2>
    <p>{e(v['event_date'])} · {e(v['guests'])} painters · {e(v['event_type'])}<br>{e(v['location'])}</p>
    <h2>{e(v['package'])}</h2><p>{'<br>'.join(e(x) for x in v['choices'])}</p><h2>What's included</h2>
    <ul>{''.join('<li>'+e(x)+'</li>' for x in v['included'])}</ul><p>{e(v['travel_note'])}</p><h2>Your price</h2>
    <table>{''.join('<tr><td>'+e(k)+'</td><td>'+e(currency(x))+'</td></tr>' for k,x in prices)}</table>
    <p>A {e(v['deposit_percentage'])}% deposit secures your event.</p><h2>Terms &amp; notes</h2>
    <p>{e(v['customer_notes']).replace(chr(10), '<br>')}</p><p>{e(v['terms']).replace(chr(10), '<br>')}</p></body></html>"""
