"""Universo iniziale confermato dall'utente (docs/decisioni.md).

Gli strumenti a leva e gli ETP crypto non hanno dati gratuiti affidabili: la serie si
ricava dal sottostante applicando il fattore di leva con ribilanciamento giornaliero.
Ticker e ISIN di riferimento vanno verificati su Trading 212 prima di operare.
"""

from dataclasses import dataclass, field
from enum import StrEnum


class Kind(StrEnum):
    INDEX = "index"
    LEVERAGED_ETF = "leveraged_etf"
    CRYPTO = "crypto"
    CRYPTO_ETP = "crypto_etp"


class Calendar(StrEnum):
    NYSE = "XNYS"
    ALWAYS = "24/7"


@dataclass(frozen=True)
class SourceRef:
    source: str
    symbol: str


@dataclass(frozen=True)
class InstrumentSpec:
    symbol: str
    name: str
    kind: Kind
    currency: str
    calendar: Calendar
    leverage: float = 1.0
    underlying: str | None = None
    # Costo annuo dello strumento (TER) usato nella serie sintetica.
    ter: float = 0.0
    reference_ticker: str | None = None
    # Simbolo Yahoo del titolo quotato, usato solo per stimare la quantità di un ordine.
    quote_symbol: str | None = None
    sources: tuple[SourceRef, ...] = field(default_factory=tuple)

    @property
    def orderable(self) -> bool:
        """Ordinabile su Trading 212 Invest: ticker verificato e prezzo reale disponibile."""
        return bool(self.quote_symbol and self.reference_ticker)

    @property
    def synthetic(self) -> bool:
        return self.underlying is not None


def _lev(
    symbol: str,
    name: str,
    underlying: str,
    leverage: float,
    ter: float,
    ticker: str,
    ccy: str,
    quote: str | None = None,
) -> InstrumentSpec:
    return InstrumentSpec(
        symbol=symbol,
        name=name,
        kind=Kind.LEVERAGED_ETF,
        currency=ccy,
        calendar=Calendar.NYSE,
        leverage=leverage,
        underlying=underlying,
        ter=ter,
        reference_ticker=ticker,
        quote_symbol=quote,
    )


UNIVERSE: tuple[InstrumentSpec, ...] = (
    InstrumentSpec(
        "SPX",
        "S&P 500",
        Kind.INDEX,
        "USD",
        Calendar.NYSE,
        sources=(SourceRef("twelvedata", "SPX"), SourceRef("yfinance", "^GSPC")),
    ),
    InstrumentSpec(
        "NDX",
        "Nasdaq 100",
        Kind.INDEX,
        "USD",
        Calendar.NYSE,
        sources=(SourceRef("twelvedata", "NDX"), SourceRef("yfinance", "^NDX")),
    ),
    InstrumentSpec(
        "SOX",
        "PHLX Semiconductor",
        Kind.INDEX,
        "USD",
        Calendar.NYSE,
        sources=(SourceRef("twelvedata", "SOX"), SourceRef("yfinance", "^SOX")),
    ),
    _lev("SPX3L", "S&P 500 3x Long", "SPX", 3, 0.0075, "3USL", "USD", "3USL.L"),
    _lev("SPX3S", "S&P 500 3x Short", "SPX", -3, 0.0080, "3USS", "USD", "3USS.L"),
    _lev("NDX3L", "Nasdaq 100 3x Long", "NDX", 3, 0.0075, "QQQ3", "USD", "QQQ3.L"),
    _lev("NDX3S", "Nasdaq 100 3x Short", "NDX", -3, 0.0080, "QQQS", "USD", "QQQS.L"),
    _lev("NDX2L", "Nasdaq 100 2x Long", "NDX", 2, 0.0060, "LQQ", "EUR", "LQQ.PA"),
    _lev("SOX3L", "Semiconduttori 3x Long", "SOX", 3, 0.0075, "da verificare", "USD"),
    InstrumentSpec(
        "BTC",
        "Bitcoin",
        Kind.CRYPTO,
        "USDT",
        Calendar.ALWAYS,
        sources=(SourceRef("binance", "BTCUSDT"), SourceRef("yfinance", "BTC-USD")),
    ),
    InstrumentSpec(
        "ETH",
        "Ethereum",
        Kind.CRYPTO,
        "USDT",
        Calendar.ALWAYS,
        sources=(SourceRef("binance", "ETHUSDT"), SourceRef("yfinance", "ETH-USD")),
    ),
    InstrumentSpec(
        "SOL",
        "Solana",
        Kind.CRYPTO,
        "USDT",
        Calendar.ALWAYS,
        sources=(SourceRef("binance", "SOLUSDT"), SourceRef("yfinance", "SOL-USD")),
    ),
    InstrumentSpec(
        "BTCETP",
        "ETP fisico Bitcoin",
        Kind.CRYPTO_ETP,
        "USD",
        Calendar.ALWAYS,
        underlying="BTC",
        ter=0.0035,
        reference_ticker="da verificare",
    ),
    InstrumentSpec(
        "ETHETP",
        "ETP fisico Ethereum",
        Kind.CRYPTO_ETP,
        "USD",
        Calendar.ALWAYS,
        underlying="ETH",
        ter=0.0035,
        reference_ticker="da verificare",
    ),
)

BY_SYMBOL = {spec.symbol: spec for spec in UNIVERSE}


def base_instruments() -> list[InstrumentSpec]:
    return [s for s in UNIVERSE if not s.synthetic]


def synthetic_instruments() -> list[InstrumentSpec]:
    return [s for s in UNIVERSE if s.synthetic]
