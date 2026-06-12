from __future__ import annotations

"""
advanced/meta_model.py — Optional ML Meta-Model Hook

This module provides a thin, optional abstraction layer for applying a
data-driven meta-model on top of the deterministic engine outputs. The
goal is to let you experiment with Logistic Regression / Gradient Boosting
or other classifiers/regressors trained on historical CSV exports without
changing the rest of the codebase.

By default, predict_meta_signal() is a no-op that simply returns an empty
dict. The advanced consensus / aggregator can call it and merge any
returned fields into the trade plan safely.
"""

from typing import Dict, Any


def predict_meta_signal(features: Dict[str, Any]) -> Dict[str, Any]:
    """
    Optionally adjust bias / confidence / sizing based on a trained model.

    Parameters
    ----------
    features : dict
        A flattened feature dict built from engine_results, risk_results,
        and regime / cycle diagnostics. Intended to be stable over time
        so that offline training code can depend on the same schema.

    Returns
    -------
    dict
        A dict of optional adjustments, for example:
          {
              \"meta_bias\": \"bullish\",
              \"meta_bias_confidence\": 0.78,
              \"meta_position_multiplier\": 0.6,
          }
        The caller is responsible for interpreting and applying these.

    Default behaviour
    -----------------
    This stub returns an empty dict so that importing and calling it
    has no effect until you plug in a real implementation.
    """
    plan = features.get("plan", {}) or {}
    cfg = features.get("cfg", {}) or {}
    news = features.get("news", {}) or {}

    # Conservative defaults
    min_conf = float(cfg.get("AI_MIN_CONFIDENCE", 0.52))
    max_risk = float(cfg.get("AI_MAX_RISK_SCORE", 0.72))
    base_mult = float(cfg.get("AI_BASE_POSITION_MULT", 0.85))
    floor_mult = float(cfg.get("AI_MIN_POSITION_MULT", 0.20))

    conf = float(plan.get("consensus_confidence", 0.0) or 0.0)
    risk = float(plan.get("overall_risk_score", 0.5) or 0.5)
    gamma_regime = str(plan.get("gamma_regime", "")).lower()

    reasons: list[str] = []
    block_trade = False

    if conf < min_conf:
        block_trade = True
        reasons.append(f"low_confidence<{min_conf:.2f}")

    if risk > max_risk:
        block_trade = True
        reasons.append(f"risk_score>{max_risk:.2f}")

    if news.get("block_trade"):
        block_trade = True
        reasons.append(str(news.get("reason", "news_block")))

    # Position multiplier shrinks with higher risk and in negative gamma
    gamma_penalty = 0.10 if "negative" in gamma_regime else 0.0
    mult = base_mult - 0.6 * max(0.0, risk - 0.5) - gamma_penalty
    mult = max(floor_mult, min(1.0, mult))

    return {
        "meta_block_trade": bool(block_trade),
        "meta_position_multiplier": round(mult, 4),
        "meta_reason": ", ".join(reasons) if reasons else "meta_ok",
    }
