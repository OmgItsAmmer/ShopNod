"""Shopper columns for Plan 1: shoppers.platform, shoppers.last_seen_at.

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    # 0001 builds tables from the current models, so on a fresh database these columns already exist.
    cols = _columns("shoppers")
    if "platform" not in cols:
        op.add_column("shoppers", sa.Column("platform", sa.String(16), nullable=True))
    if "last_seen_at" not in cols:
        op.add_column("shoppers", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
        op.create_index("ix_shoppers_last_seen_at", "shoppers", ["last_seen_at"])


def downgrade() -> None:
    cols = _columns("shoppers")
    if "last_seen_at" in cols:
        op.drop_index("ix_shoppers_last_seen_at", table_name="shoppers")
        op.drop_column("shoppers", "last_seen_at")
    if "platform" in cols:
        op.drop_column("shoppers", "platform")
