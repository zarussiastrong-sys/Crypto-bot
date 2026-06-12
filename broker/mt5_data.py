"""MT5 market data adapter."""

from __future__ import annotations

import os
import pandas as pd

from broker.mt5_symbols import resolve_symbol

_TIMEFRAME_MAP = {
    "1m": "TIMEFRAME_M1",
    "5m": "TIMEFRAME_M5",
    "15m": "TIMEFRAME_M15",
    "30m": "TIMEFRAME_M30",
    "1h": "TIMEFRAME_H1",
    "4h": "TIMEFRAME_H4",
    "1d": "TIMEFRAME_D1",
}


def _load_mt5_module():
    try:
        import MetaTrader5 as mt5  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "MetaTrader5 package is not installed. Install with: pip install MetaTrader5"
        ) from exc
    return mt5


def _initialize_mt5(mt5) -> None:
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
        raise RuntimeError(f"mt5.initialize() failed: {mt5.last_error()}")


def fetch_ohlcv(symbol: str, interval: str = "1m", bars: int = 512) -> pd.DataFrame:
    """Fetch OHLCV bars from MT5 and return normalized DataFrame."""
    mt5 = _load_mt5_module()

    tf_attr = _TIMEFRAME_MAP.get((interval or "").lower())
    if not tf_attr or not hasattr(mt5, tf_attr):
        raise ValueError(f"Unsupported MT5 interval: {interval}")
    timeframe = getattr(mt5, tf_attr)

    _initialize_mt5(mt5)

    try:
        mt5_symbol = resolve_symbol(mt5, symbol)
        rates = mt5.copy_rates_from_pos(mt5_symbol, timeframe, 0, int(bars))
        if rates is None or len(rates) == 0:
            raise RuntimeError(f"No rates from MT5 for {mt5_symbol} ({interval})")

        df = pd.DataFrame(rates)
        df.rename(
            columns={
                "time": "timestamp",
                "tick_volume": "volume",
                "real_volume": "real_volume",
                "spread": "spread",
            },
            inplace=True,
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
        return df[["timestamp", "open", "high", "low", "close", "volume", "spread"]]
    finally:
        mt5.shutdown()
