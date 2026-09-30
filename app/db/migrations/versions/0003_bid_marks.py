"""Add bid_marks: bids an officer has flagged to check later

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bid_marks",
        sa.Column("bid_id", sa.Text(), sa.ForeignKey("bids.bid_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("marked_by", sa.Text(), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("marked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("bid_marks")
