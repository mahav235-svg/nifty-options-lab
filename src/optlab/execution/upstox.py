"""Upstox API client implementing :class:`optlab.execution.broker.Broker`.

Endpoints (Upstox developer docs, checked Oct 2026):

* login dialog      GET  https://api.upstox.com/v2/login/authorization/dialog
* token exchange    POST https://api.upstox.com/v2/login/authorization/token
* instruments       GET  https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz  (public)
* option chain      GET  https://api.upstox.com/v2/option/chain
* full quotes       GET  https://api.upstox.com/v2/market-quote/quotes
* place order       POST https://api-hft.upstox.com/v3/order/place
* modify / cancel   PUT  https://api-hft.upstox.com/v3/order/modify, DELETE .../v3/order/cancel
* order details     GET  https://api.upstox.com/v2/order/details
* positions         GET  https://api.upstox.com/v2/portfolio/short-term-positions
* funds             GET  https://api.upstox.com/v2/user/get-funds-and-margin

Rules this client follows because the exchange or SEBI requires them:

* Orders go out as LIMIT only. Market orders over the API are blocked (UDAPI1158) and are a bad
  idea in options anyway.
* Since 1 April 2026 every order must come from the static IP registered in the Upstox developer
  console (error UDAPI1154 otherwise). Run the live job from that machine.
* The access token expires daily (about 03:30 IST). ``optlab live login`` prints the login URL;
  you sign in yourself and paste the returned code. The token is kept in a local file outside
  the repository and is never logged.
* Retail algos are capped at 10 orders per second unless registered with the exchange; this
  client throttles itself well below that.
"""

from __future__ import annotations

import contextlib
import gzip
import json
import logging
import os
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

from optlab.execution.broker import (
    OptionContract,
    OrderRequest,
    OrderStatus,
    OrderUpdate,
    Position,
    Quote,
    Side,
)

log = logging.getLogger(__name__)

API = "https://api.upstox.com"
HFT = "https://api-hft.upstox.com"
INSTRUMENTS_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
UNDERLYING_KEYS = {"NIFTY": "NSE_INDEX|Nifty 50", "BANKNIFTY": "NSE_INDEX|Nifty Bank"}
TOKEN_FILE = Path(os.environ.get("OPTLAB_TOKEN_FILE", Path.home() / ".optlab" / "upstox_token.json"))

_STATUS = {
    "complete": OrderStatus.COMPLETE,
    "rejected": OrderStatus.REJECTED,
    "cancelled": OrderStatus.CANCELLED,
    "open": OrderStatus.OPEN,
    "trigger pending": OrderStatus.OPEN,
    "put order req received": OrderStatus.OPEN,
    "validation pending": OrderStatus.OPEN,
    "open pending": OrderStatus.OPEN,
    "modify pending": OrderStatus.OPEN,
}


class UpstoxError(RuntimeError):
    pass


def login_url(client_id: str, redirect_uri: str) -> str:
    q = urlencode({"response_type": "code", "client_id": client_id, "redirect_uri": redirect_uri})
    return f"{API}/v2/login/authorization/dialog?{q}"


