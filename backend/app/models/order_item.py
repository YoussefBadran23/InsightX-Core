"""OrderItem model — line items per order for basket analysis and stock deduction."""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, Integer, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.product import Product


class OrderItem(UUIDMixin, TimestampMixin, Base):
    """
    One line item within an order. Enables:
    - A04 Market Basket (Apriori) — co-purchased products per order
    - A10 ABC Tier — revenue contribution per product
    - A18 Return Rate — return flag propagated per product
    - Stock qty deduction per product on each upload
    """
    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # ON DELETE RESTRICT — cannot delete a product that has sales records
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    # Price snapshotted at purchase time — product.unit_price may change later
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # line_total = quantity * unit_price; computed and stored by insert_orders task
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="order_items")
    product: Mapped["Product"] = relationship("Product", back_populates="order_items")

    def compute_line_total(self) -> Decimal:
        """Recalculate line total from current quantity and price."""
        return Decimal(str(self.quantity)) * self.unit_price

    def __repr__(self) -> str:
        return (
            f"<OrderItem order={self.order_id} product={self.product_id} "
            f"qty={self.quantity} total={self.line_total}>"
        )
