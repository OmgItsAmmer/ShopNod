"""Remove the Stripe integration: subscriptions, stripe_events, shops.stripe_customer_id, meter_events.stripe_ref.

`meter_events` stays: it is the usage ledger behind the billing page (one row per billable redemption).

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    tables = _tables()
    for t in ("stripe_events", "subscriptions"):
        if t in tables:
            op.drop_table(t)
    if "stripe_customer_id" in _columns("shops"):
        with op.batch_alter_table("shops") as b:
            b.drop_column("stripe_customer_id")
    if "stripe_ref" in _columns("meter_events"):
        with op.batch_alter_table("meter_events") as b:
            b.drop_column("stripe_ref")


def downgrade() -> None:
    if "stripe_ref" not in _columns("meter_events"):
        with op.batch_alter_table("meter_events") as b:
            b.add_column(sa.Column("stripe_ref", sa.String(120), nullable=True))
    if "stripe_customer_id" not in _columns("shops"):
        with op.batch_alter_table("shops") as b:
            b.add_column(sa.Column("stripe_customer_id", sa.String(80), nullable=True))
