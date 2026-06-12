"""MT5-friendly payload formatting helpers for bridge responses."""

from __future__ import annotations

from datetime import datetime, timezone


def format_mt5_decision(decision: dict, cfg: dict | None = None) -> dict:
    cfg = cfg or {}
    action = str(decision.get("action", "hold")).lower()

    order_type = {
        "buy": "ORDER_TYPE_BUY",
        "sell": "ORDER_TYPE_SELL",
        "close": "POSITION_CLOSE",
    }.get(action, "NO_ACTION")

    return {
        "request_id": decision.get("request_id", ""),
        "symbol": decision.get("symbol", ""),
        "order_type": order_type,
        "action": action,
        "lot": float(decision.get("volume", 0.0) or 0.0),
        "sl": float(decision.get("sl", 0.0) or 0.0),
        "tp": float(decision.get("tp", 0.0) or 0.0),
        "deviation": int(cfg.get("MT5_DEVIATION", 20)),
        "magic": int(cfg.get("MT5_MAGIC", 900001)),
        "comment": str(cfg.get("MT5_COMMENT", "temporal_bridge")),
        "time_in_force": "GTC",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
