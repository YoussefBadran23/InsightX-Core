"""Product model — catalogue, ABC tier, margin, return rate, and supplier."""

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, Date, Numeric, String, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import UUIDMixin, TimestampMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.order_item import OrderItem


class Product(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """
    Product/SKU entity. Populated during CSV ingest.
    ABC tier and return_rate written by analytics worker tasks.
    """
    __tablename__ = "products"

    # "SK-9021" format shown in Product Inventory table
    sku: Mapped[str] = mapped_column(
        String(20), nullable=False, unique=True, index=True
    )
    # "Wireless Noise-Cancelling Headphones"
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # "$299.00" shown in Product table — current selling price
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    # Unit cost of goods — from CSV; feeds A10 ABC and A11 Margin
    cost_price: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    # Supplier/vendor name — for A20 Supplier Performance
    supplier: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )

    # Stock level; dot indicator: green(>threshold), orange(near), red(< threshold)
    stock_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Per-product configurable alert threshold (default 10)
    low_stock_threshold: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10
    )

    # --- Analytics outputs (written by worker tasks) ---
    # 'A' | 'B' | 'C' — written by A10 ABC Analysis
    abc_tier: Mapped[str | None] = mapped_column(
        String(1), nullable=True, index=True
    )
    # Date the ABC tier was last computed — shown in future "last updated" UI
    abc_computed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    # % of orders that were returned — written by A18 Return Rate
    return_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )

    # --- Denormalized counters (updated by insert_orders task) ---
    # Used for ABC tier computation and inventory value stats card
    total_revenue: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"), index=True
    )
    total_units_sold: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    # Product thumbnail — shown in the mini image in Product table rows
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    order_items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem", back_populates="product"
    )

    @property
    def gross_margin_pct(self) -> Decimal | None:
        """Computed gross margin percentage. None if cost_price not set."""
        if self.cost_price is None or self.unit_price == 0:
            return None
        return ((self.unit_price - self.cost_price) / self.unit_price) * 100

    @property
    def is_low_stock(self) -> bool:
        """True when stock_qty is below the per-product threshold."""
        return self.stock_qty < self.low_stock_threshold

    def __repr__(self) -> str:
        return f"<Product sku={self.sku} name={self.name} abc={self.abc_tier}>"
