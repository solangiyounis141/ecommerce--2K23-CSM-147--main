"""Sprint 2 catalog foundation

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

JSONType = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
now = sa.func.now()


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False, server_default=""),
        sa.Column("role", sa.String(20), nullable=False, server_default="customer"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=now),
        sa.CheckConstraint("role IN ('customer','admin')", name="ck_users_role"),
    )
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("parent_id", sa.Integer, sa.ForeignKey("categories.id", ondelete="RESTRICT", onupdate="CASCADE")),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(140), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=now),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=now),
        sa.CheckConstraint("parent_id IS NULL OR parent_id <> id", name="ck_categories_not_own_parent"),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("category_id", sa.Integer, sa.ForeignKey("categories.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(220), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("specifications", JSONType),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=now),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=now),
        sa.CheckConstraint("status IN ('draft','published','archived')", name="ck_products_status"),
    )
    op.create_table(
        "variants",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False),
        sa.Column("option_values", JSONType, nullable=False),
        sa.Column("option_key", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=now),
        sa.UniqueConstraint("product_id", "option_key", name="uq_variants_product_option_key"),
    )
    op.create_table(
        "skus",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("variant_id", sa.Integer, sa.ForeignKey("variants.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("stock_quantity", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=now),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=now),
        sa.CheckConstraint("price >= 0", name="ck_skus_price_non_negative"),
        sa.CheckConstraint("stock_quantity >= 0", name="ck_skus_stock_non_negative"),
    )
    op.create_table(
        "assets",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False),
        sa.Column("variant_id", sa.Integer, sa.ForeignKey("variants.id", ondelete="SET NULL", onupdate="CASCADE")),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="gallery"),
        sa.Column("alt_text", sa.String(255), nullable=False, server_default=""),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.CheckConstraint("role IN ('primary','gallery','swatch')", name="ck_assets_role"),
    )
    op.create_index("ix_products_category_id", "products", ["category_id"])
    op.create_index("ix_variants_product_id", "variants", ["product_id"])
    op.create_index("ix_skus_variant_id", "skus", ["variant_id"])


def downgrade() -> None:
    for t in ("assets", "skus", "variants", "products", "categories", "users"):
        op.drop_table(t)
