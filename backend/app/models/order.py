"""Order model — central fact table for all revenue analytics."""

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.upload_job import UploadJob
    from app.models.order_item import OrderItem


class Order(UUIDMixin, TimestampMixin, Base):
    """
    Central fact table. Every revenue KPI, chart, and analytics module
    reads from this table. Populated by the insert_orders Celery task.
    """
    __tablename__ = "orders"

    # Original order ID from the imported CSV
    external_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True, unique=True, index=True
    )

    # FK to customer — required (every order has a customer)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True
    )
    # FK to the upload job that created this order — data lineage
    upload_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("upload_jobs.id"), nullable=True, index=True
    )

    # The transaction date — X-axis for the Sales Trend 30-day chart
    order_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Revenue amounts
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    # net_amount = total_amount - discount_amount; the primary revenue figure
    # Stored (not computed at DB level) for compatibility with SQLAlchemy ORM
    net_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # COGS — required for A11 Margin analysis
    cost_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # Gross margin = net_amount - cost_amount; computed and stored by worker
    gross_margin: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    # Region denormalized from customer at order time (NA|EU|APAC|LATAM)
    # Denormalized to preserve historical accuracy if customer changes region
    region: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # ISO 4217 currency code (e.g. USD, EUR, GBP, JPY)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    # completed | refunded | pending | cancelled
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="completed", index=True
    )

    # --- v3.0 additions ---
    # A16 Payment Channel analytics
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # A17 Marketing Attribution (organic_search|paid_ads|referral|email|social)
    acquisition_channel: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # A18 Return Rate — TRUE = this order was returned
    return_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # A19 Fulfillment SLA — days from order_date to delivery
    delivery_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # A08 BERT Sentiment — raw comment from order and its classification
    comment_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # POSITIVE | NEGATIVE | NEUTRAL — written by run_sentiment task
    sentiment_label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Confidence 0.0000–1.0000
    sentiment_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="orders")
    upload_job: Mapped["UploadJob | None"] = relationship(
        "UploadJob", back_populates="orders"
    )
    order_items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )

    def compute_net_amount(self) -> Decimal:
        """Recalculate net_amount from current total and discount."""
        return self.total_amount - self.discount_amount

    def compute_gross_margin(self) -> Decimal | None:
        """Recalculate gross margin from net_amount and cost."""
        if self.cost_amount is None:
            return None
        return self.net_amount - self.cost_amount

    def __repr__(self) -> str:
        return (
            f"<Order id={self.id} external={self.external_id} "
            f"date={self.order_date} net={self.net_amount}>"
        )
