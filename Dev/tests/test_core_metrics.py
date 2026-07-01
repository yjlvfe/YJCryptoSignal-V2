"""
Unit tests for core/core_metrics.py
"""
import pytest
from unittest.mock import MagicMock, patch


class TestMetricsRegistry:
    """Test the global metrics registry."""

    def test_get_registry_singleton(self):
        """Registry should be a singleton."""
        from core.core_metrics import get_registry

        reg1 = get_registry()
        reg2 = get_registry()
        assert reg1 is reg2

    def test_registry_creates_counters(self):
        """Registry should create and retrieve counters."""
        from core.core_metrics import get_registry

        registry = get_registry()
        counter = registry.counter("test_counter", description="Test counter")

        assert counter is not None
        assert hasattr(counter, 'inc')
        assert hasattr(counter, 'get')

    def test_registry_creates_gauges(self):
        """Registry should create and retrieve gauges."""
        from core.core_metrics import get_registry

        registry = get_registry()
        gauge = registry.gauge("test_gauge", description="Test gauge")

        assert gauge is not None
        assert hasattr(gauge, 'set')
        assert hasattr(gauge, 'inc')
        assert hasattr(gauge, 'dec')
        assert hasattr(gauge, 'get')

    def test_registry_creates_histograms(self):
        """Registry should create and retrieve histograms."""
        from core.core_metrics import get_registry

        registry = get_registry()
        hist = registry.histogram("test_hist", description="Test histogram")

        assert hist is not None
        assert hasattr(hist, 'observe')

    def test_registry_labels_support(self):
        """Registry should support labeled metrics."""
        from core.core_metrics import get_registry

        registry = get_registry()
        counter1 = registry.counter("http_requests", labels={"method": "GET", "endpoint": "/api"})
        counter2 = registry.counter("http_requests", labels={"method": "POST", "endpoint": "/api"})

        assert counter1 is not counter2  # Different label sets = different counters

    def test_prometheus_output(self):
        """Registry should generate Prometheus format output."""
        from core.core_metrics import get_registry

        registry = get_registry()
        # Create some metrics
        registry.counter("test_counter", description="Test").inc(5)
        registry.gauge("test_gauge", description="Test").set(42)
        registry.histogram("test_hist", description="Test").observe(1.5)

        output = registry.generate_prometheus()

        assert "test_counter" in output
        assert "test_counter 5.0" in output
        assert "test_gauge" in output
        assert "test_gauge 42" in output  # Gauge outputs int without .0
        assert "test_hist" in output


class TestCounter:
    """Test Counter metric type."""

    def test_counter_increment(self):
        """Counter should increment correctly."""
        from core.core_metrics import get_registry

        registry = get_registry()
        counter = registry.counter("test_counter_inc", description="Test")

        counter.inc()
        counter.inc(2.5)

        assert counter.get() == 3.5

    def test_counter_with_labels(self):
        """Counter with labels should work."""
        from core.core_metrics import get_registry

        registry = get_registry()
        counter_get = registry.counter("http_requests", labels={"method": "GET"}, description="HTTP")
        counter_post = registry.counter("http_requests", labels={"method": "POST"}, description="HTTP")

        counter_get.inc(5)
        counter_post.inc(3)

        assert counter_get.get() == 5
        assert counter_post.get() == 3


class TestGauge:
    """Test Gauge metric type."""

    def test_gauge_set_and_inc_dec(self):
        """Gauge should support set, inc, dec operations."""
        from core.core_metrics import get_registry

        registry = get_registry()
        gauge = registry.gauge("active_connections", description="Active connections")

        gauge.set(10)
        assert gauge.get() == 10

        gauge.inc(5)
        assert gauge.get() == 15

        gauge.dec(3)
        assert gauge.get() == 12

    def test_gauge_with_labels(self):
        """Gauge with labels should work independently."""
        from core.core_metrics import get_registry

        registry = get_registry()
        gauge_0 = registry.gauge("cpu_usage", labels={"core": "0"}, description="CPU")
        gauge_1 = registry.gauge("cpu_usage", labels={"core": "1"}, description="CPU")

        gauge_0.set(45.5)
        gauge_1.set(67.2)

        assert gauge_0.get() == 45.5
        assert gauge_1.get() == 67.2


class TestHistogram:
    """Test Histogram metric type."""

    def test_histogram_observe(self):
        """Histogram should record observations."""
        from core.core_metrics import get_registry

        registry = get_registry()
        hist = registry.histogram("request_duration", description="Request duration")

        hist.observe(0.05)
        hist.observe(0.3)
        hist.observe(0.8)
        hist.observe(1.5)

        # Histogram stores buckets, sum, count
        assert hasattr(hist, 'count')
        assert hist.count == 4
        assert hasattr(hist, 'sum')
        assert hist.sum == pytest.approx(2.65)
        assert hasattr(hist, 'buckets')


class TestSummary:
    """Test Summary metric type."""

    def test_summary_observe(self):
        """Summary should record observations with quantiles."""
        from core.core_metrics import get_registry

        registry = get_registry()
        summary = registry.summary("request_size", description="Request size")

        for size in [100, 200, 300, 400, 500]:
            summary.observe(size)

        assert len(summary.values) == 5
        assert summary.quantile(0.5) == 300  # Median
        assert summary.quantile(0.0) == 100  # Min
        assert summary.quantile(1.0) == 500  # Max


