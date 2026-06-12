"""Simple MT5 runner: fetch data, run consensus, optionally place order."""

from __future__ import annotations

import argparse
import logging

from broker.mt5_exec import send_market_order

logger = logging.getLogger("temporal_bot.bot.mt5_runner")


def _parse_direction(plan: dict) -> str | None:
    for key in ("direction", "signal", "bias", "action"):
        raw = str(plan.get(key, "")).lower()
        if "buy" in raw or "long" in raw:
            return "buy"
        if "sell" in raw or "short" in raw:
            return "sell"
    return None


def run_once(symbol: str, interval: str, bars: int, volume: float, dry_run: bool = True) -> dict:
    from config import build_config
    from consensus.aggregator import run as agg_run

    cfg = build_config()
    cfg["DATA_PROVIDER"] = "mt5"
    plan = agg_run(symbol, interval, bars, cfg)

    if not plan.get("success"):
        return {"success": False, "error": plan.get("error", "analysis failed"), "plan": plan}

    side = _parse_direction(plan)
    if not side:
        return {"success": True, "trade": None, "plan": plan, "note": "No clear direction in plan"}

    if dry_run:
        return {
            "success": True,
            "trade": {"dry_run": True, "side": side, "symbol": symbol, "volume": volume},
            "plan": plan,
        }

    trade = send_market_order(side=side, symbol=symbol, volume=volume)
    return {"success": bool(trade.ok), "trade": trade.__dict__, "plan": plan}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MT5 analysis + optional execution")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--interval", default="1m")
    parser.add_argument("--bars", type=int, default=512)
    parser.add_argument("--volume", type=float, default=0.01)
    parser.add_argument("--live", action="store_true", help="Send real order (default is dry-run)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
    out = run_once(args.symbol, args.interval, args.bars, args.volume, dry_run=not args.live)
    if out.get("success"):
        logger.info("MT5 runner success: %s", out.get("trade"))
    else:
        logger.error("MT5 runner failed: %s", out.get("error"))


if __name__ == "__main__":
    main()
