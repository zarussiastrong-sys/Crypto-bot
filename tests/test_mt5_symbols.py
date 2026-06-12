from broker.mt5_symbols import build_symbol_candidates, resolve_symbol


class _Info:
    def __init__(self, visible=True):
        self.visible = visible


class _FakeMt5:
    def __init__(self):
        self.selected = []

    def symbol_info(self, symbol):
        if symbol == "XAUUSDm":
            return _Info(visible=False)
        return None

    def symbol_select(self, symbol, flag):
        self.selected.append((symbol, flag))
        return True


def test_build_symbol_candidates_contains_aliases():
    cands = build_symbol_candidates("XAUUSD")
    assert "XAUUSD" in cands
    assert "XAUUSDm" in cands
    assert "GOLD" in cands


def test_resolve_symbol_selects_first_available_and_makes_visible():
    mt5 = _FakeMt5()
    symbol = resolve_symbol(mt5, "XAUUSD")
    assert symbol == "XAUUSDm"
    assert mt5.selected == [("XAUUSDm", True)]
