"""
Unit tests for core/core_ai.py and core/ai_client.py
"""
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np

from strategies.base import Signal


def _make_signal(name="RSI", signal="BUY", strength=0.8, reason="oversold"):
    return Signal(name=name, signal=signal, strength=strength, reason=reason)


def _make_df(n=30):
    rng = np.random.default_rng(42)
    closes = 100 + rng.standard_normal(n).cumsum()
    return pd.DataFrame({
        "close": closes,
        "high": closes + rng.uniform(0.5, 2.0, n),
        "low": closes - rng.uniform(0.5, 2.0, n),
        "volume": rng.uniform(1000, 5000, n),
    })


class TestProviders:
    def test_get_provider_status(self):
        from core.providers import get_provider_status
        status = get_provider_status()
        assert isinstance(status, dict)

    def test_health_check(self):
        from core.providers import health_check
        health = health_check()
        assert isinstance(health, dict)
        assert "status" in health


class TestAIClient:
    def test_call_ai_failover(self):
        from core.ai_client import call_ai
        with patch("core.ai_client._request_with_retry") as mock_request:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": "ENTER"}}]
            }
            mock_request.side_effect = [None, mock_resp]

            with patch("core.ai_client.PROVIDERS", [
                {"name": "P1", "keys": ["K1"], "models": ["M1"], "base_url": "url1"},
                {"name": "P2", "keys": ["K2"], "models": ["M2"], "base_url": "url2"},
            ]), patch("core.ai_client._p_healthy", {"P1": True, "P2": True}), \
                patch("core.ai_client._p_key_idx", {"P1": 0, "P2": 0}), \
                patch("core.ai_client._p_rpm_calls", {"P1": [], "P2": []}), \
                patch("core.ai_client._p_rpd_calls", {"P1": 0, "P2": 0}), \
                patch("core.ai_client._p_fails", {"P1": 0, "P2": 0}), \
                patch("core.ai_client._p_last_fail", {"P1": 0.0, "P2": 0.0}):
                res = call_ai("system", "user")
                assert res == "ENTER"


class TestCoreAI:
    def test_analyze_coin_pure_insufficient_data(self):
        from core.core_ai import analyze_coin_pure
        df = pd.DataFrame()
        res = analyze_coin_pure("BTCUSDT", 45000.0, df)
        assert res["decision"] == "SKIP"
        assert "بيانات غير كافية" in res["reason"]

    def test_analyze_coin_pure_insufficient_data_none(self):
        from core.core_ai import analyze_coin_pure
        res = analyze_coin_pure("ETHUSDT", 3000.0, None)
        assert res["decision"] == "SKIP"
        assert res["confidence"] == 0

    def test_analyze_coin_with_signals(self):
        from core.core_ai import analyze_coin
        signals = [
            _make_signal("RSI", "BUY", 0.8, "oversold bounce"),
            _make_signal("MACD", "BUY", 0.7, "bullish cross"),
            _make_signal("SMC", "SELL", 0.6, "break of structure"),
        ]
        regime = {"regime": "BULL", "entry_filter": "AGGRESSIVE"}
        ai_response = '{"decision":"ENTER","direction":"BUY","confidence":72,"entry":100.5,"stop_loss":97.0,"targets":[103,106,110],"risk_level":"MEDIUM","reason":"strong momentum","schools_agreeing":2,"key_signal":"RSI"}'

        with patch("core.core_ai._call_ai", return_value=ai_response):
            res = analyze_coin("BTCUSDT", 100.0, signals, regime)
        assert res["decision"] == "ENTER"
        assert res["direction"] == "BUY"
        assert res["confidence"] == 72
        assert len(res["targets"]) == 3

    def test_analyze_coin_fallback_when_ai_unavailable(self):
        from core.core_ai import analyze_coin
        signals = [_make_signal("RSI", "BUY", 0.8, "oversold")]
        regime = {"regime": "BULL", "entry_filter": "NORMAL"}

        with patch("core.core_ai._call_ai", return_value=None):
            res = analyze_coin("BTCUSDT", 100.0, signals, regime)
        assert res["decision"] in ("ENTER", "SKIP")
        assert "reason" in res

    def test_analyze_coin_pure_with_sufficient_data(self):
        from core.core_ai import analyze_coin_pure
        df = _make_df(50)
        ai_response = """القرار: ENTER
الاتجاه: BUY
الثقة: 68
وقف الخسارة: 95.0
الأهداف: 105, 110, 115
المدة: 8
السبب: صعود قوي مع تأكيد الحجم"""

        with patch("core.core_ai._call_ai", return_value=ai_response):
            res = analyze_coin_pure("ETHUSDT", 100.0, df, regime_data={"regime": "BULL"})
        assert res["decision"] == "ENTER"
        assert res["direction"] == "BUY"

    def test_analyze_coin_pure_fallback_when_ai_unavailable(self):
        from core.core_ai import analyze_coin_pure
        df = _make_df(50)

        with patch("core.core_ai._call_ai", return_value=None):
            res = analyze_coin_pure("ETHUSDT", 100.0, df)
        assert res["decision"] == "SKIP"
        assert "AI غير متاح" in res["reason"]


