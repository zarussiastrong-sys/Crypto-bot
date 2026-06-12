"""Utilities for mapping generic symbols to broker-specific MT5 symbols."""

from __future__ import annotations


def build_symbol_candidates(symbol: str) -> list[str]:
    """
    Build likely MT5 symbol candidates for common FX/metals/energy names.

    Example:
        EURUSD -> ["EURUSD", "EURUSDm", "EURUSD.r", "EURUSD.pro", ...]
    """
    base = (symbol or "").strip().upper()
    if not base:
        return []

    suffixes = ["", "m", ".m", ".r", ".pro", "_i", "-pro", "#"]
    out: list[str] = []
    for suf in suffixes:
        val = f"{base}{suf}"
        if val not in out:
            out.append(val)

    alias = {
        "XAUUSD": ["GOLD", "XAUUSDm", "XAUUSD."],
        "XAGUSD": ["SILVER"],
        "USOIL": ["WTI", "WTIUSD", "XTIUSD"],
        "UKOIL": ["BRENT", "XBRUSD"],
    }
    for a in alias.get(base, []):
        if a not in out:
            out.append(a)
    return out


def resolve_symbol(mt5, requested_symbol: str) -> str:
    """Return an available MT5 symbol name for requested symbol, else raise ValueError."""
    candidates = build_symbol_candidates(requested_symbol)
    if not candidates:
        raise ValueError("Symbol is empty")

    for symbol in candidates:
        info = mt5.symbol_info(symbol)
        if info is not None:
            if not info.visible:
                mt5.symbol_select(symbol, True)
            return symbol

    raise ValueError(
        f"No matching MT5 symbol for '{requested_symbol}'. Tried: {', '.join(candidates)}"
    )
