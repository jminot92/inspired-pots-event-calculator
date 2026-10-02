from datetime import datetime, timezone
from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    role: Mapped[str] = mapped_column(String(16), default="Staff")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    password_hash: Mapped[str] = mapped_column(Text, default="")


class Quote(Base):
    __tablename__ = "quotes"
    id: Mapped[int] = mapped_column(primary_key=True)
    quote_number: Mapped[str] = mapped_column(String(50), unique=True)
    created_at: Mapped[str] = mapped_column(String(40), default=timestamp)
    updated_at: Mapped[str] = mapped_column(String(40), default=timestamp)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    salesperson_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    # Decimal monetary values are serialized as strings, never SQLite REALs.
    data: Mapped[dict] = mapped_column(JSON)
    context: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)


class QuoteCost(Base):
    __tablename__ = "quote_costs"
    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"))
    cost_type: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(Text)
    amount_ex_vat: Mapped[str] = mapped_column(String(40))


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    shopify_product_id: Mapped[str] = mapped_column(String(100))
    shopify_variant_id: Mapped[str] = mapped_column(String(100), unique=True)
    product_title: Mapped[str] = mapped_column(Text)
    variant_title: Mapped[str] = mapped_column(Text)
    sku: Mapped[str] = mapped_column(String(150), default="")
    retail_price_inc_vat: Mapped[str] = mapped_column(String(40))
    inventory: Mapped[int] = mapped_column(Integer, default=0)
    product_type: Mapped[str] = mapped_column(String(160), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    event_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    event_package: Mapped[str] = mapped_column(String(30), default="None")
    upgrade_amount: Mapped[str] = mapped_column(String(40), default="0")
    notes: Mapped[str] = mapped_column(Text, default="")
    last_synced: Mapped[str] = mapped_column(String(40), default=timestamp)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class Commission(Base):
    __tablename__ = "commissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), unique=True)
    salesperson_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    amount: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30))
    earned_date: Mapped[str | None] = mapped_column(String(40), nullable=True)
    paid_date: Mapped[str | None] = mapped_column(String(40), nullable=True)


class Audit(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int | None] = mapped_column(ForeignKey("quotes.id"), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80))
    at: Mapped[str] = mapped_column(String(40), default=timestamp)
    detail: Mapped[dict] = mapped_column(JSON)


class Calculation(Base):
    """Simple saved price checks, separate from the deferred booking workflow."""
    __tablename__ = "calculations"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[str] = mapped_column(String(40), default=timestamp)
    updated_at: Mapped[str] = mapped_column(String(40), default=timestamp)
    version: Mapped[int] = mapped_column(Integer, default=1)
    inputs: Mapped[dict] = mapped_column(JSON)
    context: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
