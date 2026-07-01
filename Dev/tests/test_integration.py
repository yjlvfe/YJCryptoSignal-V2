"""
Integration tests for end-to-end workflows.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import pandas as pd
import numpy as np
import time
import json


class TestFullScanCycle:
    """Test complete scan cycle from data fetch to signal generation."""

    @pytest.fixture
    def setup_full_stack(self, sample_ohlcv_data):
        """Setup complete scanning stack with mocks."""
        with patch("data.data_fetcher.get_fetcher") as mock_fetcher, \
             patch("core.core_ai.analyze_coin_pure") as mock_ai, \
             patch("core.core_scanner._count_active_trades") as mock_count_trades, \
             patch("core.core_scanner._can_broadcast") as mock_can_broadcast, \
             patch("core.core_scanner._broadcast_signal") as mock_broadcast:

            # Data fetcher
            fetcher_instance = MagicMock()
            
            mock_provider = MagicMock()
            mock_provider.healthy = True
            mock_provider.name = "binance"
            mock_provider.fetch_tickers_24hr.return_value = [
                {"symbol": "BTCUSDT", "quote_volume": 1000000}
            ]
            
            fetcher_instance.providers = [mock_provider]
            fetcher_instance.fetch_klines_from.return_value = sample_ohlcv_data
            fetcher_instance.fetch_all_prices.return_value = {"BTCUSDT": 45000.0}
            mock_fetcher.return_value = fetcher_instance

            # AI
            mock_ai.return_value = {
                "decision": "ENTER",
                "direction": "BUY",
                "confidence": 85,
                "strength": 80,
                "entry": 45000,
                "stop_loss": 44300,
                "targets": [46000, 47000, 48000],
            }

            # Handlers
            mock_count_trades.return_value = 0
            mock_can_broadcast.return_value = (True, "")

            yield {
                "fetcher": fetcher_instance,
                "ai": mock_ai,
                "count_trades": mock_count_trades,
                "can_broadcast": mock_can_broadcast,
                "broadcast": mock_broadcast,
            }

    def test_full_scan_cycle_runs(self, setup_full_stack, tmp_path):
        """Running the scan loop once should call fetcher, analyzer, and broadcast."""
        from core.core_scanner import universal_scan_loop

        stack = setup_full_stack

        with patch("core.core_scanner.PROGRESS_FILE", tmp_path / "progress.json"), \
             patch("core.core_scanner.BROADCAST_CACHE_FILE", tmp_path / "broadcast.json"), \
             patch("core.core_scanner.SIGNAL_MSGS_FILE", tmp_path / "signal_msgs.json"), \
             patch("core.core_scanner.TRADES_FILE", tmp_path / "trades.json"), \
             patch("core.core_scanner.TRADES_HISTORY_FILE", tmp_path / "history.json"), \
             patch("core.core_scanner.SCANNER_LOCK", str(tmp_path / "scanner.lock")), \
             patch("time.sleep", side_effect=KeyboardInterrupt), \
             patch("engine.engine_multi_tf.scan_strength_matrix") as mock_mtf:

            # Mock MTF matrix results
            mock_mtf.return_value = [
                {"symbol": "BTCUSDT", "overall": "BUY", "alignment": 3}
            ]

            try:
                universal_scan_loop()
            except KeyboardInterrupt:
                pass

            # Assertions
            stack["ai"].assert_called()
            stack["broadcast"].assert_called()


class TestTradeLifecycle:
    """Test complete trade lifecycle."""

    @pytest.fixture
    def trade_stack(self, tmp_path):
        """Setup trade tracking stack."""
        with patch("trade.trade_tracker.DATA_DIR", tmp_path), \
             patch("trade.trade_tracker.TRADES_FILE", tmp_path / "trades.json"), \
             patch("trade.trade_tracker.HISTORY_FILE", tmp_path / "trades_history.json"), \
             patch("learn.learn_adaptive.evaluate_closed_trade") as mock_learn:

            yield {
                "learn": mock_learn,
            }

    def test_complete_trade_lifecycle(self, trade_stack):
        """Complete trade: open -> check/update -> close -> learn."""
        from trade.trade_tracker import add_trade, check_trades, load_trades

        # 1. Open trade
        success, message = add_trade(
            symbol="BTCUSDT",
            entry=45000.0,
            targets=[45900.0, 46800.0, 47700.0],
            stop_loss=44100.0,
            confidence=85,
            strategy_signals=["SMC", "RSI"]
        )
        assert success is True

        # 2. Check trades (updates prices & checks triggers)
        trades = load_trades()
        for t in trades:
            t["current_price"] = 46000.0  # hits TP1 since target is 45900

        closed, alerts = check_trades(trades)

        assert isinstance(closed, list)
        assert isinstance(alerts, list)


class TestAlertingIntegration:
    """Test alerting integration with other components."""

    def test_alert_manager_delivers_alert(self):
        """AlertManager should deliver alert to registered webhooks."""
        from utils.alerting import get_alert_manager, WebhookConfig, Alert, AlertLevel

        manager = get_alert_manager()
        manager.webhooks.clear()

        config = WebhookConfig(url="https://example.com/webhook", name="test_webhook")
        manager.add_webhook(config)

        with patch("utils.alerting.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_post.return_value = mock_resp

            alert = Alert(title="Test Alert", message="Integration testing", level=AlertLevel.INFO)
            manager.send_alert(alert)

            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[0][0] == "https://example.com/webhook"
            payload = call_args[1]["json"]
            assert payload["title"] == "Test Alert"
            assert payload["message"] == "Integration testing"