class TestCompareOpportunities:
    def test_compare_empty_candidates(self):
        from core.core_ai import compare_opportunities
        res = compare_opportunities([])
        assert res["recommendations"] == []
        assert "لا توجد" in res["summary"]

    def test_compare_single_candidate(self):
        from core.core_ai import compare_opportunities
        candidates = [{"symbol": "BTCUSDT", "price": 45000.0, "direction": "BUY", "confidence": 80}]
        res = compare_opportunities(candidates)
        assert len(res["recommendations"]) == 1
        assert res["best_pick"] == "BTCUSDT"

    def test_compare_multiple_candidates(self):
        from core.core_ai import compare_opportunities
        candidates = [
            {"symbol": "BTCUSDT", "price": 45000.0, "direction": "BUY", "confidence": 80},
            {"symbol": "ETHUSDT", "price": 3000.0, "direction": "BUY", "confidence": 70},
            {"symbol": "SOLUSDT", "price": 150.0, "direction": "SELL", "confidence": 60},
        ]
        ai_response = "1. BTCUSDT | ENTER 2. ETHUSDT | WAIT"

        with patch("core.core_ai._call_ai", return_value=ai_response):
            res = compare_opportunities(candidates, max_recommendations=2)
        assert len(res["recommendations"]) <= 2
        assert res["best_pick"] != ""

    def test_compare_fallback_when_ai_unavailable(self):
        from core.core_ai import compare_opportunities
        candidates = [
            {"symbol": "BTCUSDT", "price": 45000.0, "direction": "BUY"},
            {"symbol": "ETHUSDT", "price": 3000.0, "direction": "SELL"},
        ]

        with patch("core.core_ai._call_ai", return_value=None):
            res = compare_opportunities(candidates, max_recommendations=1)
        assert len(res["recommendations"]) == 1
        assert res["best_pick"] in ("BTCUSDT", "ETHUSDT")


class TestEnrichWithModules:
    def test_enrich_with_modules_fallback(self):
        from core.core_ai import enrich_with_modules
        df = _make_df(30)

        with patch("builtins.__import__", side_effect=ImportError("no module")):
            res = enrich_with_modules("BTCUSDT", df)
        assert res["liquidity_intel"] is None
        assert res["breakout_data"] is None

    def test_enrich_with_modules_success(self):
        from core.core_ai import enrich_with_modules
        df = _make_df(30)

        mock_liq = MagicMock(return_value={"liquidity_score": 75, "bias": "BULLISH"})
        mock_brk = MagicMock(return_value={"breakout_score": 60})

        orig_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def _mock_import(name, *args, **kwargs):
            if name == "engine.engine_liquidity":
                m = MagicMock()
                m.gather_liquidity_intel = mock_liq
                return m
            if name == "engine.engine_breakout":
                m = MagicMock()
                m.hunt_breakouts = mock_brk
                return m
            return orig_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_mock_import):
            res = enrich_with_modules("BTCUSDT", df)
        assert res["liquidity_intel"] is not None
        assert res["breakout_data"] is not None


class TestBackwardCompatibleImports:
    def test_imports_from_core_core_ai(self):
        from core.core_ai import analyze_coin
        from core.core_ai import analyze_coin_pure
        from core.core_ai import compare_opportunities
        from core.core_ai import enrich_with_modules
        from core.core_ai import call_ai
        from core.core_ai import get_provider_status
        from core.core_ai import force_provider_recovery
        from core.core_ai import health_check
        from core.core_ai import AI_ANALYST_SYSTEM
        from core.core_ai import AI_ANALYST_PURE_SYSTEM

        assert callable(analyze_coin)
        assert callable(analyze_coin_pure)
        assert callable(compare_opportunities)
        assert callable(enrich_with_modules)
        assert callable(call_ai)
        assert callable(get_provider_status)
        assert callable(force_provider_recovery)
        assert callable(health_check)
        assert isinstance(AI_ANALYST_SYSTEM, str)
        assert isinstance(AI_ANALYST_PURE_SYSTEM, str)

    def test_imports_from_core_package(self):
        from core import analyze_coin, AI_ANALYST_SYSTEM, call_ai
        assert callable(analyze_coin)
        assert callable(call_ai)
        assert isinstance(AI_ANALYST_SYSTEM, str)

    def test_prompt_constants_match_across_modules(self):
        from core.core_ai import AI_ANALYST_SYSTEM as s1, AI_ANALYST_PURE_SYSTEM as p1
        from core.ai_prompts import AI_ANALYST_SYSTEM as s2, AI_ANALYST_PURE_SYSTEM as p2
        assert s1 is s2
        assert p1 is p2

    def test_private_symbols_not_in_public_api(self):
        import core.core_ai as mod
        assert not hasattr(mod, "_p_lock")
        assert not hasattr(mod, "_p_key_idx")
        assert not hasattr(mod, "_p_rpm_calls")
        assert not hasattr(mod, "_load_env")
        assert not hasattr(mod, "_load_providers")
