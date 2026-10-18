from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)

instruments = Table(
    "instruments",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("symbol", String(16), nullable=False, unique=True),
    Column("name", Text, nullable=False),
    Column("kind", String(24), nullable=False),
    Column("currency", String(8), nullable=False),
    Column("calendar", String(8), nullable=False),
    Column("leverage", Float, nullable=False, server_default="1"),
    Column("underlying_id", Integer, ForeignKey("instruments.id"), nullable=True),
    Column("ter", Float, nullable=False, server_default="0"),
    Column("reference_ticker", String(32), nullable=True),
    Column("t212_ticker", String(32), nullable=True),
    Column("active", Boolean, nullable=False, server_default="true"),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint(
        "kind IN ('index', 'leveraged_etf', 'crypto', 'crypto_etp')", name="kind_valid"
    ),
    CheckConstraint("leverage <> 0", name="leverage_nonzero"),
)

prices = Table(
    "prices",
    metadata,
    Column(
        "instrument_id",
        Integer,
        ForeignKey("instruments.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("timeframe", String(4), primary_key=True),
    Column("ts", DateTime(timezone=True), primary_key=True),
    Column("open", Float, nullable=False),
    Column("high", Float, nullable=False),
    Column("low", Float, nullable=False),
    Column("close", Float, nullable=False),
    Column("volume", Float, nullable=False, server_default="0"),
    Column("source", String(16), nullable=False),
    CheckConstraint("timeframe IN ('5m', '15m', '1d')", name="timeframe_valid"),
    CheckConstraint("high >= low AND low > 0", name="ohlc_valid"),
)

indicators = Table(
    "indicators",
    metadata,
    Column(
        "instrument_id",
        Integer,
        ForeignKey("instruments.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("timeframe", String(4), primary_key=True),
    Column("ts", DateTime(timezone=True), primary_key=True),
    Column("name", String(32), primary_key=True),
    Column("value", Float, nullable=False),
    CheckConstraint("timeframe IN ('5m', '15m', '1d')", name="timeframe_valid"),
)

sentiment = Table(
    "sentiment",
    metadata,
    Column(
        "instrument_id",
        Integer,
        ForeignKey("instruments.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("date", Date, primary_key=True),
    Column("source", String(16), primary_key=True),
    Column("score", Float, nullable=False),
    Column("mentions", Integer, nullable=False),
    CheckConstraint("score >= -1 AND score <= 1", name="score_range"),
    CheckConstraint("mentions >= 0", name="mentions_positive"),
)

signals = Table(
    "signals",
    metadata,
    Column(
        "instrument_id",
        Integer,
        ForeignKey("instruments.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("horizon", String(8), primary_key=True),
    Column("ts", DateTime(timezone=True), primary_key=True),
    Column("score", Float, nullable=False),
    Column("components", JSONB, nullable=False),
    Column("favorable", JSONB, nullable=False),
    Column("contrary", JSONB, nullable=False),
    Column("risk_label", String(16), nullable=False),
    CheckConstraint("score >= -100 AND score <= 100", name="score_range"),
    CheckConstraint("horizon IN ('day', 'swing', 'long')", name="horizon_valid"),
    CheckConstraint(
        "risk_label IN ('Basso', 'Medio', 'Alto', 'Molto alto')", name="risk_label_valid"
    ),
)
