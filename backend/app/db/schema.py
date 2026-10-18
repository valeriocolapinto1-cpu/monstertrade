from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
    text,
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

trade_ideas = Table(
    "trade_ideas",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "instrument_id",
        Integer,
        ForeignKey("instruments.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("horizon", String(8), nullable=False),
    Column("direction", String(8), nullable=False, server_default="long"),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("signal_ts", DateTime(timezone=True), nullable=False),
    Column("score", Float, nullable=False),
    Column("entry", Float, nullable=False),
    Column("stop", Float, nullable=False),
    Column("target", Float, nullable=False),
    Column("size_eur", Float, nullable=False),
    Column("risk_eur", Float, nullable=False),
    Column("costs_eur", Float, nullable=False),
    Column("risk_label", String(16), nullable=False),
    Column("motivation", Text, nullable=False),
    Column("warnings", JSONB, nullable=False, server_default="[]"),
    Column("status", String(12), nullable=False, server_default="proposta"),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("instrument_id", "horizon", "signal_ts", name="uq_trade_ideas_signal"),
    CheckConstraint("direction IN ('long')", name="direction_valid"),
    CheckConstraint("horizon IN ('day', 'swing', 'long')", name="horizon_valid"),
    CheckConstraint(
        "status IN ('proposta', 'aperta', 'chiusa', 'scaduta', 'annullata')", name="status_valid"
    ),
    CheckConstraint("stop < entry AND entry < target", name="levels_valid"),
    CheckConstraint("size_eur > 0 AND risk_eur > 0 AND costs_eur >= 0", name="amounts_valid"),
    CheckConstraint(
        "risk_label IN ('Basso', 'Medio', 'Alto', 'Molto alto')", name="risk_label_valid"
    ),
)

trades = Table(
    "trades",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "idea_id",
        Integer,
        ForeignKey("trade_ideas.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    ),
    Column("mode", String(10), nullable=False, server_default="simulato"),
    Column("entry_ts", DateTime(timezone=True), nullable=False),
    Column("entry_price", Float, nullable=False),
    Column("size_eur", Float, nullable=False),
    Column("exit_ts", DateTime(timezone=True), nullable=True),
    Column("exit_price", Float, nullable=True),
    Column("exit_reason", String(12), nullable=True),
    Column("pnl_eur", Float, nullable=True),
    Column("fees_eur", Float, nullable=True),
    Column("status", String(8), nullable=False, server_default="aperta"),
    CheckConstraint("mode IN ('simulato', 'reale')", name="mode_valid"),
    CheckConstraint("status IN ('aperta', 'chiusa')", name="status_valid"),
    CheckConstraint(
        "exit_reason IS NULL OR exit_reason IN ('stop', 'obiettivo', 'tempo', 'segnale')",
        name="exit_reason_valid",
    ),
    CheckConstraint("entry_price > 0 AND size_eur > 0", name="amounts_valid"),
)

broker_snapshots = Table(
    "broker_snapshots",
    metadata,
    Column("day", Date, primary_key=True),
    # Conto letto: "live" (reale) o "demo" (prova), per non mescolare i valori.
    Column("env", String(8), primary_key=True, server_default="live"),
    Column("first_seen", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("total", Float, nullable=False),
    Column("cash", Float, nullable=False),
    Column("invested", Float, nullable=False),
)

# Registro di ogni ordine: la riga si scrive PRIMA dell'invio e non si cancella mai.
orders = Table(
    "orders",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("idea_id", Integer, ForeignKey("trade_ideas.id", ondelete="RESTRICT"), nullable=False),
    Column("mode", String(8), nullable=False),
    Column("ticker", String(32), nullable=False),
    Column("quantity", Float, nullable=False),
    Column("estimated_eur", Float, nullable=False),
    Column("stop_pct", Float, nullable=False),
    Column("status", String(12), nullable=False, server_default="in_attesa"),
    Column("broker_order_id", String(64), nullable=True),
    Column("fill_price", Float, nullable=True),
    Column("stop_status", String(16), nullable=True),
    Column("stop_price", Float, nullable=True),
    Column("stop_order_id", String(64), nullable=True),
    Column("error", Text, nullable=True),
    Column("request", JSONB, nullable=False, server_default="{}"),
    Column("response", JSONB, nullable=False, server_default="{}"),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("mode IN ('demo', 'live')", name="mode_valid"),
    CheckConstraint(
        "status IN ('in_attesa', 'inviato', 'eseguito', 'rifiutato', 'incerto')",
        name="status_valid",
    ),
    CheckConstraint("quantity > 0 AND estimated_eur > 0", name="amounts_valid"),
    # Una sola richiesta valida per proposta: ritentare è possibile solo se rifiutata.
    Index(
        "uq_orders_idea_active",
        "idea_id",
        unique=True,
        postgresql_where=text("status <> 'rifiutato'"),
    ),
)

# Comandi persistenti. Senza riga il blocco totale è ATTIVO (impostazione sicura).
controls = Table(
    "controls",
    metadata,
    Column("key", String(32), primary_key=True),
    Column("active", Boolean, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
