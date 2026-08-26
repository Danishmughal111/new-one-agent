"""add product affiliate_url

Revision ID: c3b8e2a4f1d7
Revises: 024a14474680
Create Date: 2026-08-25 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "c3b8e2a4f1d7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trendera_products", sa.Column("affiliate_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("trendera_products", "affiliate_url")
