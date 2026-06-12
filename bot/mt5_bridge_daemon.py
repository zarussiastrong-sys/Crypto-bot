"""File-bridge daemon for MetaTrader5 Expert Advisor integration.

EA writes requests to bridge_dir/inbox/*.json.
This daemon reads requests, runs analysis, writes decision to bridge_dir/outbox/*.json.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from config import build_config
from consensus.aggregator import run as agg_run
from data.news_filter import evaluate_news_risk
from advanced.meta_model import predict_meta_signal
from bot.mt5_format import format_mt5_decision

logger = logging.getLogger("temporal_bot.bot.mt5_bridge_daemon")


def parse_direction(plan: dict) -> str:
    raw = " ".join(str(plan.get(k, "")).lower() for k in ("direction", "signal", "bias", "action"))
    if "buy" in raw or "long" in raw:
        return "buy"
    if "sell" in raw or "short" in raw:
        return "sell"
    return "hold"


def build_decision(req: dict, plan: dict, cfg: dict) -> dict:
    action = "hold"
    sl = 0.0
    tp = 0.0

    symbol = req.get("symbol", "")
    news = evaluate_news_risk(str(symbol), cfg, now_utc=datetime.now(timezone.utc))

    if plan.get("success"):
        action = parse_direction(plan)
        sl = float(plan.get("active_stop") or plan.get("stop_loss") or 0.0)
        tp = float(plan.get("take_profit") or 0.0)
    meta = predict_meta_signal({"plan": plan, "cfg": cfg, "news": asdict(news)}) or {}

    volume = float(req.get("volume", 0.01))
    mult = float(meta.get("meta_position_multiplier", 1.0) or 1.0)
    volume = round(max(0.0, volume * mult), 4)

    if news.block_trade:
        action = "hold"
    if bool(meta.get("meta_block_trade", False)):
        action = "hold"

    return {
        "request_id": req.get("request_id", ""),
        "symbol": symbol,
        "action": action,
        "sl": sl,
        "tp": tp,
        "volume": volume,
        "success": bool(plan.get("success")),
        "error": plan.get("error"),
        "news_filter": asdict(news),
        "meta_ai": meta,
        "mt5": format_mt5_decision(
            {
                "request_id": req.get("request_id", ""),
                "symbol": symbol,
                "action": action,
                "volume": volume,
                "sl": sl,
                "tp": tp,
            },
            cfg,
        ),
        "generated_at": int(time.time()),
    }


def process_request(path: Path, outbox: Path, cfg: dict) -> None:
    req = json.loads(path.read_text(encoding="utf-8"))

    symbol = str(req.get("symbol", "XAUUSD")).upper()
    interval = str(req.get("interval", "1m"))
    bars = int(req.get("bars", 512))

    plan = agg_run(symbol, interval, bars, cfg)
    decision = build_decision(req, plan, cfg)

    out_path = outbox / f"{req['request_id']}.json"
    out_path.write_text(json.dumps(decision, ensure_ascii=False), encoding="utf-8")
    path.unlink(missing_ok=True)

    logger.info("Processed request=%s symbol=%s action=%s", req.get("request_id"), symbol, decision["action"])


def run_loop(bridge_dir: Path, poll_sec: float) -> None:
    inbox = bridge_dir / "inbox"
    outbox = bridge_dir / "outbox"
    inbox.mkdir(parents=True, exist_ok=True)
    outbox.mkdir(parents=True, exist_ok=True)

    cfg = build_config()
    cfg["DATA_PROVIDER"] = "mt5"

    logger.info("Bridge daemon started. dir=%s", bridge_dir)
    while True:
        for req_file in sorted(inbox.glob("*.json")):
            try:
                process_request(req_file, outbox, cfg)
            except Exception as exc:
                logger.exception("Failed request file=%s err=%s", req_file.name, exc)
                # keep file for retry
        time.sleep(poll_sec)


def main() -> None:
    parser = argparse.ArgumentParser(description="MT5 Experts <-> Python bridge daemon")
    parser.add_argument(
        "--bridge-dir",
        default="temporal_bot",
        help="Path to bridge folder (absolute) or relative folder name under terminal Common/Files",
    )
    parser.add_argument("--poll-sec", type=float, default=1.0)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")

    bridge_dir = Path(args.bridge_dir)
    if not bridge_dir.is_absolute():
        # For local dev fallback; in production set absolute MT5 Common/Files path.
        bridge_dir = Path.cwd() / bridge_dir

    run_loop(bridge_dir, args.poll_sec)


if __name__ == "__main__":
    main()
