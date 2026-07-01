"""
Unit tests for core/core_logging.py
"""
import json
import logging
import pytest
from unittest.mock import MagicMock, patch
from io import StringIO


class TestJSONFormatter:
    """Test JSON log formatter."""

    def test_json_formatter_basic(self):
        """JSON formatter should produce valid JSON."""
        from core.core_logging import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.module = "test"
        record.funcName = "test_func"

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["level"] == "INFO"
        assert parsed["message"] == "Test message"
        assert parsed["logger"] == "test.logger"
        assert "timestamp" in parsed
        assert parsed["module"] == "test"
        assert parsed["function"] == "test_func"
        assert parsed["service"] == "cryptosignal"

    def test_json_formatter_with_extra(self):
        """JSON formatter should include extra fields."""
        from core.core_logging import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.extra_field = "extra_value"
        record.user_id = 12345
        record.request_id = "req-abc-123"

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["extra_field"] == "extra_value"
        assert parsed["user_id"] == 12345
        assert parsed["request_id"] == "req-abc-123"

    def test_json_formatter_with_exception(self):
        """JSON formatter should include exception info."""
        from core.core_logging import JSONFormatter

        formatter = JSONFormatter()
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert "exception" in parsed
        assert parsed["exception"]["type"] == "ValueError"
        assert parsed["exception"]["message"] == "Test error"
        assert "traceback" in parsed["exception"]

    def test_json_formatter_excludes_internal(self):
        """JSON formatter should exclude internal log record fields."""
        from core.core_logging import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        parsed = json.loads(output)

        # These should not be in output
        assert "pathname" not in parsed
        assert "lineno" not in parsed
        assert "args" not in parsed
        assert "exc_info" not in parsed
        assert "exc_text" not in parsed
        assert "stack_info" not in parsed
        assert "relativeCreated" not in parsed
        assert "thread" not in parsed
        assert "threadName" not in parsed
        assert "process" not in parsed
        assert "processName" not in parsed


