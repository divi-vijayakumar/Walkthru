# Unit: core.quote_pdf.build_quote_pdf renders null amounts, negative lines, assumptions and recalled notice
import sys
import fitz
sys.path.insert(0, "/app/backend")
from core.quote_pdf import build_quote_pdf  # noqa: E402


def test_pdf_builder_edge_cases():
    q = {"version": 3, "created_at": "2026-01-05T10:00:00+00:00", "status": "recalled", "total": 12000, "low": 11000,
         "high": 14000, "deposit_pct": 5, "deposit_amount": 600, "assumptions": ["Walls are sound & dry <ok>"],
         "line_items": [{"label": "Tile", "amount": 9000}, {"label": "Permit", "amount": None}, {"label": "Discount", "amount": -500}]}
    lead = {"name": "TEST_ Jo & Co", "ask": "Bathroom remodel"}
    c = {"name": "Apex Remodeling", "phone": "(555) 010-0000", "email": "a@b.c", "address": "1 Main"}
    body = build_quote_pdf(q, lead, c)
    with fitz.open(stream=body, filetype="pdf") as d:
        t = "\n".join(p.get_text() for p in d)
    for s in ("To be priced", "-$500", "$9,000", "Quote, version 3", "January 5, 2026", "TEST_ Jo & Co", "recalled",
              "Walls are sound & dry <ok>", "a@b.c", "1 Main", "$11,000 to $14,000", "Deposit after signing (5%)", "$600"):
        assert s in t, s
