"""orders e controls (passo C), conto per ambiente in broker_snapshots

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "broker_snapshots",
        sa.Column("env", sa.String(length=8), server_default="live", nullable=False),
    )
    op.drop_constraint("pk_broker_snapshots", "broker_snapshots", type_="primary")
    op.create_primary_key("pk_broker_snapshots", "broker_snapshots", ["day", "env"])
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("idea_id", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(length=8), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("estimated_eur", sa.Float(), nullable=False),
        sa.Column("stop_pct", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=12), server_default="in_attesa", nullable=False),
        sa.Column("broker_order_id", sa.String(length=64), nullable=True),
        sa.Column("fill_price", sa.Float(), nullable=True),
        sa.Column("stop_status", sa.String(length=16), nullable=True),
        sa.Column("stop_price", sa.Float(), nullable=True),
        sa.Column("stop_order_id", sa.String(length=64), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "request", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column(
            "response",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("mode IN ('demo', 'live')", name=op.f("ck_orders_mode_valid")),
        sa.CheckConstraint(
            "status IN ('in_attesa', 'inviato', 'eseguito', 'rifiutato', 'incerto')",
            name=op.f("ck_orders_status_valid"),
        ),
        sa.CheckConstraint(
            "quantity > 0 AND estimated_eur > 0", name=op.f("ck_orders_amounts_valid")
        ),
        sa.ForeignKeyConstraint(
            ["idea_id"],
            ["trade_ideas.id"],
            name=op.f("fk_orders_idea_id_trade_ideas"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
    )
    op.create_index(
        "uq_orders_idea_active",
        "orders",
        ["idea_id"],
        unique=True,
        postgresql_where=sa.text("status <> 'rifiutato'"),
    )
    op.create_table(
        "controls",
        sa.Column("key", sa.String(length=32), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_controls")),
    )


def downgrade() -> None:
    op.drop_table("controls")
    op.drop_index("uq_orders_idea_active", table_name="orders")
    op.drop_table("orders")
    op.execute("DELETE FROM broker_snapshots WHERE env <> 'live'")
    op.drop_constraint("pk_broker_snapshots", "broker_snapshots", type_="primary")
    op.create_primary_key("pk_broker_snapshots", "broker_snapshots", ["day"])
    op.drop_column("broker_snapshots", "env")