class TestContextLogger:
    """Test context logger."""

    def test_context_logger_binds_context(self):
        """ContextLogger should bind and include context."""
        from core.core_logging import ContextLogger, JSONFormatter

        logger = ContextLogger("test.context")
        logger.logger.setLevel(logging.DEBUG)

        # Capture log output
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        logger.logger.addHandler(handler)

        # Bind context
        logger.set_context(user_id=12345, request_id="req-123")
        logger.info("Test with context")

        output = stream.getvalue().strip()
        parsed = json.loads(output)

        assert parsed["user_id"] == 12345
        assert parsed["request_id"] == "req-123"
        assert parsed["message"] == "Test with context"

    def test_context_logger_clears_context(self):
        """ContextLogger should clear context."""
        from core.core_logging import ContextLogger, JSONFormatter

        logger = ContextLogger("test.context2")
        logger.logger.setLevel(logging.DEBUG)

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        logger.logger.addHandler(handler)

        logger.set_context(user_id=12345)
        logger.clear_context()
        logger.info("No context")

        output = stream.getvalue().strip()
        parsed = json.loads(output)

        assert "user_id" not in parsed

    def test_context_logger_thread_isolation(self):
        """ContextLogger should isolate context per thread."""
        from core.core_logging import ContextLogger, JSONFormatter
        import threading

        logger = ContextLogger("test.thread")
        logger.logger.setLevel(logging.DEBUG)

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        logger.logger.addHandler(handler)

        results = {}

        def worker(thread_id):
            logger.set_context(thread_id=thread_id)
            logger.info(f"Message from thread {thread_id}")
            lines = stream.getvalue().strip().split('\n')
            last_line = lines[-1] if lines else ""
            results[thread_id] = json.loads(last_line)

        t1 = threading.Thread(target=worker, args=(1,))
        t2 = threading.Thread(target=worker, args=(2,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Each thread should see its own context
        assert results[1]["thread_id"] == 1
        assert results[2]["thread_id"] == 2

    def test_context_logger_log_levels(self):
        """ContextLogger should support all log levels."""
        from core.core_logging import ContextLogger, JSONFormatter

        logger = ContextLogger("test.levels")
        logger.logger.setLevel(logging.DEBUG)

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        logger.logger.addHandler(handler)

        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")

        lines = stream.getvalue().strip().split('\n')
        assert len(lines) == 5

        levels = [json.loads(line)["level"] for line in lines]
        assert levels == ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class TestPreconfiguredLoggers:
    """Test pre-configured loggers."""

    def test_scan_logger_exists(self):
        """SCAN_LOGGER should exist and be a ContextLogger."""
        from core.core_logging import SCAN_LOGGER, ContextLogger

        assert SCAN_LOGGER is not None
        assert isinstance(SCAN_LOGGER, ContextLogger)

    def test_ai_logger_exists(self):
        """AI_LOGGER should exist."""
        from core.core_logging import AI_LOGGER, ContextLogger

        assert AI_LOGGER is not None
        assert isinstance(AI_LOGGER, ContextLogger)

    def test_trade_logger_exists(self):
        """TRADE_LOGGER should exist."""
        from core.core_logging import TRADE_LOGGER, ContextLogger

        assert TRADE_LOGGER is not None
        assert isinstance(TRADE_LOGGER, ContextLogger)

    def test_bot_logger_exists(self):
        """BOT_LOGGER should exist."""
        from core.core_logging import BOT_LOGGER, ContextLogger

        assert BOT_LOGGER is not None
        assert isinstance(BOT_LOGGER, ContextLogger)

    def test_exchange_logger_exists(self):
        """EXCHANGE_LOGGER should exist."""
        from core.core_logging import EXCHANGE_LOGGER, ContextLogger

        assert EXCHANGE_LOGGER is not None
        assert isinstance(EXCHANGE_LOGGER, ContextLogger)

    def test_learning_logger_exists(self):
        """LEARNING_LOGGER should exist."""
        from core.core_logging import LEARNING_LOGGER, ContextLogger

        assert LEARNING_LOGGER is not None
        assert isinstance(LEARNING_LOGGER, ContextLogger)


class TestHelperFunctions:
    """Test logging helper functions."""

    def test_log_scan_start(self):
        """log_scan_start should log with scan context."""
        from core.core_logging import log_scan_start, SCAN_LOGGER, JSONFormatter

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        SCAN_LOGGER.logger.addHandler(handler)
        SCAN_LOGGER.logger.setLevel(logging.DEBUG)

        log_scan_start(cycle=1, symbols_count=50)

        output = stream.getvalue().strip()
        parsed = json.loads(output)

        assert parsed["message"] == "Scan cycle started"
        assert parsed["cycle"] == 1
        assert parsed["symbols_count"] == 50
        assert parsed["component"] == "scanner"

    def test_log_scan_complete(self):
        """log_scan_complete should log completion details."""
        from core.core_logging import log_scan_complete, SCAN_LOGGER, JSONFormatter

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        SCAN_LOGGER.logger.addHandler(handler)
        SCAN_LOGGER.logger.setLevel(logging.DEBUG)

        log_scan_complete(cycle=1, duration=2.5, signals=5, coins_scanned=100)

        output = stream.getvalue().strip()
        parsed = json.loads(output)

        assert parsed["message"] == "Scan cycle completed"
        assert parsed["cycle"] == 1
        assert parsed["duration_seconds"] == 2.5
        assert parsed["signals_generated"] == 5
        assert parsed["coins_scanned"] == 100

    def test_log_ai_request(self):
        """log_ai_request should log AI request details."""
        from core.core_logging import log_ai_request, AI_LOGGER, JSONFormatter

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        AI_LOGGER.logger.addHandler(handler)
        AI_LOGGER.logger.setLevel(logging.DEBUG)

        log_ai_request(provider="openai", model="gpt-4", duration=1.5, success=True, tokens=150)

        output = stream.getvalue().strip()
        parsed = json.loads(output)

        assert parsed["message"] == "AI request completed"
        assert parsed["provider"] == "openai"
        assert parsed["model"] == "gpt-4"
        assert parsed["duration_seconds"] == 1.5
        assert parsed["success"] is True
        assert parsed["tokens_used"] == 150
        assert parsed["component"] == "ai"

    def test_log_trade_event(self):
        """log_trade_event should log trade events."""
        from core.core_logging import log_trade_event, TRADE_LOGGER, JSONFormatter

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        TRADE_LOGGER.logger.addHandler(handler)
        TRADE_LOGGER.logger.setLevel(logging.DEBUG)

        log_trade_event(
            event="opened",
            symbol="BTCUSDT",
            direction="BUY",
            entry_price=45000,
        )

        output = stream.getvalue().strip()
        parsed = json.loads(output)

        assert parsed["message"] == "Trade opened"
        assert parsed["event"] == "opened"
        assert parsed["symbol"] == "BTCUSDT"
        assert parsed["direction"] == "BUY"
        assert parsed["entry_price"] == 45000
        assert parsed["component"] == "trade"

    def test_log_bot_command(self):
        """log_bot_command should log bot commands."""
        from core.core_logging import log_bot_command, BOT_LOGGER, JSONFormatter

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        BOT_LOGGER.logger.addHandler(handler)
        BOT_LOGGER.logger.setLevel(logging.DEBUG)

        log_bot_command(command="/start", user_id=12345, success=True)

        output = stream.getvalue().strip()
        parsed = json.loads(output)

        assert parsed["message"] == "Bot command"
        assert parsed["command"] == "/start"
        assert parsed["user_id"] == 12345
        assert parsed["success"] is True
        assert parsed["component"] == "bot"

    def test_log_exchange_call(self):
        """log_exchange_call should log exchange API calls."""
        from core.core_logging import log_exchange_call, EXCHANGE_LOGGER, JSONFormatter

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        EXCHANGE_LOGGER.logger.addHandler(handler)
        EXCHANGE_LOGGER.logger.setLevel(logging.DEBUG)

        log_exchange_call(
            exchange="bybit",
            endpoint="/v5/market/kline",
            duration=0.3,
            success=True,
        )

        output = stream.getvalue().strip()
        parsed = json.loads(output)

        assert parsed["message"] == "Exchange API call"
        assert parsed["exchange"] == "bybit"
        assert parsed["endpoint"] == "/v5/market/kline"
        assert parsed["duration_seconds"] == 0.3
        assert parsed["success"] is True
        assert parsed["component"] == "exchange"

    def test_log_learning_event(self):
        """log_learning_event should log learning events."""
        from core.core_logging import log_learning_event, LEARNING_LOGGER, JSONFormatter

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        LEARNING_LOGGER.logger.addHandler(handler)
        LEARNING_LOGGER.logger.setLevel(logging.DEBUG)

        log_learning_event(event="weight_update", strategy="SMC", new_weight=0.85)

        output = stream.getvalue().strip()
        parsed = json.loads(output)

        assert parsed["message"] == "Learning weight_update"
        assert parsed["event"] == "weight_update"
        assert parsed["strategy"] == "SMC"
        assert parsed["new_weight"] == 0.85
        assert parsed["component"] == "learning"


class TestSetupJsonLogging:
    """Test logging setup function."""

    def test_setup_json_logging_creates_handlers(self, tmp_path):
        """setup_json_logging should create file and console handlers."""
        from core.core_logging import setup_json_logging

        log_file = tmp_path / "test.log"
        logger = setup_json_logging(log_level="DEBUG", log_file=str(log_file), console=False)

        assert logger is not None
        assert len(logger.handlers) >= 1
        # Check file handler exists
        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) >= 1

    def test_setup_json_logging_with_console(self, tmp_path):
        """setup_json_logging should support console output."""
        from core.core_logging import setup_json_logging

        log_file = tmp_path / "test.log"
        logger = setup_json_logging(log_level="INFO", log_file=str(log_file), console=True)

        console_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
        assert len(console_handlers) >= 1

    def test_get_context_logger(self):
        """get_context_logger should return ContextLogger."""
        from core.core_logging import get_context_logger, ContextLogger

        logger = get_context_logger("test.module", {"custom": "context"})

        assert isinstance(logger, ContextLogger)
        assert logger.base_context == {"custom": "context"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])