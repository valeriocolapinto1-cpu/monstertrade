"""Passo C: nessun ordine senza conferma, nessun ordine oltre i limiti, nessuna chiave esposta."""

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, Engine, insert, select

from app.api import deps
from app.broker.orders import Trading212Orders
from app.broker.quotes import Quote
from app.config import Settings, get_settings
from app.data.universe import UNIVERSE
from app.db import repository as repo
from app.db.schema import broker_snapshots, orders, trade_ideas
from app.main import app
from app.trading import engine as trading_engine
from app.trading import orders as svc

KEY = "-".join(["chiave", "ordini", "finta"])
SECRET = "-".join(["segreto", "ordini", "finto"])
FILL = 50.0


def settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "orders_mode": "demo",
        "capital_eur": 1000,
        "max_order_eur": 200,
        "max_orders_per_day": 3,
    }
    return Settings(_env_file=None, **{**base, **overrides})  # type: ignore[call-arg]


def quote(_: str) -> Quote:
    return Quote(price=FILL, currency="USD", eur_per_unit=FILL)


@dataclass
class FakeT212:
    engine: Engine
    total: float = 1000.0
    market: str = "ok"  # ok | rifiuta | timeout | errore
    stop: str = "ok"
    pending: list[dict[str, Any]] = field(default_factory=list)
    seen: list[httpx.Request] = field(default_factory=list)
    logged_before_send: list[bool] = field(default_factory=list)

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        path = request.url.path.removeprefix("/api/v0")
        if request.method == "GET":
            payloads: dict[str, object] = {
                "/equity/account/summary": {
                    "currency": "EUR",
                    "totalValue": self.total,
                    "cash": {"availableToTrade": self.total},
                },
                "/equity/positions": [],
                "/equity/orders": self.pending,
                "/equity/metadata/instruments": [
                    {"ticker": "3USL_US_EQ", "shortName": "3USL"},
                    {"ticker": "3USLl_EQ", "shortName": "3USL"},
                ],
            }
            return httpx.Response(200, json=payloads[path])
        body = json.loads(request.content)
        if path == "/equity/orders/market":
            with self.engine.connect() as c:
                status = c.execute(select(orders.c.status)).scalars().all()
            self.logged_before_send.append(status[-1:] == ["in_attesa"])
            if self.market == "rifiuta":
                return httpx.Response(400, json={"code": "InsufficientFreeForStocksBuy"})
            if self.market == "timeout":
                raise httpx.ReadTimeout("timeout", request=request)
            if self.market == "errore":
                return httpx.Response(503)
            return httpx.Response(
                200,
                json={
                    "id": 101,
                    "status": "FILLED",
                    "filledQuantity": body["quantity"],
                    "fillPrice": FILL,
                },
            )
        if path == "/equity/orders/stop":
            if self.stop != "ok":
                return httpx.Response(400, json={"code": "StopOrdersNotSupported"})
            return httpx.Response(200, json={"id": 102, "status": "NEW"})
        return httpx.Response(404)

    def client(self, env: str = "demo") -> Trading212Orders:
        transport = httpx.MockTransport(self.handler)
        return Trading212Orders(httpx.Client(transport=transport), KEY, SECRET, env)

    def posts(self, suffix: str = "") -> list[httpx.Request]:
        return [r for r in self.seen if r.method == "POST" and r.url.path.endswith(suffix)]


def make_idea(engine: Engine, symbol: str = "SPX3L", stop: float = 96.0) -> int:
    with engine.begin() as conn:
        ids = repo.sync_instruments(conn, UNIVERSE)
        now = datetime.now(UTC)
        return int(
            conn.execute(
                insert(trade_ideas)
                .values(
                    instrument_id=ids[symbol],
                    horizon="swing",
                    signal_ts=now - timedelta(minutes=len(symbol) + stop),
                    score=60,
                    entry=100.0,
                    stop=stop,
                    target=110.0,
                    size_eur=150,
                    risk_eur=10,
                    costs_eur=1,
                    risk_label="Alto",
                    motivation="prova",
                    expires_at=now + timedelta(days=2),
                )
                .returning(trade_ideas.c.id)
            ).scalar_one()
        )


