"""Initial schema: every table (Plan 3 §0.4), the Haversine SQL function and the required indexes.

Revision ID: 0001
Revises:
"""
from alembic import op

from shopnod_core.geo import HAVERSINE_SQL
from shopnod_core.models import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind)
    if bind.dialect.name == "postgresql":
        op.execute(HAVERSINE_SQL)
    # Required indexes. Most are declared on the models; these `IF NOT EXISTS` statements make the contract explicit.
    op.execute("CREATE INDEX IF NOT EXISTS ix_shops_geohash6 ON shops (geohash6)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_offers_status_ends_at ON offers (status, ends_at)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_claims_token_jti ON claims (token_jti)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_redemptions_claim_id ON redemptions (claim_id)")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS haversine_m(double precision, double precision, double precision, double precision)")
    Base.metadata.drop_all(bind)
