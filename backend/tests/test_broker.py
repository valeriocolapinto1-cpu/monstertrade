import base64

import httpx
import pytest

from app.broker.service import match_instrument
from app.broker.trading212 import (
    BrokerError,
    CachedBroker,
    Trading212ReadOnly,
    parse_positions,
    parse_summary,
)

KEY = "-".join(["chiave", "finta"])
SECRET = "-".join(["segreto", "finto"])

SUMMARY = {
    "currency": "EUR",
    "totalValue": 1250.5,
    "cash": {"availableToTrade": 400.0},
    "investments": {"currentValue": 850.5, "unrealizedProfitLoss": 12.3},
}
POSITIONS = [
    {
        "ticker": "3USLl_EQ",
        "quantity": 2.5,
        "averagePrice": 60.0,
        "currentPrice": 64.0,
        "walletImpact": {"currentValue": 160.0, "unrealizedProfitLoss": 10.0},
    },
    {
        "instrument": {"ticker": "AAPL_US_EQ"},
        "quantity": 1,
        "averagePrice": 200,
        "currentPrice": 210,
    },
]


def transport(seen: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/equity/account/summary"):
            return httpx.Response(200, json=SUMMARY)
        if request.url.path.endswith("/equity/positions"):
            return httpx.Response(200, json=POSITIONS)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_reads_account_with_basic_auth_and_only_get() -> None:
    seen: list[httpx.Request] = []
    broker = Trading212ReadOnly(httpx.Client(transport=transport(seen)), KEY, SECRET, "demo")
    summary = broker.account_summary()
    positions = broker.positions()
    assert summary.total == 1250.5 and summary.cash == 400.0 and summary.invested == 850.5
    assert [p.ticker for p in positions] == ["3USLl_EQ", "AAPL_US_EQ"]
    assert positions[1].value == pytest.approx(210.0)
    assert {r.method for r in seen} == {"GET"}
    assert all(str(r.url).startswith("https://demo.trading212.com/api/v0/") for r in seen)
    expected = base64.b64encode(f"{KEY}:{SECRET}".encode()).decode()
    assert seen[0].headers["Authorization"] == f"Basic {expected}"


def test_client_has_no_order_capability() -> None:
    names = {n for n in dir(Trading212ReadOnly) if not n.startswith("__")}
    assert not {
        n
        for n in names
        if any(w in n.lower() for w in ("order", "buy", "sell", "post", "cancel", "delete"))
    }


def test_errors_never_contain_credentials() -> None:
    for status in (401, 403, 429, 500):
        client = httpx.Client(transport=httpx.MockTransport(lambda r, s=status: httpx.Response(s)))
        broker = Trading212ReadOnly(client, KEY, SECRET)
        with pytest.raises(BrokerError) as info:
            broker.account_summary()
        assert KEY not in str(info.value) and SECRET not in str(info.value)
        assert info.value.__cause__ is None


def test_invalid_payloads() -> None:
    with pytest.raises(BrokerError):
        parse_summary([1, 2])
    with pytest.raises(BrokerError):
        parse_positions({"a": 1})
    assert parse_summary({"total": 10, "free": 4, "invested": 6, "ppl": 0.5}).cash == 4


def test_cache_limits_requests() -> None:
    seen: list[httpx.Request] = []
    broker = Trading212ReadOnly(httpx.Client(transport=transport(seen)), KEY, SECRET)
    cached = CachedBroker(broker, ttl=60)
    cached.snapshot()
    cached.snapshot()
    assert len(seen) == 2  # una lettura del conto e una delle posizioni


def test_ticker_mapping() -> None:
    spx3l = match_instrument("3USLl_EQ")
    assert spx3l is not None and spx3l.symbol == "SPX3L"
    qqq3 = match_instrument("QQQ3l_EQ")
    assert qqq3 is not None and qqq3.symbol == "NDX3L"
    assert match_instrument("AAPL_US_EQ") is None
    assert match_instrument("???") is None
