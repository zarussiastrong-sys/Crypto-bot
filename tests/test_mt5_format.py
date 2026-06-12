from bot.mt5_format import format_mt5_decision


def test_format_mt5_decision_buy_mapping():
    decision = {"request_id": "r1", "symbol": "XAUUSD", "action": "buy", "volume": 0.03, "sl": 3200, "tp": 3260}
    cfg = {"MT5_DEVIATION": 25, "MT5_MAGIC": 42, "MT5_COMMENT": "bridge"}
    out = format_mt5_decision(decision, cfg)
    assert out["order_type"] == "ORDER_TYPE_BUY"
    assert out["lot"] == 0.03
    assert out["magic"] == 42
    assert out["deviation"] == 25


def test_format_mt5_decision_hold_mapping():
    out = format_mt5_decision({"action": "hold"}, {})
    assert out["order_type"] == "NO_ACTION"
