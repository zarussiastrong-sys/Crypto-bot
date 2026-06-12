"""High-impact news filter for trade gating.

Reads an optional events JSON file and blocks trading around strong news windows.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


@dataclass
class NewsFilterResult:
    block_trade: bool
    reason: str
    matched_event: dict[str, Any] | None


def _parse_symbol_currencies(symbol: str) -> set[str]:
    s = (symbol or "").upper()
    out: set[str] = set()
    if len(s) >= 6:
        out.add(s[:3])
        out.add(s[3:6])
    if "XAU" in s or "GOLD" in s:
        out.add("USD")
    if "USOIL" in s or "UKOIL" in s or "WTI" in s or "BRENT" in s:
        out.add("USD")
    return out


def _parse_iso_utc(ts: str) -> datetime | None:
    try:
        t = ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(t)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def evaluate_news_risk(symbol: str, cfg: dict, now_utc: datetime | None = None) -> NewsFilterResult:
    enabled = bool(cfg.get("NEWS_FILTER_ENABLED", True))
    if not enabled:
        return NewsFilterResult(False, "news_filter_disabled", None)

    now = now_utc or datetime.now(timezone.utc)
    events_path = Path(str(cfg.get("NEWS_EVENTS_FILE", "news_events.json")))
    if not events_path.exists():
        return NewsFilterResult(False, "news_events_file_missing", None)

    before_min = int(cfg.get("NEWS_BLOCK_BEFORE_MIN", 30))
    after_min = int(cfg.get("NEWS_BLOCK_AFTER_MIN", 30))
    wanted = set(str(x).upper() for x in cfg.get("HIGH_IMPACT_CURRENCIES", ["USD", "EUR", "GBP", "JPY"]))
    symbol_ccy = _parse_symbol_currencies(symbol)

    try:
        payload = json.loads(events_path.read_text(encoding="utf-8"))
    except Exception:
        return NewsFilterResult(False, "news_events_file_unreadable", None)

    events = payload if isinstance(payload, list) else payload.get("events", [])
    for ev in events:
        if not isinstance(ev, dict):
            continue
        impact = str(ev.get("impact", "")).lower()
        if impact not in {"high", "strong", "red"}:
            continue
        ccy = str(ev.get("currency", "")).upper()
        if ccy and ccy not in wanted:
            continue
        if ccy and ccy not in symbol_ccy:
            continue

        t = _parse_iso_utc(str(ev.get("time", "")))
        if t is None:
            continue
        if t - timedelta(minutes=before_min) <= now <= t + timedelta(minutes=after_min):
            return NewsFilterResult(True, f"high_impact_news:{ccy or 'UNK'}", ev)

    return NewsFilterResult(False, "no_high_impact_news_window", None)
