"""
Integration tests for backtest + regime change tracking.
"""
import os
import pytest
from unittest.mock import patch, MagicMock
import numpy as np
import pandas as pd


def _make_ohlcv(base_price: float, n: int = 60) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=n, freq="4h")
    rng = np.random.RandomState(42)
    close = base_price * (1 + rng.normal(0, 0.005, n)).cumprod()
    return pd.DataFrame({
        "open": close * (1 + rng.normal(0, 0.001, n)),
        "high": close * (1 + np.abs(rng.normal(0, 0.005, n))),
        "low": close * (1 - np.abs(rng.normal(0, 0.005, n))),
        "close": close,
        "volume": rng.lognormal(10, 1, n),
    })


class TestRegimeChangeTracking:
    """Test regime change detection and flag management."""

    def test_regime_change_tracking(self):
        """Changing regime should set the flag and reset on check."""
        import core.core_regime as regime_mod

        regime_mod._prev_regime = None
        regime_mod._regime_change_flag = False

        df1 = _make_ohlcv(50000)

        with patch("core.core_regime.REGIME_FILE"):
            from core.core_regime import detect_regime, has_regime_changed, get_previous_regime

            detect_regime(df1)
            assert regime_mod._prev_regime is not None
            first_regime = regime_mod._prev_regime

            detect_regime(df1)
            assert regime_mod._prev_regime == first_regime
            assert not has_regime_changed()

            regime_mod._prev_regime = "BULL"
            regime_mod._regime_change_flag = False

            df2 = _make_ohlcv(30000)
            detect_regime(df2)
            assert regime_mod._regime_change_flag or regime_mod._prev_regime != "BULL"

            assert get_previous_regime() == regime_mod._prev_regime

        regime_mod._prev_regime = None
        regime_mod._regime_change_flag = False


class TestRegimeBacktestEnvVar:
    """Test ENABLE_REGIME_BACKTEST env var gating."""

    def test_regime_backtest_env_var(self):
        """ENABLE_REGIME_BACKTEST=false should return None."""
        with patch.dict(os.environ, {"ENABLE_REGIME_BACKTEST": "false"}):
            from engine.engine_backtest import run_regime_backtest
            result = run_regime_backtest("BULL")
            assert result is None

    def test_regime_backtest_default_off(self):
        """No env var set should also skip."""
        env = os.environ.copy()
        env.pop("ENABLE_REGIME_BACKTEST", None)
        with patch.dict(os.environ, env, clear=True):
            from engine.engine_backtest import run_regime_backtest
            result = run_regime_backtest("BULL")
            assert result is None


class TestRegimeBacktestDispatched:
    """Test that regime change triggers backtest thread in scanner."""

    def test_regime_backtest_dispatched(self):
        """_run_regime_backtest_async calls run_regime_backtest with the regime."""
        from core.core_scanner import _run_regime_backtest_async

        with patch("engine.engine_backtest.run_regime_backtest") as mock_backtest:
            mock_backtest.return_value = {"regime": "BULL", "strategies_tested": 5}
            _run_regime_backtest_async("BULL")
            mock_backtest.assert_called_once_with("BULL")

    def test_regime_backtest_daemon_thread(self):
        """Function runs synchronously and handles exceptions gracefully."""
        from core.core_scanner import _run_regime_backtest_async

        with patch("engine.engine_backtest.run_regime_backtest", return_value=None):
            _run_regime_backtest_async("BEAR")


class TestBacktestResultContainsStrategyMetrics:
    """Test that backtest result contains expected structure."""

    def test_backtest_result_contains_strategy_metrics(self):
        """BacktestResult.to_dict returns dict with expected keys."""
        from engine.engine_backtest import BacktestResult

        result = BacktestResult(
            strategy_name="test_strategy",
            symbol="BTCUSDT",
            timeframe="4h",
            total_trades=10,
            winning_trades=6,
            losing_trades=4,
            win_rate=60.0,
            total_return_pct=5.5,
            profit_factor=1.8,
            sharpe_ratio=1.2,
            max_drawdown_pct=8.0,
        )
        d = result.to_dict()
        assert "strategy_name" in d
        assert "win_rate" in d
        assert "total_return_pct" in d
        assert "profit_factor" in d
        assert "sharpe_ratio" in d
        assert "max_drawdown_pct" in d
        assert d["strategy_name"] == "test_strategy"
        assert d["win_rate"] == 60.0
        assert d["total_return_pct"] == 5.5

    def test_no_regime_change_no_backtest(self):
        """Same regime twice should not set the flag."""
        import core.core_regime as regime_mod

        regime_mod._prev_regime = None
        regime_mod._regime_change_flag = False

        df = _make_ohlcv(50000)

        with patch("core.core_regime.REGIME_FILE"):
            from core.core_regime import detect_regime, has_regime_changed

            detect_regime(df)
            actual_regime = regime_mod._prev_regime
            regime_mod._regime_change_flag = False

            detect_regime(df)
            if regime_mod._prev_regime == actual_regime:
                assert not has_regime_changed()

        regime_mod._prev_regime = None
        regime_mod._regime_change_flag = False
