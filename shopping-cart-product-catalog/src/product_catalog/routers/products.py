"""Product discovery and administration endpoints."""

from decimal import Decimal
from secrets import compare_digest
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..auth import CurrentUser, get_current_user, require_auth
from ..database import get_db
from ..messaging import ProductEventPublisher, get_event_publisher
from ..config import get_settings
from ..models import Category, Product
from ..schemas import (
    InventoryUpdate,
    InventoryBatchRequest,
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    PaginatedResponse,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)

router = APIRouter()
logger = structlog.get_logger(__name__)


def require_internal_token(x_internal_api_token: str = Header(default="")) -> None:
    expected = get_settings().internal_api_token
    if not expected or not compare_digest(x_internal_api_token, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Internal service authentication required")


def require_valid_category(db: Session, slug: str | None) -> None:
    if not slug or not db.query(Category).filter(Category.slug == slug, Category.is_active.is_(True)).first():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Select an active category from the catalog taxonomy")


@router.get("", response_model=PaginatedResponse)
def list_products(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    category: str | None = None,
    search: str | None = Query(default=None, min_length=1, max_length=120),
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    sort: str = Query(default="newest", pattern="^(newest|price_asc|price_desc|name)$"),
    active_only: bool = True,
    seller_id: UUID | None = None,
    user: CurrentUser | None = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaginatedResponse:
    """List products with server-side search, filters and stable sorting."""
    if not active_only and not (user and user.is_catalog_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Catalog admin role required to include inactive products")
    query = db.query(Product)

    if active_only:
        query = query.filter(Product.is_active.is_(True))

    if seller_id:
        query = query.filter(Product.seller_id == seller_id)

    if category:
        query = query.filter(func.lower(Product.category) == category.strip().lower())

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Product.name.ilike(term),
                Product.description.ilike(term),
                Product.sku.ilike(term),
                Product.category.ilike(term),
            )
        )

    if min_price is not None:
        query = query.filter(Product.price >= min_price)

    if max_price is not None:
        query = query.filter(Product.price <= max_price)

    ordering = {
        "newest": Product.created_at.desc(),
        "price_asc": Product.price.asc(),
        "price_desc": Product.price.desc(),
        "name": Product.name.asc(),
    }
    query = query.order_by(ordering[sort], Product.id.asc())

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return PaginatedResponse(
        items=[ProductResponse.model_validate(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(include_inactive: bool = False, db: Session = Depends(get_db)) -> list[CategoryResponse]:
    query = db.query(Category)
    if not include_inactive:
        query = query.filter(Category.is_active.is_(True))
    return query.order_by(Category.sort_order.asc(), Category.name.asc()).all()


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(category_in: CategoryCreate, db: Session = Depends(get_db), user: CurrentUser = Depends(require_auth)) -> CategoryResponse:
    if not user.is_catalog_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Catalog admin role required")
    if db.query(Category).filter((Category.slug == category_in.slug) | (Category.name == category_in.name)).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Category slug or name already exists")
    category = Category(**category_in.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.patch("/categories/{category_id}", response_model=CategoryResponse)
def update_category(category_id: int, category_in: CategoryUpdate, db: Session = Depends(get_db), user: CurrentUser = Depends(require_auth)) -> CategoryResponse:
    if not user.is_catalog_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Catalog admin role required")
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    for field, value in category_in.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    db.commit()
    db.refresh(category)
    return category


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, db: Session = Depends(get_db), user: CurrentUser = Depends(require_auth)) -> Response:
    if not user.is_catalog_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Catalog admin role required")
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    if db.query(Product).filter(Product.category == category.slug).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Category is in use; deactivate it instead")
    db.delete(category)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/inventory/batch", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_internal_token)])
def adjust_inventory_batch(request: InventoryBatchRequest, db: Session = Depends(get_db)) -> Response:
    quantities: dict[UUID, int] = {}
    for item in request.items:
        quantities[item.product_id] = quantities.get(item.product_id, 0) + item.quantity
    products = db.query(Product).filter(Product.id.in_(quantities)).with_for_update().all()
    if len(products) != len(quantities):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="One or more products no longer exist")
    if request.operation == "reserve":
        unavailable = [p.sku for p in products if not p.is_active or int(p.quantity) < quantities[p.id]]
        if unavailable:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Insufficient stock for: " + ", ".join(unavailable))
        for product in products:
            product.quantity = int(product.quantity) - quantities[product.id]
    else:
        for product in products:
            product.quantity = int(product.quantity) + quantities[product.id]
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/suggestions", response_model=list[str])
def search_suggestions(
    q: str = Query(min_length=2, max_length=120),
    limit: int = Query(default=6, ge=1, le=10),
    db: Session = Depends(get_db),
) -> list[str]:
    """Return lightweight product-name suggestions without exposing inactive items."""
    rows = (
        db.query(Product.name)
        .filter(Product.is_active.is_(True), Product.name.ilike(f"%{q.strip()}%"))
        .order_by(Product.name.asc())
        .limit(limit)
        .all()
    )
    return [name for (name,) in rows]


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    user: CurrentUser | None = Depends(get_current_user),
) -> ProductResponse:
    """Get a product by ID."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    can_manage_product = bool(user and (user.is_admin or (product.seller_id and str(product.seller_id) == user.id)))
    if not product.is_active and not can_manage_product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return ProductResponse.model_validate(product)


@router.get("/sku/{sku}", response_model=ProductResponse)
def get_product_by_sku(
    sku: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
) -> ProductResponse:
    """Get a product by SKU."""
    product = db.query(Product).filter(Product.sku == sku).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if not user.is_admin and (product.seller_id is None or str(product.seller_id) != user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only view SKU details for your own products")
    return ProductResponse.model_validate(product)


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    product_in: ProductCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
) -> ProductResponse:
    """Create a new product."""
    if not user.is_admin and not user.has_any_role("seller-owner", "seller-manager", "seller-staff"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Approved seller role required")
    require_valid_category(db, product_in.category)
    # Check for duplicate SKU
    existing = db.query(Product).filter(Product.sku == product_in.sku).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Product with SKU '{product_in.sku}' already exists",
        )

    seller_id = UUID(user.id) if not user.is_admin else None
    product = Product(**product_in.model_dump(), seller_id=seller_id)
    db.add(product)
    db.commit()
    db.refresh(product)

    logger.info("product_created", product_id=str(product.id), sku=product.sku)

    return ProductResponse.model_validate(product)


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: UUID,
    product_in: ProductUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
) -> ProductResponse:
    """Update a product."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if not user.is_admin and (product.seller_id is None or str(product.seller_id) != user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only update your own products")

    update_data = product_in.model_dump(exclude_unset=True)
    if "category" in update_data:
        require_valid_category(db, update_data["category"])
    for field, value in update_data.items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)

    logger.info("product_updated", product_id=str(product.id), fields=list(update_data.keys()))

    return ProductResponse.model_validate(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
) -> None:
    """Soft delete a product (sets is_active=False)."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if not user.is_admin and (product.seller_id is None or str(product.seller_id) != user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only delete your own products")

    product.is_active = False
    db.commit()

    logger.info("product_deleted", product_id=str(product.id))


@router.post("/{product_id}/inventory", response_model=ProductResponse)
def update_inventory(
    product_id: UUID,
    inventory_update: InventoryUpdate,
    db: Session = Depends(get_db),
    event_publisher: ProductEventPublisher = Depends(get_event_publisher),
    x_correlation_id: str | None = Header(None),
    user: CurrentUser = Depends(require_auth),
) -> ProductResponse:
    """Update product inventory and publish event."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if not user.is_admin and (product.seller_id is None or str(product.seller_id) != user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only update inventory for your own products")

    previous_quantity = int(product.quantity)
    new_quantity = previous_quantity + inventory_update.quantity_change

    if new_quantity < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient inventory. Current: {previous_quantity}, requested change: {inventory_update.quantity_change}",
        )

    product.quantity = new_quantity
    db.commit()
    db.refresh(product)

    logger.info(
        "inventory_updated",
        product_id=str(product.id),
        previous_quantity=previous_quantity,
        new_quantity=new_quantity,
        reason=inventory_update.reason,
    )

    # Publish inventory.updated event to RabbitMQ
    event_publisher.publish_inventory_updated(
        product_id=str(product.id),
        sku=product.sku,
        previous_quantity=previous_quantity,
        new_quantity=new_quantity,
        reason=inventory_update.reason,
        correlation_id=x_correlation_id,
    )

    return ProductResponse.model_validate(product)
