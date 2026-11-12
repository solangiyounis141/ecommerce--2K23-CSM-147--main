"""Idempotent seed: `python -m app.seed`. Optional admin from ADMIN_EMAIL / ADMIN_PASSWORD."""
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import hash_password
from .database import SessionLocal
from .models import Category, Product, Sku, User
from .services import get_or_create_variant

CATEGORIES = [  # (slug, name, parent_slug)
    ("clothing", "Clothing", None), ("t-shirts", "T-Shirts", "clothing"),
    ("accessories", "Accessories", "clothing"),
    ("footwear", "Footwear", None), ("sneakers", "Sneakers", "footwear"),
]
PRODUCTS = [  # slug, name, category, status, [(options, code, price, stock)]
    ("classic-cotton-tee", "Classic Cotton Tee", "t-shirts", "published", [
        ({"size": "M", "color": "Black"}, "TEE-BLK-M", "1499.00", 25),
        ({"size": "L", "color": "Black"}, "TEE-BLK-L", "1499.00", 10),
        ({"size": "M", "color": "White"}, "TEE-WHT-M", "1399.00", 0),
        # White/L is intentionally NOT created: unavailable combination (CAT04)
    ]),
    ("canvas-sneaker", "Canvas Sneaker", "sneakers", "published", [
        ({"size": "42"}, "SNK-42", "4999.00", 8),
        ({"size": "43"}, "SNK-43", "4999.00", 3),
    ]),
    ("leather-belt", "Leather Belt", "accessories", "draft", [
        ({}, "BELT-STD", "1999.00", 15),  # no variants: default variant
    ]),
]


def run_seed(db: Session, admin_email: str | None = None, admin_password: str | None = None) -> None:
    cats: dict[str, Category] = {}
    for slug, name, parent in CATEGORIES:
        cat = db.scalar(select(Category).where(Category.slug == slug))
        if not cat:
            cat = Category(slug=slug, name=name, parent_id=cats[parent].id if parent else None)
            db.add(cat)
            db.flush()
        cats[slug] = cat
    for slug, name, cat_slug, status, skus in PRODUCTS:
        p = db.scalar(select(Product).where(Product.slug == slug))
        if not p:
            p = Product(slug=slug, name=name, category_id=cats[cat_slug].id, status="draft",
                        description=f"{name} - seed data")
            db.add(p)
            db.flush()
        for options, code, price, stock in skus:
            if db.scalar(select(Sku.id).where(Sku.code == code)):
                continue
            variant, _ = get_or_create_variant(db, p, options)
            db.add(Sku(variant_id=variant.id, code=code, price=price, stock_quantity=stock))
        db.flush()
        p.status = status
    if admin_email and admin_password and not db.scalar(select(User.id).where(User.email == admin_email.lower())):
        db.add(User(email=admin_email.lower(), password_hash=hash_password(admin_password),
                    full_name="Store Admin", role="admin"))
    db.commit()


if __name__ == "__main__":
    with SessionLocal() as session:
        run_seed(session, os.getenv("ADMIN_EMAIL"), os.getenv("ADMIN_PASSWORD"))
    print("Seed complete.")
