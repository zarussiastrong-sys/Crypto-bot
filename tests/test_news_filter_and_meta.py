from datetime import datetime, timezone
import json

from data.news_filter import evaluate_news_risk
from advanced.meta_model import predict_meta_signal


def test_news_filter_blocks_high_impact_within_window(tmp_path):
    events = {
        "events": [
            {
                "time": "2026-01-10T12:30:00Z",
                "currency": "USD",
                "impact": "high",
                "title": "NFP",
            }
        ]
    }
    p = tmp_path / "events.json"
    p.write_text(json.dumps(events), encoding="utf-8")

    cfg = {
        "NEWS_FILTER_ENABLED": True,
        "NEWS_EVENTS_FILE": str(p),
        "NEWS_BLOCK_BEFORE_MIN": 30,
        "NEWS_BLOCK_AFTER_MIN": 30,
        "HIGH_IMPACT_CURRENCIES": ["USD"],
    }
    now = datetime(2026, 1, 10, 12, 20, tzinfo=timezone.utc)
    r = evaluate_news_risk("XAUUSD", cfg, now_utc=now)
    assert r.block_trade is True


def test_meta_model_blocks_on_low_confidence_or_high_risk():
    features = {
        "plan": {"consensus_confidence": 0.2, "overall_risk_score": 0.9, "gamma_regime": "negative"},
        "cfg": {"AI_MIN_CONFIDENCE": 0.5, "AI_MAX_RISK_SCORE": 0.7},
        "news": {"block_trade": False},
    }
    out = predict_meta_signal(features)
    assert out["meta_block_trade"] is True
    assert out["meta_position_multiplier"] <= 1.0