@pytest.fixture
def ready(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[FakeT212, int]]:
    monkeypatch.setattr(trading_engine, "correlations", lambda conn, s, others: {})
    fake = FakeT212(engine)
    idea = make_idea(engine)
    with engine.begin() as conn:
        svc.set_kill_switch(conn, False)
    yield fake, idea


def run_preview(engine: Engine, fake: FakeT212, idea: int, **kw: Any) -> dict[str, object]:
    with engine.connect() as conn:
        return svc.preview(conn, idea, settings(**kw), fake.client(), quote)


def run_place(
    engine: Engine, fake: FakeT212, idea: int, qty: float, token: str, **kw: Any
) -> dict[str, object]:
    with engine.connect() as conn:
        return svc.place(conn, idea, qty, token, settings(**kw), fake.client(), quote)


# --- Blocchi di base ------------------------------------------------------------------


def test_disabled_by_default_and_no_request(engine: Engine) -> None:
    assert Settings(_env_file=None).orders_mode == "disabled"  # type: ignore[call-arg]
    fake = FakeT212(engine)
    idea = make_idea(engine)
    with engine.connect() as conn, pytest.raises(svc.OrderBlockedError, match="disattivati"):
        svc.preview(conn, idea, settings(orders_mode="disabled"), fake.client(), quote)
    assert fake.seen == []


