"""Customers router — paginated list, detail, and filtering."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.customer import Customer
from app.schemas.api import CustomerOut, CustomerDetailOut, CustomerListOut

router = APIRouter(prefix="/customers", tags=["Customers"])

_SORT_FIELDS = {
    "lifetime_value": Customer.lifetime_value,
    "total_orders": Customer.total_orders,
    "churn_risk_score": Customer.churn_risk_score,
    "clv_predicted": Customer.clv_predicted,
    "first_purchase_date": Customer.first_purchase_date,
    "last_active_at": Customer.last_active_at,
}


@router.get("", response_model=CustomerListOut, summary="List customers with filtering and sorting")
def list_customers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None, description="Search by name, email, or external_id"),
    segment: str | None = Query(default=None, description="Filter by ai_segment"),
    region: str | None = Query(default=None, description="Filter by region"),
    sort_by: str = Query(default="lifetime_value", description="Sort field"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return paginated customer list. Supports search, segment filter, region filter, and sort."""
    query = db.query(Customer).filter(Customer.deleted_at.is_(None))

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Customer.full_name.ilike(search_term))
            | (Customer.email.ilike(search_term))
            | (Customer.external_id.ilike(search_term))
        )

    if segment:
        query = query.filter(Customer.ai_segment == segment)

    if region:
        query = query.filter(Customer.region == region)

    sort_col = _SORT_FIELDS.get(sort_by, Customer.lifetime_value)
    query = query.order_by(desc(sort_col) if sort_dir == "desc" else asc(sort_col))

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    pages = max(1, (total + page_size - 1) // page_size)

    return CustomerListOut(
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        items=[CustomerOut.model_validate(c) for c in items],
    )


@router.get("/{customer_id}", response_model=CustomerDetailOut, summary="Get full customer profile")
def get_customer(
    customer_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return full customer profile including all analytics fields."""
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.deleted_at.is_(None))
        .first()
    )
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return CustomerDetailOut.model_validate(customer)
