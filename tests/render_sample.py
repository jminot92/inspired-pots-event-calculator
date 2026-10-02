"""Developer-only PDF layout fixture. Run from the app folder."""
from pathlib import Path
from types import SimpleNamespace
from conftest import q as quote_fixture, context as context_fixture
from services.pricing import calculate_quote
from services.exports import customer_view
from services.pdf import generate_pdf

q = quote_fixture.__wrapped__()
c = context_fixture.__wrapped__()
quote = SimpleNamespace(data=q, context=c, result=calculate_quote(q, c), quote_number="IP-PREVIEW", created_at="2026-10-01T10:00:00+00:00")
folder = Path("tmp/pdfs")
folder.mkdir(parents=True, exist_ok=True)
(folder / "customer-preview.pdf").write_bytes(generate_pdf(customer_view(quote)))
print(folder / "customer-preview.pdf")