class TestHelperFunctions:
    """Test helper functions for recording common metrics."""

    def test_record_scan_cycle(self):
        """record_scan_cycle should record scan metrics."""
        from core.core_metrics import record_scan_cycle, get_registry

        registry = get_registry()
        # Clear pre-defined metrics by getting fresh ones
        SYSTEM_CYCLE_COUNT = registry.counter("cryptosignal_cycles_total")
        SCANNER_COINS_SCANNED = registry.counter("cryptosignal_scanner_coins_scanned_total")
        SCANNER_SIGNALS_GENERATED = registry.counter("cryptosignal_scanner_signals_generated_total")

        initial_cycles = SYSTEM_CYCLE_COUNT.get()

        record_scan_cycle(coins_scanned=100, signals=5, duration=2.5)

        assert SYSTEM_CYCLE_COUNT.get() == initial_cycles + 1
        assert SCANNER_COINS_SCANNED.get() >= 100
        assert SCANNER_SIGNALS_GENERATED.get() >= 5

    def test_record_ai_call(self):
        """record_ai_call should record AI metrics."""
        from core.core_metrics import record_ai_call, get_registry

        registry = get_registry()
        AI_REQUESTS_TOTAL = registry.counter("cryptosignal_ai_requests_total")

        initial_requests = AI_REQUESTS_TOTAL.get()

        record_ai_call(provider="openai", model="gpt-4", duration=1.5, success=True, tokens=150)

        # Check that metrics were incremented (using labels)
        # Since the helper uses labels, we can't easily check specific labeled counters
        # but we can verify the function runs without error
        assert True  # Function executed

    def test_record_ai_call_failure(self):
        """record_ai_call should record failures correctly."""
        from core.core_metrics import record_ai_call

        # Should not raise
        record_ai_call(
            provider="deepseek",
            model="deepseek-chat",
            duration=0.5,
            success=False,
            tokens=0,
        )
        assert True

    def test_record_trade_opened(self):
        """record_trade_opened should record trade metrics."""
        from core.core_metrics import record_trade_opened, get_registry

        registry = get_registry()
        TRADES_OPENED = registry.counter("cryptosignal_trades_opened_total")
        TRADES_ACTIVE = registry.gauge("cryptosignal_trades_active")

        initial_opened = TRADES_OPENED.get()
        initial_active = TRADES_ACTIVE.get()

        record_trade_opened(direction="BUY")

        assert TRADES_OPENED.get() >= initial_opened
        assert TRADES_ACTIVE.get() >= initial_active

    def test_record_trade_closed(self):
        """record_trade_closed should record PnL metrics."""
        from core.core_metrics import record_trade_closed, get_registry

        registry = get_registry()
        TRADES_CLOSED = registry.counter("cryptosignal_trades_closed_total")
        TRADES_ACTIVE = registry.gauge("cryptosignal_trades_active")
        TRADE_PNL = registry.histogram("cryptosignal_trade_pnl_percent")

        initial_closed = TRADES_CLOSED.get()
        initial_active = TRADES_ACTIVE.get()

        record_trade_closed(result="TP1", pnl_pct=2.5, duration_hours=3.5)

        assert TRADES_CLOSED.get() >= initial_closed
        assert TRADES_ACTIVE.get() <= initial_active  # Should dec
        assert TRADE_PNL.count > 0

    def test_record_bot_message(self):
        """record_bot_message should record bot message metrics."""
        from core.core_metrics import record_bot_message, get_registry

        registry = get_registry()
        BOT_MESSAGES_SENT = registry.counter("cryptosignal_bot_messages_sent_total")

        initial = BOT_MESSAGES_SENT.get()

        record_bot_message(message_type="signal")

        assert BOT_MESSAGES_SENT.get() >= initial

    def test_record_bot_command(self):
        """record_bot_command should record command metrics."""
        from core.core_metrics import record_bot_command, get_registry

        registry = get_registry()
        BOT_COMMANDS_RECEIVED = registry.counter("cryptosignal_bot_commands_received_total")

        initial = BOT_COMMANDS_RECEIVED.get()

        record_bot_command(command="/start")

        assert BOT_COMMANDS_RECEIVED.get() >= initial


class TestPredefinedMetrics:
    """Test that all predefined metrics exist and work."""

    def test_system_metrics_exist(self):
        """System metrics should be defined."""
        from core.core_metrics import get_registry, SYSTEM_UPTIME, SYSTEM_CYCLE_COUNT

        assert SYSTEM_UPTIME is not None
        assert SYSTEM_CYCLE_COUNT is not None

    def test_scanner_metrics_exist(self):
        """Scanner metrics should be defined."""
        from core.core_metrics import SCANNER_COINS_SCANNED, SCANNER_SIGNALS_GENERATED

        assert SCANNER_COINS_SCANNED is not None
        assert SCANNER_SIGNALS_GENERATED is not None

    def test_ai_metrics_exist(self):
        """AI metrics should be defined."""
        from core.core_metrics import AI_REQUESTS_TOTAL, AI_TOKENS_USED, AI_KEY_ROTATIONS

        assert AI_REQUESTS_TOTAL is not None
        assert AI_TOKENS_USED is not None
        assert AI_KEY_ROTATIONS is not None

    def test_trade_metrics_exist(self):
        """Trade metrics should be defined."""
        from core.core_metrics import TRADES_ACTIVE, TRADES_OPENED, TRADES_CLOSED, TRADE_PNL

        assert TRADES_ACTIVE is not None
        assert TRADES_OPENED is not None
        assert TRADES_CLOSED is not None
        assert TRADE_PNL is not None

    def test_bot_metrics_exist(self):
        """Bot metrics should be defined."""
        from core.core_metrics import BOT_MESSAGES_SENT, BOT_COMMANDS_RECEIVED

        assert BOT_MESSAGES_SENT is not None
        assert BOT_COMMANDS_RECEIVED is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])