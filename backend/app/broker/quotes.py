"""Prezzo reale del titolo quotato, per stimare la quantità di un ordine.

Le serie degli ETF a leva sono sintetiche (base 100): per un ordine serve il prezzo
del titolo vero. Yahoo ha un ritardo di circa 15 minuti, per questo la quantità si
arrotonda per difetto e l'importo non supera mai il limite per ordine.
"""

from dataclasses import dataclass

import yfinance as yf

from app.broker.trading212 import BrokerError


@dataclass(frozen=True)
class Quote:
    price: float  # nella valuta di quotazione (GBp per i pence)
    currency: str
    eur_per_unit: float  # controvalore in euro di una quota


def _last(symbol: str) -> float:
    try:
        value = yf.Ticker(symbol).fast_info.get("last_price")
    except Exception:
        raise BrokerError(f"Cambio non disponibile ({symbol})") from None
    if not isinstance(value, int | float) or value <= 0:
        raise BrokerError(f"Prezzo non disponibile per {symbol}")
    return float(value)


def yahoo_quote(symbol: str) -> Quote:
    try:
        info = yf.Ticker(symbol).fast_info
        price = info.get("last_price")
        currency = str(info.get("currency") or "")
    except Exception:  # yfinance solleva eccezioni eterogenee
        raise BrokerError(f"Prezzo non disponibile per {symbol}") from None
    if not isinstance(price, int | float) or price <= 0 or not currency:
        raise BrokerError(f"Prezzo non disponibile per {symbol}")
    unit = float(price)
    ccy = currency
    if ccy in ("GBp", "GBX"):
        unit, ccy = unit / 100, "GBP"
    fx = 1.0 if ccy == "EUR" else _last(f"{ccy}EUR=X")
    return Quote(price=float(price), currency=currency, eur_per_unit=unit * fx)
