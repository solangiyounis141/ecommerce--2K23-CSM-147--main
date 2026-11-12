from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JSONType = sa.JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('customer','admin')", name="ck_users_role"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120), default="")
    role: Mapped[str] = mapped_column(String(20), default="customer", server_default="customer")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="ck_categories_not_own_parent"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(140), unique=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=sa.true())
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("status IN ('draft','published','archived')", name="ck_products_status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT", onupdate="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(220), unique=True)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    status: Mapped[str] = mapped_column(String(20), default="draft", server_default="draft")
    specifications: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    variants: Mapped[list["Variant"]] = relationship(back_populates="product", order_by="Variant.id")


class Variant(Base):
    __tablename__ = "variants"
    __table_args__ = (UniqueConstraint("product_id", "option_key", name="uq_variants_product_option_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE", onupdate="CASCADE")
    )
    option_values: Mapped[dict] = mapped_column(JSONType)  # e.g. {"size": "M", "color": "Black"}
    option_key: Mapped[str] = mapped_column(String(255))  # canonical form, enforces one row per combination
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    product: Mapped[Product] = relationship(back_populates="variants")
    skus: Mapped[list["Sku"]] = relationship(back_populates="variant", order_by="Sku.id")


class Sku(Base):
    __tablename__ = "skus"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_skus_price_non_negative"),
        CheckConstraint("stock_quantity >= 0", name="ck_skus_stock_non_negative"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    variant_id: Mapped[int] = mapped_column(
        ForeignKey("variants.id", ondelete="RESTRICT", onupdate="CASCADE")
    )
    code: Mapped[str] = mapped_column(String(40), unique=True)
    price = mapped_column(Numeric(10, 2))
    stock_quantity: Mapped[int] = mapped_column(default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(default=True, server_default=sa.true())
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    variant: Mapped[Variant] = relationship(back_populates="skus")


class Asset(Base):  # table only in Sprint 2; upload/API is Sprint 3
    __tablename__ = "assets"
    __table_args__ = (
        CheckConstraint("role IN ('primary','gallery','swatch')", name="ck_assets_role"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE", onupdate="CASCADE")
    )
    variant_id: Mapped[int | None] = mapped_column(
        ForeignKey("variants.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True
    )
    storage_key: Mapped[str] = mapped_column(String(500))
    role: Mapped[str] = mapped_column(String(20), default="gallery", server_default="gallery")
    alt_text: Mapped[str] = mapped_column(String(255), default="", server_default="")
    sort_order: Mapped[int] = mapped_column(default=0, server_default="0")
