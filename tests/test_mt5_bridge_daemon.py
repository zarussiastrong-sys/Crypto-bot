from bot.mt5_bridge_daemon import parse_direction, build_decision


def test_parse_direction_buy_sell_hold():
    assert parse_direction({"direction": "LONG"}) == "buy"
    assert parse_direction({"signal": "strong_sell"}) == "sell"
    assert parse_direction({"signal": "neutral"}) == "hold"


def test_build_decision_uses_stops_and_volume():
    req = {"request_id": "abc", "symbol": "XAUUSD", "volume": 0.02}
    plan = {
        "success": True,
        "direction": "buy",
        "active_stop": 3210.5,
        "take_profit": 3260.0,
        "consensus_confidence": 0.9,
        "overall_risk_score": 0.3,
    }
    cfg = {"NEWS_FILTER_ENABLED": False, "AI_MIN_CONFIDENCE": 0.5}

    out = build_decision(req, plan, cfg)
    assert out["action"] == "buy"
    assert out["sl"] == 3210.5
    assert out["tp"] == 3260.0
    assert out["volume"] > 0
    assert "news_filter" in out
    assert "meta_ai" in out
    assert out["mt5"]["order_type"] == "ORDER_TYPE_BUY"
