"""
Unit tests for data fetching and exchange modules.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import pandas as pd
import numpy as np
import json
import os


class TestDataFetcher:
    """Test DataFetcher module functions and classes."""

    @pytest.fixture
    def mock_fetcher(self):
        """Mock the global fetcher for test isolation."""
        with patch("data.data_fetcher.get_fetcher") as mock_get:
            mock_instance = MagicMock()
            mock_get.return_value = mock_instance
            yield mock_instance

    def test_fetch_klines(self, mock_fetcher):
        """fetch_klines should invoke fetcher.fetch_klines."""
        mock_df = pd.DataFrame([[1700000000000, 45000, 45100, 44900, 45050, 1000]],
                               columns=["timestamp", "open", "high", "low", "close", "volume"])
        mock_fetcher.fetch_klines.return_value = mock_df

        from data.data_fetcher import fetch_klines
        df = fetch_klines("BTCUSDT", "4h", limit=100)

        assert isinstance(df, pd.DataFrame)
        mock_fetcher.fetch_klines.assert_called_once_with("BTCUSDT", "4h", 100)

    def test_fetch_multi_timeframe(self, mock_fetcher):
        """fetch_multi_timeframe should return dict of DataFrames."""
        mock_df = pd.DataFrame([[1700000000000, 45000, 45100, 44900, 45050, 1000]],
                               columns=["timestamp", "open", "high", "low", "close", "volume"])
        mock_fetcher.fetch_klines.return_value = mock_df

        from data.data_fetcher import fetch_multi_timeframe
        with patch("time.sleep"):  # Speed up test
            result = fetch_multi_timeframe("BTCUSDT", ["4h", "1h"])

        assert isinstance(result, dict)
        assert "4h" in result
        assert "1h" in result

    def test_get_top_volume_pairs(self, mock_fetcher):
        """get_top_volume_pairs should return list of sorted symbols."""
        mock_fetcher.fetch_tickers_24hr.return_value = [
            {"symbol": "BTCUSDT", "quote_volume": 1000000},
            {"symbol": "ETHUSDT", "quote_volume": 500000},
        ]

        from data.data_fetcher import get_top_volume_pairs
        symbols = get_top_volume_pairs(limit=2)

        assert len(symbols) == 2
        assert symbols[0] == "BTCUSDT"
        assert symbols[1] == "ETHUSDT"


class TestExchangeProviders:
    """Test individual exchange providers."""

    def test_mexc_provider_symbol_mapping(self):
        """MEXC symbol conversion should remove hyphen or keep raw."""
        from data.data_fetcher import MEXCProvider
        provider = MEXCProvider()
        assert provider.symbol_to_exchange("BTCUSDT") == "BTCUSDT"

    @patch("requests.get")
    def test_okx_provider_fetch_klines(self, mock_get):
        """OKXProvider fetch_klines should parse response correctly."""
        from data.data_fetcher import OKXProvider
        provider = OKXProvider()

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "code": "0",
            "data": [
                ["1700000000000", "45000", "45100", "44900", "45050", "1000", "45000000", "45000000", "1"]
            ]
        }
        mock_get.return_value = mock_resp

        df = provider.fetch_klines("BTCUSDT", "4h", limit=100)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert df.iloc[0]["close"] == 45050.0


class TestRedisCache:
    """Test RedisCache class for optional caching layer."""

    def test_redis_cache_available(self):
        """When Redis is available, get/set should use Redis with TTL."""
        import sys
        mock_redis_module = MagicMock()
        mock_redis = MagicMock()
        mock_redis_module.Redis.return_value = mock_redis
        mock_redis.ping.return_value = True
        mock_redis.get.return_value = json.dumps({"BTCUSDT": 45000.0})
        mock_redis.setex.return_value = True

        from data.data_fetcher import RedisCache

        with patch.dict(sys.modules, {"redis": mock_redis_module}):
            with patch.dict(os.environ, {"USE_REDIS": "true", "REDIS_HOST": "localhost", "REDIS_PORT": "6379", "REDIS_CACHE_TTL": "60"}):
                cache = RedisCache()

        assert cache._enabled is True
        cache.set("prices_all", {"BTCUSDT": 45000.0})
        mock_redis.setex.assert_called_once_with("prices_all", 60, json.dumps({"BTCUSDT": 45000.0}))

        result = cache.get("prices_all")
        assert result == {"BTCUSDT": 45000.0}

    def test_redis_cache_unavailable(self):
        """When Redis import fails, cache should fall back to in-memory dict."""
        import sys
        mock_redis_module = MagicMock()
        mock_redis_module.Redis.side_effect = ConnectionError("no redis")

        from data.data_fetcher import RedisCache

        with patch.dict(sys.modules, {"redis": mock_redis_module}):
            with patch.dict(os.environ, {"USE_REDIS": "true", "REDIS_HOST": "badhost", "REDIS_PORT": "9999"}):
                cache = RedisCache()

        assert cache._enabled is False
        assert cache._redis is None

        cache.set("test_key", {"foo": "bar"})
        result = cache.get("test_key")
        assert result == {"foo": "bar"}

    def test_cached_fetch_klines(self):
        """Second fetch_klines call should return cached result without hitting API."""
        from data.data_fetcher import MultiExchangeFetcher

        mock_df = pd.DataFrame([
            {"date": "2024-01-01", "open": 45000.0, "high": 45100.0, "low": 44900.0, "close": 45050.0, "volume": 1000.0}
        ])

        fetcher = MultiExchangeFetcher()
        cache_key = "klines_BTCUSDT_4h_100"
        fetcher._cache.set(cache_key, mock_df.to_dict(orient="records"))

        fetcher._try_all = MagicMock(return_value=(mock_df, "MEXC"))

        result = fetcher.fetch_klines("BTCUSDT", "4h", limit=100)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        fetcher._try_all.assert_not_called()

    def test_cache_clear_on_error(self):
        """When fetch fails, cached entry should be invalidated."""
        from data.data_fetcher import MultiExchangeFetcher

        fetcher = MultiExchangeFetcher()
        cache_key = "klines_BTCUSDT_4h_100"
        fetcher._cache.set(cache_key, 42)

        assert fetcher._cache.get(cache_key) is not None

        fetcher._try_all = MagicMock(side_effect=RuntimeError("All exchanges failed"))

        with pytest.raises(RuntimeError, match="All exchanges failed"):
            fetcher.fetch_klines("BTCUSDT", "4h", limit=100)

        assert fetcher._cache.get(cache_key) is None

    def test_redis_disabled_by_env(self):
        """USE_REDIS=false should skip Redis init entirely."""
        from data.data_fetcher import RedisCache

        with patch.dict(os.environ, {"USE_REDIS": "false"}):
            cache = RedisCache()

        assert cache._enabled is False
        assert cache._redis is None

        cache.set("key", {"val": 1})
        assert cache.get("key") == {"val": 1}
        cache.delete("key")
        assert cache.get("key") is None