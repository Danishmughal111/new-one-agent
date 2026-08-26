"""add affiliate offers cache

Revision ID: d4e5f6a7b8c9
Revises: c3b8e2a4f1d7
Create Date: 2026-08-25 01:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c3b8e2a4f1d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trendera_affiliate_offers",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("product_id", sa.String(length=32), nullable=False),
        sa.Column("affiliate_url", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=255), nullable=False),
        sa.Column("provider_product_name", sa.Text(), nullable=True),
        sa.Column("match_score", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id"),
    )
    op.create_index(
        "ix_trendera_affiliate_offers_product_id", "trendera_affiliate_offers", ["product_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_trendera_affiliate_offers_product_id", table_name="trendera_affiliate_offers")
    op.drop_table("trendera_affiliate_offers")
