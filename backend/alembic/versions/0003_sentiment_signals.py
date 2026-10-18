"""sentiment e signals

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sentiment",
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("mentions", sa.Integer(), nullable=False),
        sa.CheckConstraint("mentions >= 0", name=op.f("ck_sentiment_mentions_positive")),
        sa.CheckConstraint("score >= -1 AND score <= 1", name=op.f("ck_sentiment_score_range")),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name=op.f("fk_sentiment_instrument_id_instruments"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("instrument_id", "date", "source", name=op.f("pk_sentiment")),
    )
    op.create_table(
        "signals",
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("horizon", sa.String(length=8), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("components", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("favorable", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("contrary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("risk_label", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "horizon IN ('day', 'swing', 'long')", name=op.f("ck_signals_horizon_valid")
        ),
        sa.CheckConstraint(
            "risk_label IN ('Basso', 'Medio', 'Alto', 'Molto alto')",
            name=op.f("ck_signals_risk_label_valid"),
        ),
        sa.CheckConstraint("score >= -100 AND score <= 100", name=op.f("ck_signals_score_range")),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name=op.f("fk_signals_instrument_id_instruments"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("instrument_id", "horizon", "ts", name=op.f("pk_signals")),
    )


def downgrade() -> None:
    op.drop_table("signals")
    op.drop_table("sentiment")