def exchange_code(
    code: str, client_id: str, client_secret: str, redirect_uri: str, token_file: Path = TOKEN_FILE
) -> None:
    resp = requests.post(
        f"{API}/v2/login/authorization/token",
        timeout=30,
        headers={"Accept": "application/json"},
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    if resp.status_code != 200:
        raise UpstoxError(f"token exchange failed: HTTP {resp.status_code}")
    token = resp.json()["access_token"]
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(
        json.dumps({"access_token": token, "saved_at": datetime.now().isoformat()}), encoding="utf-8"
    )
    with contextlib.suppress(OSError):  # not supported on every filesystem (e.g. Windows ACLs)
        token_file.chmod(0o600)


def load_token(token_file: Path = TOKEN_FILE) -> str:
    env = os.environ.get("UPSTOX_ACCESS_TOKEN")
    if env:
        return env
    if not token_file.exists():
        raise UpstoxError("no access token; run `optlab live login` first")
    return str(json.loads(token_file.read_text(encoding="utf-8"))["access_token"])


def _tick(raw: Any) -> float:
    """The instrument file gives tick size in paise for F&O (5.0 means Rs 0.05)."""
    t = float(raw) if raw is not None else 0.05
    return t / 100.0 if t >= 1 else t


class UpstoxBroker:
    name = "upstox"

    def __init__(
        self,
        token: str | None = None,
        session: requests.Session | None = None,
        min_interval: float = 0.25,
        algo_name: str | None = None,
    ) -> None:
        self._s = session or requests.Session()
        self._s.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token or load_token()}",
            }
        )
        if algo_name:
            self._s.headers["X-Algo-Name"] = algo_name
        self._min_interval = min_interval
        self._last = 0.0
        self._instruments: list[dict[str, Any]] | None = None

    # -- transport ------------------------------------------------------------------------------

    def _call(self, method: str, url: str, **kw: Any) -> Any:
        wait = self._min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        resp = self._s.request(method, url, timeout=20, **kw)
        try:
            body = resp.json()
        except ValueError as exc:
            raise UpstoxError(f"{method} {url}: HTTP {resp.status_code}, non-JSON body") from exc
        if resp.status_code >= 400 or body.get("status") == "error":
            errors = body.get("errors") or [{}]
            code = errors[0].get("errorCode") or errors[0].get("error_code")
            msg = errors[0].get("message", "")
            raise UpstoxError(f"{method} {url}: HTTP {resp.status_code} {code} {msg}")
        return body.get("data")

    # -- reference data -------------------------------------------------------------------------

    def _instrument_master(self) -> list[dict[str, Any]]:
        if self._instruments is None:
            raw = requests.get(INSTRUMENTS_URL, timeout=60).content
            self._instruments = json.loads(gzip.decompress(raw))
        return self._instruments

    def option_contracts(self, underlying: str, expiry: date) -> list[OptionContract]:
        out = []
        for r in self._instrument_master():
            if r.get("segment") != "NSE_FO" or r.get("instrument_type") not in ("CE", "PE"):
                continue
            if r.get("underlying_symbol") != underlying:
                continue
            exp = datetime.fromtimestamp(int(r["expiry"]) / 1000).date()
            if exp != expiry:
                continue
            out.append(
                OptionContract(
                    instrument_key=r["instrument_key"],
                    symbol=r.get("trading_symbol", ""),
                    underlying=underlying,
                    expiry=exp,
                    strike=float(r["strike_price"]),
                    option_type=r["instrument_type"],
                    lot_size=int(r["lot_size"]),
                    tick_size=_tick(r.get("tick_size")),
                    freeze_qty=int(r["freeze_quantity"]) if r.get("freeze_quantity") else None,
                )
            )
        return sorted(out, key=lambda c: (c.strike, c.option_type))

    def expiries(self, underlying: str) -> list[date]:
        exps = {
            datetime.fromtimestamp(int(r["expiry"]) / 1000).date()
            for r in self._instrument_master()
            if r.get("segment") == "NSE_FO"
            and r.get("underlying_symbol") == underlying
            and r.get("instrument_type") in ("CE", "PE")
        }
        return sorted(exps)

    def holidays(self) -> list[date]:
        """Weekday NSE closures from Upstox's market-holidays endpoint (best effort)."""
        data = self._call("GET", f"{API}/v2/market/holidays") or []
        out = []
        for h in data:
            closed = h.get("closed_exchanges") or []
            if "NSE" in closed or "NFO" in closed:
                out.append(date.fromisoformat(str(h["date"])[:10]))
        return out

    # -- market data ----------------------------------------------------------------------------

    def quotes(self, keys: list[str]) -> dict[str, Quote]:
        out: dict[str, Quote] = {}
        for i in range(0, len(keys), 450):  # the endpoint accepts up to 500 keys per call
            batch = keys[i : i + 450]
            data = self._call(
                "GET", f"{API}/v2/market-quote/quotes", params={"instrument_key": ",".join(batch)}
            )
            for item in (data or {}).values():
                depth = item.get("depth") or {}
                bid = (depth.get("buy") or [{}])[0].get("price", 0.0) or 0.0
                ask = (depth.get("sell") or [{}])[0].get("price", 0.0) or 0.0
                key = item.get("instrument_token") or item.get("instrument_key")
                out[key] = Quote(
                    instrument_key=key,
                    bid=float(bid),
                    ask=float(ask),
                    ltp=float(item.get("last_price", 0)),
                    volume=float(item.get("volume", 0)),
                    oi=float(item.get("oi", 0)),
                )
        return out

    def spot(self, underlying: str) -> float:
        key = UNDERLYING_KEYS[underlying]
        data = self._call("GET", f"{API}/v2/market-quote/quotes", params={"instrument_key": key})
        return float(next(iter(data.values()))["last_price"])

    # -- orders ---------------------------------------------------------------------------------

    def place(self, req: OrderRequest) -> str:
        c = req.contract
        if req.quantity % c.lot_size:
            raise ValueError(f"quantity {req.quantity} is not a multiple of lot size {c.lot_size}")
        body = {
            "quantity": req.quantity,
            "product": "D",
            "validity": "DAY",
            "price": round(req.limit_price, 2),
            "tag": req.tag[:40],
            "instrument_token": c.instrument_key,
            "order_type": "LIMIT",
            "transaction_type": req.side.value,
            "disclosed_quantity": 0,
            "trigger_price": 0,
            "is_amo": False,
            "slice": True,
        }
        data = self._call("POST", f"{HFT}/v3/order/place", data=json.dumps(body))
        ids = data.get("order_ids") or [data.get("order_id")]
        log.info("placed %s %d %s @ %.2f -> %s", req.side, req.quantity, c.symbol, req.limit_price, ids)
        return str(ids[0])

    def modify(self, order_id: str, limit_price: float) -> None:
        self._call(
            "PUT",
            f"{HFT}/v3/order/modify",
            data=json.dumps(
                {
                    "order_id": order_id,
                    "order_type": "LIMIT",
                    "price": round(limit_price, 2),
                    "validity": "DAY",
                    "trigger_price": 0,
                    "disclosed_quantity": 0,
                }
            ),
        )

    def cancel(self, order_id: str) -> None:
        self._call("DELETE", f"{HFT}/v3/order/cancel", params={"order_id": order_id})

    def status(self, order_id: str) -> OrderUpdate:
        d = self._call("GET", f"{API}/v2/order/details", params={"order_id": order_id})
        st = _STATUS.get(str(d.get("status", "")).lower(), OrderStatus.OPEN)
        filled = int(d.get("filled_quantity", 0))
        if st is OrderStatus.OPEN and filled > 0:
            st = OrderStatus.PARTIAL
        return OrderUpdate(
            order_id=order_id,
            status=st,
            filled_qty=filled,
            avg_price=float(d.get("average_price") or 0),
            message=str(d.get("status_message") or ""),
        )

    def positions(self) -> list[Position]:
        data = self._call("GET", f"{API}/v2/portfolio/short-term-positions") or []
        return [
            Position(p["instrument_token"], int(p["quantity"]), float(p.get("average_price") or 0))
            for p in data
            if int(p.get("quantity", 0)) != 0
        ]

    def available_margin(self) -> float:
        d = self._call("GET", f"{API}/v2/user/get-funds-and-margin", params={"segment": "SEC"})
        return float((d.get("equity") or d).get("available_margin", 0.0))


__all__ = ["Side", "UpstoxBroker", "UpstoxError", "exchange_code", "load_token", "login_url"]
