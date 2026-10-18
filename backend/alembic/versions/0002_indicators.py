"""indicators

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "indicators",
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("timeframe", sa.String(length=4), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.CheckConstraint(
            "timeframe IN ('5m', '15m', '1d')", name=op.f("ck_indicators_timeframe_valid")
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name=op.f("fk_indicators_instrument_id_instruments"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "instrument_id", "timeframe", "ts", "name", name=op.f("pk_indicators")
        ),
    )


def downgrade() -> None:
    op.drop_table("indicators")
