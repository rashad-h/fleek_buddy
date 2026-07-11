"""init items, negotiations and messages tables

Revision ID: 0001
Revises:
Create Date: 2026-07-11

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("brand", sa.String(), nullable=False),
        sa.Column("vendor_name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("condition", sa.String(), nullable=False),
        sa.Column("sizes", sa.String(), nullable=False),
        sa.Column("piece_count", sa.Integer(), nullable=False),
        sa.Column("price_per_piece", sa.Numeric(10, 2), nullable=False),
        sa.Column("bundle_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("original_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("discount_percent", sa.Integer(), nullable=True),
        sa.Column("shipping_days_min", sa.Integer(), nullable=False),
        sa.Column("shipping_days_max", sa.Integer(), nullable=False),
        sa.Column("is_single_brand", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("image_url", sa.String(), nullable=False),
        sa.Column("negotiable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("high_quantity", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("buying_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("lowest_bundle_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("lowest_price_per_piece", sa.Numeric(10, 2), nullable=False),
        sa.Column("grades", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "negotiations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("buyer_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("current_offer", sa.Numeric(10, 2), nullable=True),
        sa.Column("current_selection", postgresql.JSONB(), nullable=True),
        sa.Column("agreed_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_negotiations_item_id", "negotiations", ["item_id"])
    op.create_index("ix_negotiations_buyer_id", "negotiations", ["buyer_id"])
    op.create_index("ix_negotiations_item_buyer", "negotiations", ["item_id", "buyer_id"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "negotiation_id",
            sa.Integer(),
            sa.ForeignKey("negotiations.id"),
            nullable=False,
        ),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("offer_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("offer_selection", postgresql.JSONB(), nullable=True),
        sa.Column("action", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_messages_negotiation_id", "messages", ["negotiation_id"])


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("negotiations")
    op.drop_table("items")
