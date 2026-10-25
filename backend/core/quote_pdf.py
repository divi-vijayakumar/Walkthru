from io import BytesIO
from datetime import datetime
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

INK, MUTED, LINE, ACCENT = (colors.HexColor(c) for c in ("#0E1726", "#5B6577", "#E3E7ED", "#C2410C"))


def usd(n):
    return "" if n is None else (f"-${abs(round(n)):,}" if n < 0 else f"${round(n):,}")


def style(size, color=INK, bold=False, align=0):
    return ParagraphStyle("s", fontName="Helvetica-Bold" if bold else "Helvetica", fontSize=size, leading=size * 1.35, textColor=color, alignment=align)


def p(text, *a, **k):
    return Paragraph(escape(str(text)), style(*a, **k))


def build_quote_pdf(quote: dict, lead: dict, contractor: dict) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=0.8 * inch, rightMargin=0.8 * inch, topMargin=0.7 * inch,
                            bottomMargin=0.7 * inch, title=f"{contractor['name']} quote v{quote['version']}", author=contractor["name"])
    date = datetime.fromisoformat(quote["created_at"]).strftime("%B %-d, %Y")
    contact = "  |  ".join(x for x in (contractor.get("phone"), contractor.get("email"), contractor.get("address")) if x)
    story = [p(contractor["name"], 22, bold=True), p(contact, 9.5, MUTED), Spacer(1, 22),
             p(f"Quote, version {quote['version']}", 15, ACCENT, True), Spacer(1, 4),
             p(f"Prepared {date} for {lead['name']}", 10.5, MUTED), p(f"Project: {lead['ask']}", 10.5, MUTED), Spacer(1, 16)]
    if quote.get("status") == "recalled":
        story += [p("This quote was recalled and is no longer valid.", 11, ACCENT, True), Spacer(1, 10)]
    items = quote["line_items"]
    rows = [[p("Item", 9, MUTED, True), p("Price", 9, MUTED, True, 2)]]
    rows += [[p(i["label"], 10.5), "To be priced" if i.get("amount") is None else usd(i["amount"])] for i in items]
    rows += [[p("Total", 12, bold=True), usd(quote["total"])],
             [p(f"Deposit after signing ({quote['deposit_pct']}%)", 10.5, bold=True), usd(quote["deposit_amount"])]]
    n = len(items)
    table = Table(rows, colWidths=[4.6 * inch, 2.2 * inch], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (1, 1), (1, -1), "Helvetica"), ("FONTSIZE", (1, 1), (1, -1), 10.5), ("TEXTCOLOR", (1, 0), (1, -1), INK),
        ("LINEBELOW", (0, 0), (-1, n), 0.6, LINE), ("LINEABOVE", (0, n + 1), (-1, n + 1), 1.2, INK),
        ("FONTNAME", (1, n + 1), (1, n + 1), "Helvetica-Bold"), ("FONTSIZE", (1, n + 1), (1, n + 1), 12),
        ("FONTNAME", (1, n + 2), (1, n + 2), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7), ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(table)
    if quote.get("if_not"):
        story += [Spacer(1, 12), p(f"{quote['if_not']['say']} That would make the total {usd(quote['if_not']['total'])}.", 10.5, ACCENT, True)]
    if quote.get("assumptions"):
        story += [Spacer(1, 18), p("Assumptions", 11, bold=True), Spacer(1, 4)]
        story += [p(f"- {a}", 10, MUTED) for a in quote["assumptions"]]
    story += [Spacer(1, 22), p(f"This estimate is based on a video walkthrough. {contractor['name']} confirms the final price "
                                f"after a site check. The deposit is due after the contract is signed.", 9, MUTED)]
    doc.build(story)
    return buf.getvalue()
