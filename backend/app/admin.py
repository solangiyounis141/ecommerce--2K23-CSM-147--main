from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import require_admin
from .database import get_db
from .errors import AppError
from .models import Category, Product, Sku, Variant
from .schemas import (CategoryCreate, CategoryUpdate, ProductCreate, ProductUpdate,
                      SkuCreate, SkuUpdate, VariantCreate)
from .services import (descendant_ids, get_or_create_variant, normalize_options,
                       would_create_cycle)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)])


# ---------- helpers ----------
def commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "integrity_error", "Request conflicts with an existing record or database rule")


def get_or_404(db: Session, model, obj_id: int, label: str):
    obj = db.get(model, obj_id)
    if obj is None:
        raise AppError(404, f"{label}_not_found", f"{label.capitalize()} {obj_id} not found")
    return obj


def availability(s: Sku) -> str:
    if not s.is_active:
        return "inactive"
    return "in_stock" if s.stock_quantity > 0 else "out_of_stock"


def sku_out(s: Sku) -> dict:
    return {"id": s.id, "variant_id": s.variant_id, "code": s.code,
            "price": f"{Decimal(s.price):.2f}", "stock_quantity": s.stock_quantity,
            "is_active": s.is_active, "availability": availability(s)}


def variant_out(v: Variant) -> dict:
    return {"id": v.id, "product_id": v.product_id, "option_values": v.option_values,
            "skus": [sku_out(s) for s in v.skus]}


def product_out(p: Product) -> dict:
    return {"id": p.id, "name": p.name, "slug": p.slug, "description": p.description,
            "status": p.status, "category_id": p.category_id, "specifications": p.specifications,
            "variants": [variant_out(v) for v in p.variants],
            "created_at": p.created_at.isoformat(), "updated_at": p.updated_at.isoformat()}


def category_out(c: Category) -> dict:
    return {"id": c.id, "parent_id": c.parent_id, "name": c.name, "slug": c.slug,
            "is_active": c.is_active, "children": []}


def slug_taken(db: Session, model, slug: str, exclude_id: int | None = None) -> bool:
    q = select(model.id).where(model.slug == slug)
    if exclude_id is not None:
        q = q.where(model.id != exclude_id)
    return db.scalar(q) is not None


def dup_slug() -> AppError:
    return AppError(409, "duplicate_slug", "Slug already exists")


def has_active_sku(p: Product, ignore_sku_id: int | None = None) -> bool:
    return any(s.is_active and s.id != ignore_sku_id for v in p.variants for s in v.skus)


def require_active_category(db: Session, category_id: int) -> Category:
    cat = db.get(Category, category_id)
    if cat is None:
        raise AppError(422, "invalid_category", f"Category {category_id} does not exist")
    if not cat.is_active:
        raise AppError(422, "inactive_category", "Category is inactive")
    return cat


# ---------- categories ----------
@router.post("/categories", status_code=201)
def create_category(body: CategoryCreate, db: Session = Depends(get_db)):
    if body.parent_id is not None:
        parent = db.get(Category, body.parent_id)
        if parent is None:
            raise AppError(422, "invalid_parent", "Parent category does not exist")
        if not parent.is_active:
            raise AppError(422, "inactive_parent", "Parent category is inactive")
    if slug_taken(db, Category, body.slug):
        raise dup_slug()
    cat = Category(name=body.name, slug=body.slug, parent_id=body.parent_id)
    db.add(cat)
    commit(db)
    db.refresh(cat)
    return category_out(cat)


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    cats = list(db.scalars(select(Category).order_by(Category.id)))
    nodes = {c.id: category_out(c) for c in cats}
    roots = []
    for c in cats:
        (nodes[c.parent_id]["children"] if c.parent_id in nodes else roots).append(nodes[c.id])
    return {"items": roots}


@router.patch("/categories/{category_id}")
def update_category(category_id: int, body: CategoryUpdate, db: Session = Depends(get_db)):
    cat = get_or_404(db, Category, category_id, "category")
    data = body.model_dump(exclude_unset=True)
    if data.get("slug") and slug_taken(db, Category, data["slug"], cat.id):
        raise dup_slug()
    if "parent_id" in data:
        pid = data["parent_id"]
        if pid is not None:
            if pid == cat.id or would_create_cycle(db, cat.id, pid):
                raise AppError(422, "category_cycle", "A category cannot become its own ancestor")
            if db.get(Category, pid) is None:
                raise AppError(422, "invalid_parent", "Parent category does not exist")
        cat.parent_id = pid
    if data.get("name"):
        cat.name = data["name"]
    if data.get("slug"):
        cat.slug = data["slug"]
    if data.get("is_active") is False:
        ids = [cat.id] + descendant_ids(db, cat.id)  # deactivating a parent deactivates its subtree
        db.execute(update(Category).where(Category.id.in_(ids)).values(is_active=False))
    elif data.get("is_active") is True:
        if cat.parent_id is not None and not db.get(Category, cat.parent_id).is_active:
            raise AppError(409, "inactive_parent", "Reactivate the parent category first")
        cat.is_active = True
    commit(db)
    db.refresh(cat)
    return category_out(cat)


