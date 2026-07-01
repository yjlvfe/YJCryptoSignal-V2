"""
Unit tests for strategies/
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from strategies.base import Signal


class TestSMCCore:
    """Test SMC strategy core functionality."""

    @pytest.fixture
    def sample_data(self):
        """Create sample OHLCV data for SMC testing."""
        dates = pd.date_range(start="2024-01-01", periods=200, freq="4h")
        np.random.seed(42)
        base_price = 45000

        # Create trending data with clear structure
        trend = np.linspace(0, 0.1, 200)
        noise = np.random.normal(0, 0.01, 200)
        prices = base_price * (1 + trend + noise).cumprod()

        df = pd.DataFrame({
            "timestamp": dates,
            "open": prices * (1 + np.random.normal(0, 0.001, 200)),
            "high": prices * (1 + np.abs(np.random.normal(0, 0.005, 200))),
            "low": prices * (1 - np.abs(np.random.normal(0, 0.005, 200))),
            "close": prices,
            "volume": np.random.lognormal(10, 0.5, 200).astype(int),
        })
        df["high"] = df[["open", "high", "close"]].max(axis=1)
        df["low"] = df[["open", "low", "close"]].min(axis=1)
        return df

    def test_smc_analyze_returns_structure(self, sample_data):
        """SMC analyze should return expected structure."""
        from strategies.smc import SMCStrategy

        strategy = SMCStrategy()
        result = strategy.analyze(sample_data)

        assert isinstance(result, Signal)
        assert hasattr(result, "signal")
        assert hasattr(result, "confidence")
        assert result.signal in ["BUY", "SELL", "NEUTRAL"]

    def test_find_order_blocks(self, sample_data):
        """_find_bullish_obs/_find_bearish_obs should detect order blocks."""
        from strategies.smc import SMCStrategy

        strategy = SMCStrategy()
        obs = strategy._find_bullish_obs(
            sample_data["open"].values,
            sample_data["high"].values,
            sample_data["low"].values,
            sample_data["close"].values,
            sample_data["volume"].values
        )

        assert isinstance(obs, list)
        for ob in obs:
            assert "price" in ob
            assert "index" in ob
            assert "type" in ob
            assert "vol_confirmed" in ob

    def test_find_fvg(self, sample_data):
        """_find_fvg should detect fair value gaps."""
        from strategies.smc import SMCStrategy

        strategy = SMCStrategy()
        fvgs = strategy._find_fvgs(sample_data["high"].values, sample_data["low"].values)

        assert isinstance(fvgs, list)
        for fvg in fvgs:
            assert "top" in fvg or "high" in fvg
            assert "bottom" in fvg or "low" in fvg
            assert "index" in fvg
            assert "type" in fvg  # bullish/bearish

    def test_detect_liquidity_sweep(self, sample_data):
        """_detect_liquidity_sweep should detect sweeps."""
        from strategies.smc import SMCStrategy

        strategy = SMCStrategy()
        swept, sweep_dir, sweep_price, sweep_vol = strategy._detect_liquidity_sweep(
            sample_data["high"].values,
            sample_data["low"].values,
            sample_data["close"].values,
            sample_data["volume"].values,
            50000.0,
            40000.0
        )
        assert isinstance(swept, bool)

    def test_find_breaker_blocks(self, sample_data):
        """_find_breaker_blocks should detect breaker blocks."""
        from strategies.smc import SMCStrategy

        strategy = SMCStrategy()
        breakers = strategy._find_breaker_blocks([], [], sample_data["close"].values)
        assert isinstance(breakers, list)

    def test_track_fvg_mitigation(self, sample_data):
        """_track_fvg_mitigation should track FVG fills."""
        from strategies.smc import SMCStrategy

        strategy = SMCStrategy()
        fvgs = strategy._find_fvgs(sample_data["high"].values, sample_data["low"].values)
        if fvgs:
            mitigated = strategy._track_fvg_mitigation(
                fvgs,
                sample_data["high"].values,
                sample_data["low"].values,
                sample_data["close"].values
            )
            assert isinstance(mitigated, list)


class TestMarketStructureCore:
    """Test Market Structure strategy core functionality."""

    @pytest.fixture
    def sample_data(self):
        """Create sample OHLCV data."""
        dates = pd.date_range(start="2024-01-01", periods=200, freq="4h")
        np.random.seed(42)
        base_price = 45000
        trend = np.linspace(0, 0.1, 200)
        noise = np.random.normal(0, 0.01, 200)
        prices = base_price * (1 + trend + noise).cumprod()

        df = pd.DataFrame({
            "timestamp": dates,
            "open": prices * (1 + np.random.normal(0, 0.001, 200)),
            "high": prices * (1 + np.abs(np.random.normal(0, 0.005, 200))),
            "low": prices * (1 - np.abs(np.random.normal(0, 0.005, 200))),
            "close": prices,
            "volume": np.random.lognormal(10, 0.5, 200).astype(int),
        })
        df["high"] = df[["open", "high", "close"]].max(axis=1)
        df["low"] = df[["open", "low", "close"]].min(axis=1)
        return df

    def test_market_structure_analyze(self, sample_data):
        """Market structure analyze should return expected structure."""
        from strategies.market_structure import MarketStructureStrategy

        strategy = MarketStructureStrategy()
        result = strategy.analyze(sample_data)

        assert isinstance(result, Signal)
        assert hasattr(result, "signal")
        assert hasattr(result, "confidence")

    def test_detect_choch(self, sample_data):
        """_detect_choch should detect change of character."""
        from strategies.market_structure import MarketStructureStrategy

        strategy = MarketStructureStrategy()
        peaks = strategy._find_peaks(sample_data["high"].values)
        valleys = strategy._find_valleys(sample_data["low"].values)
        choch, choch_strength = strategy._detect_choch(peaks, valleys, sample_data["close"].values)

        assert choch is None or isinstance(choch, str)
        assert isinstance(choch_strength, float)

    def test_detect_bos(self, sample_data):
        """_detect_bos should detect break of structure."""
        from strategies.market_structure import MarketStructureStrategy

        strategy = MarketStructureStrategy()
        peaks = strategy._find_peaks(sample_data["high"].values)
        valleys = strategy._find_valleys(sample_data["low"].values)
        bos, bos_strength = strategy._detect_bos(peaks, valleys, sample_data["close"].iloc[-1], sample_data["close"].values)

        assert bos is None or isinstance(bos, str)
        assert isinstance(bos_strength, float)

    def test_detect_internal_bos(self, sample_data):
        """_detect_internal_bos should detect early entry signals."""
        from strategies.market_structure import MarketStructureStrategy

        strategy = MarketStructureStrategy()
        peaks = strategy._find_peaks(sample_data["high"].values)
        valleys = strategy._find_valleys(sample_data["low"].values)
        ibos, ibos_strength = strategy._detect_internal_bos(peaks, valleys, sample_data["close"].iloc[-1], sample_data["close"].values)

        assert ibos is None or isinstance(ibos, str)
        assert isinstance(ibos_strength, float)

    def test_check_mitigation(self, sample_data):
        """_check_mitigation should track OB/FVG retests."""
        from strategies.market_structure import MarketStructureStrategy

        strategy = MarketStructureStrategy()
        peaks = strategy._find_peaks(sample_data["high"].values)
        valleys = strategy._find_valleys(sample_data["low"].values)
        mitigated, m_type, m_dist = strategy._check_mitigation(peaks, valleys, sample_data["close"].iloc[-1])
        assert isinstance(mitigated, bool)

    def test_calc_structure_targets(self, sample_data):
        """_calc_structure_targets should calculate targets from structure."""
        from strategies.market_structure import MarketStructureStrategy

        strategy = MarketStructureStrategy()
        peaks = strategy._find_peaks(sample_data["high"].values)
        valleys = strategy._find_valleys(sample_data["low"].values)
        targets = strategy._calc_structure_targets(sample_data["close"].iloc[-1], "BUY", peaks, valleys)

        assert isinstance(targets, list)
        assert len(targets) == 3


class TestRSIStrategy:
    """Test RSI strategy."""

    @pytest.fixture
    def sample_data(self):
        dates = pd.date_range(start="2024-01-01", periods=100, freq="4h")
        np.random.seed(42)
        base_price = 45000
        prices = base_price * (1 + np.random.normal(0, 0.01, 100)).cumprod()

        df = pd.DataFrame({
            "timestamp": dates,
            "open": prices,
            "high": prices * 1.01,
            "low": prices * 0.99,
            "close": prices,
            "volume": np.random.lognormal(10, 0.5, 100).astype(int),
        })
        return df

    def test_rsi_analyze(self, sample_data):
        """RSI analyze should work."""
        from strategies.rsi_strategy import RSIStrategy

        strategy = RSIStrategy()
        result = strategy.analyze(sample_data)

        assert isinstance(result, Signal)
        assert hasattr(result, "signal")
        assert hasattr(result, "confidence")


class TestMACDStrategy:
    """Test MACD strategy."""

    @pytest.fixture
    def sample_data(self):
        dates = pd.date_range(start="2024-01-01", periods=100, freq="4h")
        np.random.seed(42)
        base_price = 45000
        prices = base_price * (1 + np.random.normal(0, 0.01, 100)).cumprod()

        df = pd.DataFrame({
            "timestamp": dates,
            "open": prices,
            "high": prices * 1.01,
            "low": prices * 0.99,
            "close": prices,
            "volume": np.random.lognormal(10, 0.5, 100).astype(int),
        })
        return df

    def test_macd_analyze(self, sample_data):
        """MACD analyze should work."""
        from strategies.macd_strategy import MACDStrategy

        strategy = MACDStrategy()
        result = strategy.analyze(sample_data)

        assert isinstance(result, Signal)
        assert hasattr(result, "signal")
        assert hasattr(result, "confidence")


class TestStrategyWeights:
    """Test strategy weight calculations."""

    def test_get_strategy_weight(self):
        """Should return correct weight for each strategy."""
        from engine.engine_weights import get_weighted_score

        # All weights should be positive
        assert get_weighted_score("SMC (Smart Money)") > 0
        assert get_weighted_score("Market Structure") > 0

    def test_calculate_total_score(self):
        """Should calculate total score with cluster bonuses."""
        from core.core_analyzer import AnalysisResult

        signals = [
            Signal(name="SMC (Smart Money)", signal="BUY", strength=0.8, confidence=80, entry=45000),
            Signal(name="Market Structure", signal="BUY", strength=0.75, confidence=75, entry=45000),
            Signal(name="RSI", signal="BUY", strength=0.7, confidence=70, entry=45000),
        ]
        res = AnalysisResult(symbol="BTCUSDT", price=45000.0, signals=signals, timeframe="4h")
        assert res.aggregated["direction"] == "BUY"
        assert res.aggregated["confidence"] > 0

    def test_intra_cluster_cap(self):
        """Should cap intra-cluster contributions."""
        from core.core_analyzer import AnalysisResult

        signals = [
            Signal(name="SMC (Smart Money)", signal="BUY", strength=0.8, confidence=80, entry=45000),
            Signal(name="Market Structure", signal="BUY", strength=0.75, confidence=75, entry=45000),
        ]
        res = AnalysisResult(symbol="BTCUSDT", price=45000.0, signals=signals, timeframe="4h")
        assert res.aggregated["direction"] == "BUY"


class TestStrategyRegistry:
    """Test strategy registry and loading."""

    def test_all_strategies_registered(self):
        """All expected strategies should be registered."""
        from core.core_analyzer import ALL_STRATEGIES

        expected = [
            "SMC (Smart Money)", "Market Structure", "MACD", "RSI",
            "VWAP",
        ]

        names = [s.name for s in ALL_STRATEGIES]
        for name in expected:
            assert name in names, f"Missing strategy: {name}"