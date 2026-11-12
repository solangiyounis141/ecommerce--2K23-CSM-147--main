import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from .errors import AppError
from .models import Category, Product, Variant


def normalize_options(ov: dict | None) -> dict:
    return {str(k).strip().lower(): str(v).strip() for k, v in (ov or {}).items()}


def option_key(ov: dict) -> str:
    return json.dumps({k: v.lower() for k, v in ov.items()}, sort_keys=True, separators=(",", ":"))


def check_option_names(product: Product, ov: dict) -> None:
    """All variants of a product must use the same option types (CAT04: valid combinations only)."""
    if product.variants:
        expected = set(product.variants[0].option_values.keys())
        if set(ov.keys()) != expected:
            raise AppError(
                422, "invalid_option_combination",
                "Variant options must use the same option types as the product's other variants",
                {"expected": sorted(expected), "received": sorted(ov.keys())},
            )


def get_or_create_variant(db: Session, product: Product, ov: dict) -> tuple[Variant, bool]:
    ov = normalize_options(ov)
    key = option_key(ov)
    existing = db.scalar(select(Variant).where(Variant.product_id == product.id, Variant.option_key == key))
    if existing:
        return existing, False
    check_option_names(product, ov)
    variant = Variant(product_id=product.id, option_values=ov, option_key=key)
    db.add(variant)
    db.flush()
    db.refresh(product)
    return variant, True


def would_create_cycle(db: Session, category_id: int, new_parent_id: int) -> bool:
    seen, cur = set(), new_parent_id
    while cur is not None:
        if cur == category_id or cur in seen:
            return True
        seen.add(cur)
        cur = db.scalar(select(Category.parent_id).where(Category.id == cur))
    return False


def descendant_ids(db: Session, category_id: int) -> list[int]:
    result, frontier = [], [category_id]
    while frontier:
        children = list(db.scalars(select(Category.id).where(Category.parent_id.in_(frontier))))
        result.extend(children)
        frontier = children
    return result