# ---------- products ----------
@router.post("/products", status_code=201)
def create_product(body: ProductCreate, db: Session = Depends(get_db)):
    if slug_taken(db, Product, body.slug):
        raise dup_slug()
    require_active_category(db, body.category_id)
    p = Product(name=body.name, slug=body.slug, description=body.description,
                category_id=body.category_id, specifications=body.specifications, status="draft")
    db.add(p)
    commit(db)
    db.refresh(p)
    return product_out(p)


@router.get("/products")
def list_products(status: str | None = None, category_id: int | None = None,
                  limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                  db: Session = Depends(get_db)):
    q = select(Product)
    if status:
        q = q.where(Product.status == status)
    if category_id:
        q = q.where(Product.category_id == category_id)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    items = db.scalars(q.order_by(Product.id).limit(limit).offset(offset))
    return {"items": [product_out(p) for p in items], "total": total, "limit": limit, "offset": offset}


@router.get("/products/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db)):
    return product_out(get_or_404(db, Product, product_id, "product"))


@router.patch("/products/{product_id}")
def update_product(product_id: int, body: ProductUpdate, db: Session = Depends(get_db)):
    p = get_or_404(db, Product, product_id, "product")
    data = body.model_dump(exclude_unset=True)
    if data.get("slug") and slug_taken(db, Product, data["slug"], p.id):
        raise dup_slug()
    if data.get("category_id") is not None:
        require_active_category(db, data["category_id"])
    if data.get("status") == "published" and not has_active_sku(p):
        raise AppError(409, "no_sellable_sku", "A product needs at least one active SKU to be published")
    for field in ("name", "slug", "description", "category_id", "status"):
        if data.get(field) is not None:
            setattr(p, field, data[field])
    if "specifications" in data:
        p.specifications = data["specifications"]
    commit(db)
    db.refresh(p)
    return product_out(p)


@router.delete("/products/{product_id}", status_code=204)
def archive_product(product_id: int, db: Session = Depends(get_db)):
    """Soft delete: keeps rows so future cart/order references stay valid."""
    p = get_or_404(db, Product, product_id, "product")
    p.status = "archived"
    commit(db)
    return Response(status_code=204)


# ---------- variants & SKUs ----------
@router.post("/products/{product_id}/variants", status_code=201)
def create_variant(product_id: int, body: VariantCreate, db: Session = Depends(get_db)):
    p = get_or_404(db, Product, product_id, "product")
    variant, created = get_or_create_variant(db, p, body.option_values)
    if not created:
        raise AppError(409, "duplicate_variant", "This option combination already exists for the product")
    commit(db)
    db.refresh(variant)
    return variant_out(variant)


@router.post("/products/{product_id}/skus", status_code=201)
def create_sku(product_id: int, body: SkuCreate, db: Session = Depends(get_db)):
    p = get_or_404(db, Product, product_id, "product")
    code = body.code.upper()
    if db.scalar(select(Sku.id).where(Sku.code == code)):
        raise AppError(409, "duplicate_sku_code", f"SKU code {code} already exists")
    if body.variant_id is not None:
        variant = db.get(Variant, body.variant_id)
        if variant is None or variant.product_id != p.id:
            raise AppError(422, "invalid_variant", "Variant does not belong to this product")
    else:  # no options given -> the product's single default variant ({})
        variant, _ = get_or_create_variant(db, p, normalize_options(body.option_values))
    sku = Sku(variant_id=variant.id, code=code, price=body.price,
              stock_quantity=body.stock_quantity, is_active=body.is_active)
    db.add(sku)
    commit(db)
    db.refresh(sku)
    return sku_out(sku)


@router.patch("/skus/{sku_id}")
def update_sku(sku_id: int, body: SkuUpdate, db: Session = Depends(get_db)):
    sku = get_or_404(db, Sku, sku_id, "sku")
    data = body.model_dump(exclude_unset=True)
    if data.get("is_active") is False and sku.is_active:
        product = sku.variant.product
        if product.status == "published" and not has_active_sku(product, ignore_sku_id=sku.id):
            raise AppError(409, "last_sellable_sku", "Cannot deactivate the last active SKU of a published product")
    for field in ("price", "stock_quantity", "is_active"):
        if data.get(field) is not None:
            setattr(sku, field, data[field])
    commit(db)
    db.refresh(sku)
    return sku_out(sku)
