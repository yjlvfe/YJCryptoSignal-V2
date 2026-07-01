"""
Unit tests for core/core_scanner.py
"""
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
import json


class TestCoreScannerHelpers:
    """Test core scanner helper functions."""

    def test_is_stablecoin(self):
        """Should identify stablecoins correctly."""
        from core.core_scanner import _is_stablecoin

        assert _is_stablecoin("USDCUSDT") is True
        assert _is_stablecoin("BUSDUSDT") is True
        assert _is_stablecoin("EURCUSDT") is True
        assert _is_stablecoin("BTCUSDT") is False
        assert _is_stablecoin("ETHUSDT") is False

    def test_is_stock_token(self):
        """Should identify stock tokens correctly."""
        from core.core_scanner import _is_stock_token

        assert _is_stock_token("RNVDAUSDT") is True
        assert _is_stock_token("RDELLUSDT") is True
        assert _is_stock_token("BTCUSDT") is False

    def test_can_broadcast_new(self, tmp_path):
        """Should allow broadcasting if not recently broadcasted."""
        from core.core_scanner import _can_broadcast

        cache = {}
        with patch("core.core_scanner.BROADCAST_CACHE_FILE", tmp_path / "broadcast.json"), \
             patch("core.core_scanner.TRADES_FILE", tmp_path / "trades.json"), \
             patch("core.core_scanner.TRADES_HISTORY_FILE", tmp_path / "history.json"):

            allowed, reason = _can_broadcast("BTCUSDT", cache)
            assert allowed is True

    def test_can_broadcast_cached(self, tmp_path):
        """Should prevent broadcasting if in cache."""
        import time
        from core.core_scanner import _can_broadcast

        cache = {"BTCUSDT": time.time()}
        with patch("core.core_scanner.BROADCAST_CACHE_FILE", tmp_path / "broadcast.json"), \
             patch("core.core_scanner.TRADES_FILE", tmp_path / "trades.json"), \
             patch("core.core_scanner.TRADES_HISTORY_FILE", tmp_path / "history.json"):

            allowed, reason = _can_broadcast("BTCUSDT", cache)
            assert allowed is False
            assert "مبثوثة" in reason

    def test_count_active_trades(self, tmp_path):
        """Should return the count of active trades."""
        from core.core_scanner import _count_active_trades

        trades_file = tmp_path / "trades.json"
        trades_file.write_text(json.dumps([
            {"symbol": "BTCUSDT", "status": "active"},
            {"symbol": "ETHUSDT", "status": "pending"},
            {"symbol": "SOLUSDT", "status": "closed"},
        ]))

        with patch("core.core_scanner.TRADES_FILE", trades_file):
            assert _count_active_trades() == 2

    def test_gather_all_exchange_coins(self):
        """Should gather coins from healthy providers, ignoring excluded/stablecoins."""
        from core.core_scanner import _gather_all_exchange_coins

        mock_provider1 = MagicMock()
        mock_provider1.name = "MEXC"
        mock_provider1.healthy = True
        mock_provider1.fetch_tickers_24hr.return_value = [
            {"symbol": "BTCUSDT", "quote_volume": 1000000},
            {"symbol": "USDCUSDT", "quote_volume": 500000},  # stablecoin
        ]

        mock_fetcher = MagicMock()
        mock_fetcher.providers = [mock_provider1]

        coins, stats, volume_sums = _gather_all_exchange_coins(mock_fetcher, min_volume=1000)
        # Should only have BTCUSDT
        assert len(coins) == 1
        assert coins[0]["symbol"] == "BTCUSDT"