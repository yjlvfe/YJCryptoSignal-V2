"""
Unit tests for trade/ modules.
"""
import pytest
from unittest.mock import MagicMock, patch
import json
import time
from pathlib import Path


class TestTradeTracker:
    """Test trade_tracker module functions."""

    @pytest.fixture(autouse=True)
    def setup_paths(self, tmp_path):
        """Mock data directory paths to use a temporary directory."""
        with patch("trade.trade_tracker.DATA_DIR", tmp_path), \
             patch("trade.trade_tracker.TRADES_FILE", tmp_path / "trades.json"), \
             patch("trade.trade_tracker.HISTORY_FILE", tmp_path / "trades_history.json"):
            yield

    def test_load_save_trades(self):
        """Should persist trades to disk and reload."""
        from trade.trade_tracker import load_trades, save_trades

        trades = [{"symbol": "BTCUSDT", "status": "active"}]
        save_trades(trades)

        loaded = load_trades()
        assert len(loaded) == 1
        assert loaded[0]["symbol"] == "BTCUSDT"

    def test_add_trade(self):
        """Should add a new trade successfully."""
        from trade.trade_tracker import add_trade, get_active_trades

        # Initially empty
        assert len(get_active_trades()) == 0

        # Add trade
        success, message = add_trade(
            symbol="BTCUSDT",
            entry=45000.0,
            targets=[46000.0, 47000.0, 48000.0],
            stop_loss=44000.0,
            confidence=85,
            strategy_signals=["SMC"]
        )

        assert success is True
        active = get_active_trades()
        assert len(active) == 1
        assert active[0]["symbol"] == "BTCUSDT"
        assert active[0]["status"] == "active"


class TestTradeSafety:
    """Test trade_safety module functions."""

    @pytest.fixture(autouse=True)
    def setup_safety_path(self, tmp_path):
        """Mock SAFETY_FILE path in trade_safety."""
        with patch("trade.trade_safety.SAFETY_FILE", tmp_path / "safety_walls.json"):
            yield

    def test_enforce_safety_walls_allowed(self):
        """Should allow trading under normal circumstances."""
        from trade.trade_safety import enforce_safety_walls

        active_trades = []
        result = enforce_safety_walls(active_trades, portfolio_value=1000.0)

        assert result["allowed"] is True
        assert len(result["blocked_by"]) == 0

    def test_circuit_breaker_activation(self):
        """Should activate circuit breaker cooling on consecutive losses."""
        from trade.trade_safety import record_trade_result, enforce_safety_walls

        # Record consecutive losses to trigger cooling
        record_trade_result(-2.5)
        record_trade_result(-1.5)
        record_trade_result(-3.0)

        result = enforce_safety_walls([], portfolio_value=1000.0)
        assert result["allowed"] is False
        assert "CIRCUIT_BREAKER_COOLING" in result["blocked_by"] or "CIRCUIT_BREAKER" in result["blocked_by"]


class TestTradeSizing:
    """Test trade_sizing module functions."""

    def test_compute_volatility_adjustment(self):
        """Should compute volatility multiplier correctly."""
        from trade.trade_sizing import compute_volatility_adjustment

        # Lower ATR pct should yield higher/normal multiplier
        mult_low_vol = compute_volatility_adjustment(1.0)
        mult_high_vol = compute_volatility_adjustment(5.0)

        assert mult_low_vol >= mult_high_vol

    def test_compute_confidence_multiplier(self):
        """Should scale with confidence."""
        from trade.trade_sizing import compute_confidence_multiplier

        mult_high = compute_confidence_multiplier(0.9)
        mult_low = compute_confidence_multiplier(0.5)

        assert mult_high > mult_low


class TestTradeHeat:
    """Test trade_heat module functions."""

    @pytest.fixture(autouse=True)
    def setup_heat_path(self, tmp_path):
        """Mock HEAT_FILE/DATA_DIR in trade_heat."""
        with patch("trade.trade_heat.HEAT_FILE", tmp_path / "portfolio_heat.json"):
            yield

    def test_compute_portfolio_heat(self):
        """Should calculate portfolio heat based on active positions."""
        from trade.trade_heat import compute_portfolio_heat

        active_trades = [
            {
                "symbol": "BTCUSDT",
                "status": "active",
                "entry_price": 45000.0,
                "current_price": 46000.0,
                "position_size": {"position_units": 0.1, "position_value_usd": 4500.0}
            }
        ]

        heat = compute_portfolio_heat(active_trades, portfolio_value=10000.0)

        assert "unrealized_pnl_pct" in heat
        assert "blocked" in heat
        assert "active_trade_count" in heat
        assert heat["active_trade_count"] == 1