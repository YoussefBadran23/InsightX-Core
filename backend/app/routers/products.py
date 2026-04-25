"""Products router — paginated list and detail with ABC tier, stock status filters."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.product import Product
from app.schemas.api import ProductOut, ProductListOut

router = APIRouter(prefix="/products", tags=["Products"])

_SORT_FIELDS = {
    "total_revenue": Product.total_revenue,
    "total_units_sold": Product.total_units_sold,
    "unit_price": Product.unit_price,
    "stock_qty": Product.stock_qty,
    "name": Product.name,
}


@router.get("", response_model=ProductListOut, summary="List products with filtering and sorting")
def list_products(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None, description="Search by name, SKU, or category"),
    category: str | None = Query(default=None, description="Filter by category"),
    abc_tier: str | None = Query(default=None, description="Filter by ABC tier (A, B, C)"),
    low_stock_only: bool = Query(default=False, description="Only show low-stock products"),
    sort_by: str = Query(default="total_revenue", description="Sort field"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return paginated product list. Supports search, category, ABC tier, stock status, and sort."""
    query = db.query(Product).filter(Product.deleted_at.is_(None), Product.is_active.is_(True))

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Product.name.ilike(search_term))
            | (Product.sku.ilike(search_term))
            | (Product.category.ilike(search_term))
        )

    if category:
        query = query.filter(Product.category == category)

    if abc_tier:
        query = query.filter(Product.abc_tier == abc_tier.upper())

    if low_stock_only:
        # stock_qty < low_stock_threshold
        query = query.filter(Product.stock_qty < Product.low_stock_threshold)

    sort_col = _SORT_FIELDS.get(sort_by, Product.total_revenue)
    query = query.order_by(desc(sort_col) if sort_dir == "desc" else asc(sort_col))

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    pages = max(1, (total + page_size - 1) // page_size)

    return ProductListOut(
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        items=[ProductOut.model_validate(p) for p in items],
    )


@router.get("/{product_id}", response_model=ProductOut, summary="Get single product detail")
def get_product(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return full product detail."""
    product = (
        db.query(Product)
        .filter(Product.id == product_id, Product.deleted_at.is_(None))
        .first()
    )
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return ProductOut.model_validate(product)
