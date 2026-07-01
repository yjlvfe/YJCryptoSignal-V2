"""
pytest configuration and shared fixtures for CryptoSignal tests.
"""
import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


# ──────────────────────────────────────────────
# Session-scoped fixtures
# ──────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Setup test environment variables."""
    os.environ.setdefault("BOT_TOKEN", "test_token_123")
    os.environ.setdefault("ADMIN_ID", "123456789")
    os.environ.setdefault("DATA_DIR", "/tmp/test_cryptosignal")
    os.environ.setdefault("OPENAI_API_KEY", "test_openai_key")
    os.environ.setdefault("DEEPSEEK_API_KEY", "test_deepseek_key")
    os.environ.setdefault("GROQ_API_KEY", "test_groq_key")
    os.environ.setdefault("COHERE_API_KEY", "test_cohere_key")
    os.environ.setdefault("OPENROUTER_API_KEY", "test_openrouter_key")
    os.environ.setdefault("GEMINI_API_KEY", "test_gemini_key")
    yield
    # Cleanup handled by tmp_path fixtures


# ──────────────────────────────────────────────
# Core module fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def mock_ai_providers():
    """Mock AI provider responses."""
    with patch("core.core_ai.AsyncOpenAI") as mock_openai, \
         patch("core.core_ai.AsyncGroq") as mock_groq, \
         patch("core.core_ai.AsyncCohere") as mock_cohere, \
         patch("core.core_ai.AsyncAnthropic") as mock_anthropic, \
         patch("core.core_ai.AsyncGoogleGenerativeAI") as mock_gemini:

        # Setup mock responses
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"decision": "ENTER", "direction": "BUY", "confidence": 85, "stop_loss": 45000, "targets": [46000, 47000, 48000], "duration_hours": 4}'))]
        mock_response.usage = MagicMock(total_tokens=150)

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai.return_value = mock_client
        mock_groq.return_value = mock_client
        mock_cohere.return_value = mock_client
        mock_anthropic.return_value = mock_client
        mock_gemini.return_value = mock_client

        yield {
            "openai": mock_openai,
            "groq": mock_groq,
            "cohere": mock_cohere,
            "anthropic": mock_anthropic,
            "gemini": mock_gemini,
        }


@pytest.fixture
def mock_http_responses():
    """Mock HTTP responses for exchange APIs."""
    with patch("httpx.AsyncClient.get") as mock_get, \
         patch("httpx.AsyncClient.post") as mock_post:

        # Default successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": [
                [1700000000000, 1000, 45000, 45100, 44900, 45050, 45050000, True],
                [1700003600000, 1100, 45100, 45200, 45000, 45150, 45150000, True],
            ],
            "retCode": 0
        }
        mock_get.return_value = mock_response
        mock_post.return_value = mock_response

        yield {"get": mock_get, "post": mock_post}


@pytest.fixture
def mock_telegram_bot():
    """Mock Telegram bot for testing handlers."""
    with patch("telegram.Bot") as mock_bot_class:
        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock(return_value=MagicMock(message_id=123))
        mock_bot.send_photo = AsyncMock(return_value=MagicMock(message_id=124))
        mock_bot.edit_message_text = AsyncMock()
        mock_bot.answer_callback_query = AsyncMock()
        mock_bot_class.return_value = mock_bot
        yield mock_bot


@pytest.fixture
def sample_ohlcv_data():
    """Sample OHLCV data for testing."""
    import pandas as pd
    import numpy as np

    dates = pd.date_range(start="2024-01-01", periods=100, freq="4h")
    np.random.seed(42)
    base_price = 45000
    returns = np.random.normal(0, 0.01, 100)
    prices = base_price * (1 + returns).cumprod()

    df = pd.DataFrame({
        "timestamp": dates,
        "open": prices * (1 + np.random.normal(0, 0.001, 100)),
        "high": prices * (1 + np.abs(np.random.normal(0, 0.005, 100))),
        "low": prices * (1 - np.abs(np.random.normal(0, 0.005, 100))),
        "close": prices,
        "volume": np.random.lognormal(10, 1, 100).astype(int),
    })
    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)

    return df


@pytest.fixture
def sample_signal_data():
    """Sample signal data for testing."""
    return {
        "symbol": "BTCUSDT",
        "direction": "BUY",
        "entry_price": 45000.0,
        "stop_loss": 44100.0,
        "targets": [45900.0, 46800.0, 47700.0],
        "confidence": 85,
        "duration_hours": 4,
        "strategies": ["SMC", "Market_Structure", "RSI"],
        "regime": "TRENDING_BULL",
        "timeframe": "4H",
        "analysis": "Strong bullish structure with CHOCH confirmed...",
    }


@pytest.fixture
def sample_trade_data():
    """Sample trade data for testing."""
    return {
        "trade_id": "test_trade_123",
        "user_id": 123456789,
        "symbol": "BTCUSDT",
        "direction": "BUY",
        "entry_price": 45000.0,
        "quantity": 0.01,
        "stop_loss": 44100.0,
        "targets": [45900.0, 46800.0, 47700.0],
        "status": "OPEN",
        "opened_at": "2024-01-15T10:00:00Z",
        "strategies": ["SMC", "Market_Structure"],
        "confidence": 85,
    }


# ──────────────────────────────────────────────
# Temporary file/directory fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def temp_data_dir(tmp_path):
    """Create temporary data directory structure."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "trades").mkdir()
    (data_dir / "learning").mkdir()
    (data_dir / "logs").mkdir()
    return data_dir


@pytest.fixture
def temp_log_file(tmp_path):
    """Temporary log file for testing logging."""
    return tmp_path / "test.log"


# ──────────────────────────────────────────────
# Utility fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def mock_time():
    """Mock time for deterministic tests."""
    with patch("time.time", return_value=1700000000.0), \
         patch("time.monotonic", return_value=1000.0), \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        yield {"sleep": mock_sleep}


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton state between tests."""
    # Reset metrics registry
    import core.core_metrics as metrics_module
    if hasattr(metrics_module, "_global_registry"):
        metrics_module._global_registry = None

    # Reset logging context
    import core.core_logging as logging_module
    if hasattr(logging_module, "_context_var"):
        logging_module._context_var.set({})

    yield

    # Cleanup after test
    import gc
    gc.collect()


# ──────────────────────────────────────────────
# Test helpers
# ──────────────────────────────────────────────

class AsyncContextManager:
    """Helper for async context manager mocking."""
    def __init__(self, return_value):
        self._return_value = return_value

    async def __aenter__(self):
        return self._return_value

    async def __aexit__(self, *args):
        pass


def make_async_mock(return_value):
    """Create an async mock that returns the given value."""
    mock = AsyncMock()
    mock.return_value = return_value
    return mock


def assert_metric_recorded(metric_name: str, labels: Dict[str, str] = None):
    """Assert a metric was recorded with given labels."""
    import core.core_metrics as metrics
    registry = metrics.get_registry()
    metric = registry.get(metric_name)
    assert metric is not None, f"Metric {metric_name} not found"
    if labels:
        # For labeled metrics, check the labeled instance exists
        labeled_metric = metric.labels(**labels)
        assert labeled_metric is not None
    return metric
