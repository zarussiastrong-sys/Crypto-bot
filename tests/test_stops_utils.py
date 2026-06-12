import numpy as np

from risk.stops_utils import (
    compute_atr,
    initial_stop,
    trailing_stop,
    stop_schedule,
)


def test_compute_atr_reasonable_value():
    close = np.linspace(100.0, 120.0, 30)
    high = close + 2.0
    low = close - 2.0
    atr = compute_atr(high, low, close, period=14)
    assert atr > 0
    assert atr < 10  # with such mild moves, ATR should be modest


def test_initial_stop_with_murray_levels_long():
    entry = 100.0
    atr = 2.0
    mult = 2.0
    levels = np.array([80.0, 90.0, 95.0, 99.0])
    res = initial_stop(entry, atr, mult, levels, direction="long")
    assert res["stop_price"] < entry
    assert res["stop_type"] == "initial"


def test_trailing_stop_moves_with_price():
    prices = np.array([100.0, 105.0, 110.0, 115.0, 120.0])
    entry = 100.0
    atr = 2.0
    phase = 200.0
    levels = np.array([])
    res = trailing_stop(prices, entry, atr, phase, direction="long", levels=levels)
    assert res["stop_price"] < prices.max()
    assert res["stop_type"] == "trailing"


def test_stop_schedule_generates_future_points():
    sched = stop_schedule(phase=100.0, entry=100.0, atr=2.0, direction="long")
    assert sched
    for item in sched:
        assert item["bars_ahead"] > 0
        assert isinstance(item["projected_stop"], float)


def test_trailing_stop_locks_break_even_after_profit():
    prices = np.array([100.0, 101.0, 102.0, 103.0, 104.0])
    res = trailing_stop(
        prices=prices,
        entry=100.0,
        atr=2.0,
        phase=220.0,
        direction="long",
        levels=np.array([]),
        cfg={"TRAIL_BREAK_EVEN_R": 0.5, "TRAIL_BREAK_EVEN_BUFFER_ATR": 0.1},
    )
    # Once PnL > 0.5 ATR, stop should be above entry (break-even protection).
    assert res["stop_price"] >= 100.2


def test_trailing_stop_uses_step_ratchet():
    prices = np.array([100.0, 102.0, 104.0, 106.0, 108.0])
    res = trailing_stop(
        prices=prices,
        entry=100.0,
        atr=2.0,
        phase=359.0,  # tiny trail distance, so step ratchet dominates
        direction="long",
        levels=np.array([]),
        cfg={"TRAIL_STEP_R": 0.25, "TRAIL_STEP_LOCK_R": 0.15},
    )
    # profit = 8.0 => 16 steps of 0.25R, lock should be at least +4.8 over entry.
    assert res["stop_price"] >= 104.8
