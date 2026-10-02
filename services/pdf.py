from io import BytesIO
from html import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from services.exports import currency


def generate_pdf(v):
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("Brand", fontName="Times-Roman", fontSize=34, leading=39, textColor=colors.HexColor("#267366"), spaceAfter=10))
    styles.add(ParagraphStyle("Price", parent=styles["BodyText"], alignment=TA_RIGHT))
    styles["BodyText"].leading, styles["BodyText"].spaceAfter = 13, 5
    styles["Heading2"].textColor = colors.HexColor("#267366")
    def p(text, style="BodyText"):
        return Paragraph(escape(str(text)).replace("\n", "<br/>"), styles[style])
    story = [p("Inspired Pots", "Brand"), p("POTTERY PAINTING · HEXHAM"), Spacer(1, 8 * mm),
             p("Your event quote", "Heading1"), p(f"{v['quote_number']}  |  Created {v['created']}"),
             p(v["customer"], "Heading2"), p(f"{v['event_date']} · {v['guests']} painters · {v['event_type']}"), p(v["location"]),
             p(v["package"], "Heading2")]
    for choice in v["choices"]:
        story.append(p("• " + choice))
    story.append(p("What's included", "Heading2"))
    story.extend(p("• " + item) for item in v["included"])
    story.append(p(v["travel_note"]))
    prices = [("Per painter ex VAT", v["per_person"]), ("Subtotal ex VAT", v["subtotal"]),
              (f"VAT ({v['vat_percentage']}%)", v["vat"]), ("Total inc VAT", v["total"]), ("Deposit required", v["deposit"])]
    table = Table([[p(label), p(currency(value), "Price")] for label, value in prices], colWidths=[112 * mm, 50 * mm])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0ECE5")),
                               ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                               ("LINEBELOW", (0, 3), (-1, 3), 1, colors.HexColor("#267366"))]))
    story.append(KeepTogether([p("Your price", "Heading2"), table, Spacer(1, 4 * mm), p(f"A {v['deposit_percentage']}% deposit secures your event.")]))
    # Keep the heading with its first paragraph while allowing long terms to flow.
    first_note = v["customer_notes"] or v["terms"]
    story.append(KeepTogether([p("Terms & notes", "Heading2"), p(first_note)]))
    if v["customer_notes"]:
        story.append(p(v["terms"]))
    def footer(canvas, doc):
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.HexColor("#65736b"))
        canvas.drawString(24 * mm, 15 * mm, "Inspired Pots · Hexham · NE46 1BH")
        canvas.drawRightString(186 * mm, 15 * mm, f"Page {doc.page}")
    SimpleDocTemplate(buffer, pagesize=A4, leftMargin=24 * mm, rightMargin=24 * mm, topMargin=22 * mm, bottomMargin=25 * mm,
                      title=f"Inspired Pots quote {v['quote_number']}", author="Inspired Pots").build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
