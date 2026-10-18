"""broker_snapshots: valore del conto reale a inizio giornata

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "broker_snapshots",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column(
            "first_seen",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("total", sa.Float(), nullable=False),
        sa.Column("cash", sa.Float(), nullable=False),
        sa.Column("invested", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("day", name=op.f("pk_broker_snapshots")),
    )


def downgrade() -> None:
    op.drop_table("broker_snapshots")
