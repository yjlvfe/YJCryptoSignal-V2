"""
Unit tests for learn/ modules.
"""
import pytest
from unittest.mock import MagicMock, patch
import json
import time
from pathlib import Path


class TestLearnAdaptive:
    """Test learn_adaptive module."""

    @pytest.fixture(autouse=True)
    def setup_dirs(self, tmp_path):
        """Mock paths in learn_adaptive to use temp directory."""
        with patch("learn.learn_adaptive.LEARN_DIR", tmp_path), \
             patch("learn.learn_adaptive.LEARN_FILE", tmp_path / "strategy_stats.json"), \
             patch("learn.learn_adaptive.WEIGHTS_FILE", tmp_path / "adjusted_weights.json"), \
             patch("learn.learn_adaptive.PERF_FILE", tmp_path / "regime_performance.json"):
            
            # Reset global stats/regime dicts inside module if any
            import learn.learn_adaptive as la
            la._strategy_stats = {}
            la._regime_stats = {}
            yield

    def test_record_trade_outcome_win(self):
        """Should record winning trade outcome for learning."""
        from learn.learn_adaptive import record_trade_outcome, TradeRecord, get_all_stats

        record = TradeRecord(
            symbol="BTCUSDT",
            direction="BUY",
            entry=45000.0,
            exit=46000.0,
            profit_pct=2.2,
            strategies_used=["SMC", "RSI"],
            market_regime="BULL",
            btc_trend="UP",
            duration_hours=2.0,
            closed_at=time.time()
        )

        record_trade_outcome(record)

        stats = get_all_stats()
        assert "SMC" in stats
        assert "RSI" in stats
        
        smc_stats = stats["SMC"]
        assert smc_stats.total_signals == 1
        assert smc_stats.winning_signals == 1
        assert smc_stats.losing_signals == 0

    def test_record_trade_outcome_loss(self):
        """Should record losing trade outcome for learning."""
        from learn.learn_adaptive import record_trade_outcome, TradeRecord, get_all_stats

        record = TradeRecord(
            symbol="ETHUSDT",
            direction="BUY",
            entry=3000.0,
            exit=2900.0,
            profit_pct=-3.3,
            strategies_used=["MACD"],
            market_regime="BEAR",
            btc_trend="DOWN",
            duration_hours=1.5,
            closed_at=time.time()
        )

        record_trade_outcome(record)

        stats = get_all_stats()
        assert "MACD" in stats
        macd_stats = stats["MACD"]
        assert macd_stats.total_signals == 1
        assert macd_stats.winning_signals == 0
        assert macd_stats.losing_signals == 1

    def test_get_adjusted_weights(self):
        """Should adjust strategy weights based on performance."""
        from learn.learn_adaptive import get_adjusted_weights, StrategyStats
        import learn.learn_adaptive as la

        # Set up mock strategy stats with sufficient signals (>=30)
        la._strategy_stats["SMC"] = StrategyStats(
            name="SMC",
            total_signals=35,
            winning_signals=25,
            bull_signals=35,
            bull_wins=25,
            win_rate=0.71,
            profit_factor=2.5,
        )
        la._strategy_stats["RSI"] = StrategyStats(
            name="RSI",
            total_signals=35,
            winning_signals=10,
            bull_signals=35,
            bull_wins=10,
            win_rate=0.28,
            profit_factor=0.8,
        )

        base_weights = {"SMC": 1.0, "RSI": 1.0}
        adjusted = get_adjusted_weights(current_regime="BULL", base_weights=base_weights)

        # SMC should have higher weight since it won
        assert adjusted["SMC"] > adjusted["RSI"]

    def test_get_adaptive_thresholds(self):
        """Should adapt confidence and strength thresholds based on recent performance."""
        from learn.learn_adaptive import get_adaptive_thresholds

        # Test base thresholds when there is no data
        strength, confidence = get_adaptive_thresholds(25, 40)
        assert strength == 25
        assert confidence == 40

    def test_evaluate_closed_trade(self):
        """Should parse closed trade dictionary and record it."""
        from learn.learn_adaptive import evaluate_closed_trade, get_all_stats

        trade = {
            "symbol": "SOLUSDT",
            "direction": "BUY",
            "entry_price": 100.0,
            "close_price": 105.0,
            "pnl_pct": 5.0,
            "strategies": ["VWAP"],
            "duration_min": 120.0
        }

        evaluate_closed_trade(trade)

        stats = get_all_stats()
        assert "VWAP" in stats
        assert stats["VWAP"].total_signals == 1