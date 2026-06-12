"""MT5 execution adapter with safe defaults for SL/TP and reduce-only closes."""

from __future__ import annotations

import os
from dataclasses import dataclass

from broker.mt5_symbols import resolve_symbol


@dataclass
class OrderResult:
    ok: bool
    retcode: int | None
    comment: str
    order: int | None = None


def _load_mt5_module():
    try:
        import MetaTrader5 as mt5  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "MetaTrader5 package is not installed. Install with: pip install MetaTrader5"
        ) from exc
    return mt5


def _initialize_mt5(mt5) -> tuple[bool, str | None]:
    login = os.getenv("MT5_LOGIN", "").strip()
    password = os.getenv("MT5_PASSWORD", "").strip()
    server = os.getenv("MT5_SERVER", "").strip()

    kwargs = {}
    if login.isdigit():
        kwargs["login"] = int(login)
    if password:
        kwargs["password"] = password
    if server:
        kwargs["server"] = server

    ok = mt5.initialize(**kwargs) if kwargs else mt5.initialize()
    if not ok:
        return False, f"mt5.initialize() failed: {mt5.last_error()}"
    return True, None


def send_market_order(
    side: str,
    symbol: str,
    volume: float,
    sl: float | None = None,
    tp: float | None = None,
    deviation: int = 20,
    magic: int = 900001,
):
    mt5 = _load_mt5_module()
    ok_init, err = _initialize_mt5(mt5)
    if not ok_init:
        return OrderResult(False, None, err or "mt5.initialize() failed")

    try:
        mt5_symbol = resolve_symbol(mt5, symbol)
        tick = mt5.symbol_info_tick(mt5_symbol)
        if tick is None:
            return OrderResult(False, None, f"No tick for {mt5_symbol}")

        side_norm = (side or "").lower()
        if side_norm not in {"buy", "sell"}:
            return OrderResult(False, None, f"Unsupported side: {side}")

        is_buy = side_norm == "buy"
        order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
        price = float(tick.ask if is_buy else tick.bid)

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": mt5_symbol,
            "volume": float(volume),
            "type": order_type,
            "price": price,
            "deviation": int(deviation),
            "magic": int(magic),
            "comment": "temporal_bot_mt5",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        if sl is not None:
            request["sl"] = float(sl)
        if tp is not None:
            request["tp"] = float(tp)

        result = mt5.order_send(request)
        if result is None:
            return OrderResult(False, None, f"order_send returned None: {mt5.last_error()}")

        ok = result.retcode == mt5.TRADE_RETCODE_DONE
        return OrderResult(ok, int(result.retcode), str(result.comment), int(getattr(result, "order", 0) or 0))
    finally:
        mt5.shutdown()


def close_position(ticket: int, deviation: int = 20):
    """Close existing MT5 position by ticket using opposite side market order."""
    mt5 = _load_mt5_module()
    ok_init, err = _initialize_mt5(mt5)
    if not ok_init:
        return OrderResult(False, None, err or "mt5.initialize() failed")

    try:
        positions = mt5.positions_get(ticket=int(ticket))
        if not positions:
            return OrderResult(False, None, f"Position not found: {ticket}")
        pos = positions[0]

        symbol = pos.symbol
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return OrderResult(False, None, f"No tick for {symbol}")

        is_buy_pos = int(pos.type) == int(mt5.POSITION_TYPE_BUY)
        close_type = mt5.ORDER_TYPE_SELL if is_buy_pos else mt5.ORDER_TYPE_BUY
        close_price = float(tick.bid if is_buy_pos else tick.ask)

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": int(pos.ticket),
            "symbol": symbol,
            "volume": float(pos.volume),
            "type": close_type,
            "price": close_price,
            "deviation": int(deviation),
            "magic": int(getattr(pos, "magic", 900001)),
            "comment": "temporal_bot_close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is None:
            return OrderResult(False, None, f"order_send returned None: {mt5.last_error()}")

        ok = result.retcode == mt5.TRADE_RETCODE_DONE
        return OrderResult(ok, int(result.retcode), str(result.comment), int(getattr(result, "order", 0) or 0))
    finally:
        mt5.shutdown()