def test_kill_switch_is_active_until_disabled_explicitly(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(trading_engine, "correlations", lambda conn, s, others: {})
    fake = FakeT212(engine)
    idea = make_idea(engine)
    with engine.connect() as conn:
        assert svc.kill_switch_active(conn)
        with pytest.raises(svc.OrderBlockedError, match="Blocco totale"):
            svc.preview(conn, idea, settings(), fake.client(), quote)
    assert fake.seen == []
    with engine.begin() as conn:
        svc.set_kill_switch(conn, False)
    assert run_preview(engine, fake, idea)["quantity"] == 4.0
    with engine.begin() as conn:
        svc.set_kill_switch(conn, True)
    with pytest.raises(svc.OrderBlockedError, match="Blocco totale"):
        run_preview(engine, fake, idea)


def test_broker_env_must_match_mode(engine: Engine, ready: tuple[FakeT212, int]) -> None:
    fake, idea = ready
    with engine.connect() as conn, pytest.raises(svc.OrderBlockedError, match="Ambiente"):
        svc.preview(conn, idea, settings(), fake.client("live"), quote)


# --- Nessun ordine senza conferma -------------------------------------------------------


def test_no_order_without_valid_confirmation(engine: Engine, ready: tuple[FakeT212, int]) -> None:
    fake, idea = ready
    pv = run_preview(engine, fake, idea)
    token = str(pv["token"])
    qty = float(str(pv["quantity"]))
    expired = svc.confirm_token(idea, qty, "demo", now=0)
    other_idea = svc.confirm_token(idea + 1, qty, "demo")
    live = svc.confirm_token(idea, qty, "live")
    bad = [("", qty), ("123.abc", qty), (expired, qty), (other_idea, qty), (live, qty)]
    bad.append((token, qty * 2))  # quantità diversa da quella confermata
    bad.append((token[:-1] + ("0" if token[-1] != "0" else "1"), qty))
    for tok, q in bad:
        with pytest.raises(svc.OrderBlockedError, match="Conferma"):
            run_place(engine, fake, idea, q, tok)
    assert fake.posts() == []
    with engine.connect() as conn:
        assert conn.execute(select(orders)).first() is None


def test_confirmed_order_places_market_and_stop_on_demo(
    engine: Engine, ready: tuple[FakeT212, int]
) -> None:
    fake, idea = ready
    pv = run_preview(engine, fake, idea)
    assert pv["mode"] == "demo" and pv["ticker"] == "3USLl_EQ"
    assert float(str(pv["estimated_eur"])) <= 200
    row = run_place(engine, fake, idea, float(str(pv["quantity"])), str(pv["token"]))
    assert row["status"] == "eseguito" and row["stop_status"] == "attivo"
    assert row["fill_price"] == FILL and row["broker_order_id"] == "101"
    assert fake.logged_before_send == [True]
    market, stop = fake.posts("/market"), fake.posts("/stop")
    assert len(market) == 1 and len(stop) == 1
    assert json.loads(market[0].content) == {"ticker": "3USLl_EQ", "quantity": 4.0}
    stop_body = json.loads(stop[0].content)
    assert stop_body["quantity"] == -4.0
    assert stop_body["stopPrice"] == pytest.approx(FILL * 0.96)
    assert all(str(r.url).startswith("https://demo.trading212.com/api/v0/") for r in fake.seen)


def test_same_idea_cannot_be_ordered_twice(engine: Engine, ready: tuple[FakeT212, int]) -> None:
    fake, idea = ready
    pv = run_preview(engine, fake, idea)
    run_place(engine, fake, idea, float(str(pv["quantity"])), str(pv["token"]))
    with pytest.raises(svc.OrderBlockedError, match="già inviato"):
        run_place(engine, fake, idea, float(str(pv["quantity"])), str(pv["token"]))
    assert len(fake.posts("/market")) == 1


# --- Nessun ordine oltre i limiti ------------------------------------------------------


def test_order_size_never_exceeds_limit(engine: Engine, ready: tuple[FakeT212, int]) -> None:
    fake, idea = ready
    pv = run_preview(engine, fake, idea, max_order_eur=60)
    assert float(str(pv["estimated_eur"])) <= 60
    token = svc.confirm_token(idea, 3.0, "demo")
    with pytest.raises(svc.OrderBlockedError, match="oltre i limiti"):
        run_place(engine, fake, idea, 3.0, token, max_order_eur=60)
    assert fake.posts() == []


def test_daily_order_count_limit(engine: Engine, ready: tuple[FakeT212, int]) -> None:
    fake, idea = ready
    pv = run_preview(engine, fake, idea, max_orders_per_day=1)
    run_place(engine, fake, idea, float(str(pv["quantity"])), str(pv["token"]))
    second = make_idea(engine, "NDX2L", stop=94.0)
    with pytest.raises(svc.OrderBlockedError, match="ordini al giorno"):
        run_preview(engine, fake, second, max_orders_per_day=1)
    assert len(fake.posts("/market")) == 1


def test_daily_loss_limit_blocks_orders(engine: Engine, ready: tuple[FakeT212, int]) -> None:
    fake, idea = ready
    with engine.begin() as conn:
        conn.execute(
            insert(broker_snapshots).values(
                day=datetime.now(UTC).date(), env="demo", total=1000, cash=1000, invested=0
            )
        )
    fake.total = 960.0  # -4% da inizio giornata
    with pytest.raises(svc.OrderBlockedError, match="Perdita giornaliera"):
        run_preview(engine, fake, idea)
    assert fake.posts() == []


def test_pending_order_on_same_ticker_blocks(engine: Engine, ready: tuple[FakeT212, int]) -> None:
    fake, idea = ready
    fake.pending = [{"id": 7, "ticker": "3USLl_EQ", "type": "LIMIT", "quantity": 1}]
    with pytest.raises(svc.OrderBlockedError, match="in attesa"):
        run_preview(engine, fake, idea)


def test_expired_or_closed_idea_blocks(engine: Engine, ready: tuple[FakeT212, int]) -> None:
    fake, idea = ready
    with engine.begin() as conn:
        conn.execute(trade_ideas.update().where(trade_ideas.c.id == idea).values(status="scaduta"))
    with pytest.raises(svc.OrderBlockedError, match="non è più attiva"):
        run_preview(engine, fake, idea)


def test_crypto_is_not_orderable(engine: Engine, ready: tuple[FakeT212, int]) -> None:
    fake, _ = ready
    idea = make_idea(engine, "BTC")
    with pytest.raises(svc.OrderBlockedError, match="non ordinabile"):
        run_preview(engine, fake, idea)


# --- Esiti dell'invio: nessun nuovo tentativo -----------------------------------------


def test_timeout_is_uncertain_and_never_retried(
    engine: Engine, ready: tuple[FakeT212, int]
) -> None:
    fake, idea = ready
    fake.market = "timeout"
    pv = run_preview(engine, fake, idea)
    row = run_place(engine, fake, idea, float(str(pv["quantity"])), str(pv["token"]))
    assert row["status"] == "incerto" and "verifica" in str(row["error"])
    assert len(fake.posts("/market")) == 1 and fake.posts("/stop") == []
    with pytest.raises(svc.OrderBlockedError, match="già inviato"):
        run_preview(engine, fake, idea)


def test_server_error_is_uncertain(engine: Engine, ready: tuple[FakeT212, int]) -> None:
    fake, idea = ready
    fake.market = "errore"
    pv = run_preview(engine, fake, idea)
    row = run_place(engine, fake, idea, float(str(pv["quantity"])), str(pv["token"]))
    assert row["status"] == "incerto"


def test_rejection_is_logged_without_secrets_and_can_be_retried(
    engine: Engine, ready: tuple[FakeT212, int]
) -> None:
    fake, idea = ready
    fake.market = "rifiuta"
    pv = run_preview(engine, fake, idea)
    row = run_place(engine, fake, idea, float(str(pv["quantity"])), str(pv["token"]))
    assert row["status"] == "rifiutato"
    assert "InsufficientFreeForStocksBuy" in str(row["error"])
    dumped = json.dumps(row)
    assert KEY not in dumped and SECRET not in dumped
    fake.market = "ok"
    pv = run_preview(engine, fake, idea)
    assert run_place(engine, fake, idea, 4.0, str(pv["token"]))["status"] == "eseguito"


def test_failed_stop_is_flagged(engine: Engine, ready: tuple[FakeT212, int]) -> None:
    fake, idea = ready
    fake.stop = "rifiuta"
    pv = run_preview(engine, fake, idea)
    row = run_place(engine, fake, idea, float(str(pv["quantity"])), str(pv["token"]))
    assert row["status"] == "eseguito" and row["stop_status"] == "da_impostare"
    assert "Stop NON impostato" in str(row["error"])


# --- API ------------------------------------------------------------------------------


@pytest.fixture
def api(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    def conn() -> Iterator[Connection]:
        with engine.connect() as c:
            yield c

    app.dependency_overrides[deps.get_conn] = conn
    svc.get_order_broker.cache_clear()
    yield TestClient(app)
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_api_orders_and_kill_switch(
    engine: Engine, api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(trading_engine, "correlations", lambda conn, s, others: {})
    monkeypatch.setenv("ORDERS_MODE", "demo")
    monkeypatch.setenv("T212_ORDER_API_KEY", KEY)
    monkeypatch.setenv("T212_ORDER_API_SECRET", SECRET)
    get_settings.cache_clear()
    fake = FakeT212(engine)
    monkeypatch.setattr(svc, "get_order_broker", lambda: fake.client())
    monkeypatch.setattr(svc, "yahoo_quote", quote)
    idea = make_idea(engine)

    state = api.get("/api/orders").json()
    assert state["mode"] == "demo" and state["kill_switch"] is True
    assert api.post("/api/orders/preview", json={"idea_id": idea}).status_code == 409
    assert api.post("/api/controls/kill-switch", json={"active": False}).json() == {
        "kill_switch": False
    }
    pv = api.post("/api/orders/preview", json={"idea_id": idea})
    assert pv.status_code == 200
    body = pv.json()
    # Senza codice di conferma o con codice malformato: rifiuto prima di ogni invio.
    for payload in (
        {"idea_id": idea, "quantity": body["quantity"]},
        {"idea_id": idea, "quantity": body["quantity"], "token": "x" * 20},
        {"idea_id": -1, "quantity": body["quantity"], "token": body["token"]},
    ):
        assert api.post("/api/orders", json=payload).status_code == 422
    assert fake.posts() == []
    placed = api.post(
        "/api/orders",
        json={"idea_id": idea, "quantity": body["quantity"], "token": body["token"]},
    )
    assert placed.status_code == 200 and placed.json()["status"] == "eseguito"
    listing = api.get("/api/orders").json()
    assert listing["limits"]["today"] == 1 and len(listing["orders"]) == 1
    for text in (pv.text, placed.text, json.dumps(listing)):
        assert KEY not in text and SECRET not in text
    assert api.post("/api/controls/kill-switch", json={"active": True}).json() == {
        "kill_switch": True
    }


def test_api_cannot_disable_kill_switch_when_orders_disabled(api: TestClient) -> None:
    get_settings.cache_clear()
    response = api.post("/api/controls/kill-switch", json={"active": False})
    assert response.status_code == 409
