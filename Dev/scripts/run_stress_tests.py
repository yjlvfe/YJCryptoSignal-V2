#!/usr/bin/env python3
"""
CryptoSignal Stress Test Runner
Executes comprehensive load and stress tests
"""
import sys
import os
import asyncio
import time
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.load_test import (
    LoadTester, StressTestConfig, AsyncLoadTester
)
from scripts.chaos_engineering import (
    ChaosEngine, create_standard_experiments, ChaosExperimentRunner
)


def run_metrics_load_tests():
    """Run load tests on metrics system"""
    print("\n" + "="*60)
    print("METRICS LOAD TESTS")
    print("="*60)

    config = StressTestConfig(num_workers=50, operations_per_worker=200)
    tester = LoadTester(config)

    from core.core_metrics import get_registry, Counter, Gauge, Histogram
    registry = get_registry()

    # Test 1: Counter increment
    counter = registry.counter("stress_test_counter")
    result = tester.run_load_test("counter_increment", counter.inc)
    print(f"Counter Inc: {result.operations_per_second:,.0f} ops/s, p99: {result.p99_latency_ms:.2f}ms")

    # Test 2: Gauge set
    gauge = registry.gauge("stress_test_gauge")
    result = tester.run_load_test("gauge_set", gauge.set, 42.0)
    print(f"Gauge Set: {result.operations_per_second:,.0f} ops/s, p99: {result.p99_latency_ms:.2f}ms")

    # Test 3: Histogram observe
    hist = registry.histogram("stress_test_hist")
    import random
    result = tester.run_load_test("histogram_observe", hist.observe, random.random())
    print(f"Histogram Observe: {result.operations_per_second:,.0f} ops/s, p99: {result.p99_latency_ms:.2f}ms")

    # Test 4: Mixed metrics workload
    def mixed_metrics():
        counter.inc()
        gauge.set(random.random() * 100)
        hist.observe(random.random())
        gauge.inc(0.1)

    result = tester.run_load_test("mixed_metrics", mixed_metrics, workers=30, ops_per_worker=200)
    print(f"Mixed Metrics: {result.operations_per_second:,.0f} ops/s, p99: {result.p99_latency_ms:.2f}ms")

    # Test 5: Helper functions
    from core.core_metrics import record_scan_cycle, record_ai_call, record_trade_opened, record_trade_closed

    def record_scan():
        record_scan_cycle(100, 5, 2.5)

    result = tester.run_load_test("record_scan_cycle", record_scan, workers=20, ops_per_worker=100)
    print(f"Record Scan: {result.operations_per_second:,.0f} ops/s, p99: {result.p99_latency_ms:.2f}ms")

    def record_ai():
        record_ai_call("openai", "gpt-4", 1.5, True, 150)

    result = tester.run_load_test("record_ai_call", record_ai, workers=20, ops_per_worker=100)
    print(f"Record AI: {result.operations_per_second:,.0f} ops/s, p99: {result.p99_latency_ms:.2f}ms")

    def record_trade():
        record_trade_opened("BUY")
        record_trade_closed("TP1", 2.5, 3.0)

    result = tester.run_load_test("record_trade", record_trade, workers=20, ops_per_worker=100)
    print(f"Record Trade: {result.operations_per_second:,.0f} ops/s, p99: {result.p99_latency_ms:.2f}ms")

    return tester.results


def run_logging_load_tests():
    """Run load tests on logging system"""
    print("\n" + "="*60)
    print("LOGGING LOAD TESTS")
    print("="*60)

    config = StressTestConfig(num_workers=20, operations_per_worker=200)
    tester = LoadTester(config)

    from core.core_logging import (
        log_scan_start, log_ai_request, log_trade_event,
        log_bot_command, log_exchange_call, log_learning_event,
        SCAN_LOGGER, AI_LOGGER, TRADE_LOGGER, BOT_LOGGER,
        EXCHANGE_LOGGER, LEARNING_LOGGER
    )

    # Disable console output for load test
    for logger in [SCAN_LOGGER, AI_LOGGER, TRADE_LOGGER, BOT_LOGGER, EXCHANGE_LOGGER, LEARNING_LOGGER]:
        logger.logger.handlers.clear()

    import logging
    from io import StringIO
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    for logger in [SCAN_LOGGER, AI_LOGGER, TRADE_LOGGER, BOT_LOGGER, EXCHANGE_LOGGER, LEARNING_LOGGER]:
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.DEBUG)

    # Test 1: Scan logging
    result = tester.run_load_test("log_scan", log_scan_start, cycle=1, symbols_count=100, workers=10, ops_per_worker=100)
    print(f"Log Scan: {result.operations_per_second:,.0f} ops/s, p99: {result.p99_latency_ms:.2f}ms")

    # Test 2: AI logging
    result = tester.run_load_test("log_ai", log_ai_request, provider="openai", model="gpt-4", duration=1.5, success=True, tokens=150, workers=10, ops_per_worker=100)
    print(f"Log AI: {result.operations_per_second:,.0f} ops/s, p99: {result.p99_latency_ms:.2f}ms")

    # Test 3: Trade logging
    result = tester.run_load_test("log_trade", log_trade_event, event="opened", symbol="BTCUSDT", direction="BUY", entry=45000, workers=10, ops_per_worker=100)
    print(f"Log Trade: {result.operations_per_second:,.0f} ops/s, p99: {result.p99_latency_ms:.2f}ms")

    return tester.results


def run_alerting_load_tests():
    """Run load tests on alerting system"""
    print("\n" + "="*60)
    print("ALERTING LOAD TESTS")
    print("="*60)

    config = StressTestConfig(num_workers=10, operations_per_worker=50)
    tester = LoadTester(config)

    from utils.alerting import AlertManager, WebhookConfig, Alert, AlertLevel, get_alert_manager
    import time

    manager = AlertManager()
    config_w = WebhookConfig(name='test', url='https://httpbin.org/post', retry_count=1, timeout=5)
    manager.add_webhook(config_w)

    # Test alert sending (will fail on network but measures local overhead)
    def send_alert():
        alert = Alert(
            title="Test Alert",
            message="Load test alert",
            level=AlertLevel.INFO,
            source="loadtest",
            tags={"test": "true"}
        )
        # Use sync version for load test
        manager.send_alert(alert)

    result = tester.run_load_test("send_alert", send_alert, workers=5, ops_per_worker=20)
    print(f"Send Alert: {result.operations_per_second:,.0f} ops/s, p99: {result.p99_latency_ms:.2f}ms")

    return tester.results


async def run_async_load_tests():
    """Run async load tests"""
    print("\n" + "="*60)
    print("ASYNC LOAD TESTS")
    print("="*60)

    config = StressTestConfig(num_workers=50, operations_per_worker=100)
    tester = AsyncLoadTester(config)

    from core.core_metrics import get_registry
    registry = get_registry()
    counter = registry.counter("async_stress_counter")

    async def async_increment():
        counter.inc()

    result = await tester.run_async_load_test("async_counter_inc", async_increment)
    print(f"Async Counter: {result.operations_per_second:,.0f} ops/s, p99: {result.p99_latency_ms:.2f}ms")

    return tester.results


def run_chaos_experiments():
    """Run chaos engineering experiments"""
    print("\n" + "="*60)
    print("CHAOS ENGINEERING EXPERIMENTS")
    print("="*60)

    engine = ChaosEngine()

    # Register a subset of experiments that are safe to run
    safe_experiments = [
        exp for exp in create_standard_experiments()
        if exp.chaos_type.value in [
            "ai_latency_spike", "exchange_latency", "cpu_spike"
        ]
    ]

    for exp in safe_experiments:
        # Reduce intensity for safety
        exp.intensity = min(exp.intensity, 0.3)
        exp.duration_seconds = min(exp.duration_seconds, 3)
        engine.register_experiment(exp)

    print(f"Running {len(safe_experiments)} chaos experiments...")
    results = engine.run_all_experiments()

    passed = sum(1 for r in results if r.success)
    print(f"Results: {passed}/{len(results)} passed")

    print(engine.generate_report())
    return results


def main():
    """Main stress test runner"""
    print("🚀 CRYPTOSIGNAL v3.0 — STRESS TEST SUITE")
    print("="*60)

    all_results = []

    try:
        # Run synchronous load tests
        all_results.extend(run_metrics_load_tests())
        print()

        all_results.extend(run_logging_load_tests())
        print()

        all_results.extend(run_alerting_load_tests())
        print()

        # Run async load tests
        async_results = asyncio.run(run_async_load_tests())
        all_results.extend(async_results)
        print()

        # Run chaos experiments (optional - can be slow)
        import os
        if os.getenv("RUN_CHAOS", "false").lower() == "true":
            chaos_results = run_chaos_experiments()
            all_results.extend(chaos_results)
            print()

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    # Summary
    print("\n" + "="*60)
    print("STRESS TEST SUMMARY")
    print("="*60)

    for r in all_results:
        if hasattr(r, 'operations_per_second'):
            status = "✅" if r.successful_operations == r.total_operations else "⚠️"
            print(f"{status} {r.test_name:<30} {r.operations_per_second:>10,.0f} ops/s  p99: {r.p99_latency_ms:>7.2f}ms  fail: {r.failed_operations}")

    # Save results
    output_file = Path(__file__).parent.parent / "stress_test_results.json"
    data = []
    for r in all_results:
        if hasattr(r, 'test_name'):
            data.append({
                "test_name": r.test_name,
                "duration_seconds": r.duration_seconds,
                "total_operations": r.total_operations,
                "successful_operations": r.successful_operations,
                "failed_operations": r.failed_operations,
                "operations_per_second": r.operations_per_second,
                "avg_latency_ms": r.avg_latency_ms,
                "p50_latency_ms": r.p50_latency_ms,
                "p95_latency_ms": r.p95_latency_ms,
                "p99_latency_ms": r.p99_latency_ms,
                "max_latency_ms": r.max_latency_ms,
                "error_count": len(r.errors)
            })

    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\n📄 Results saved to: {output_file}")

    # Overall assessment
    total_ops = sum(r.operations_per_second for r in all_results if hasattr(r, 'operations_per_second'))
    print(f"\n📊 Aggregate Throughput: {total_ops:,.0f} ops/s")

    if total_ops > 50000:
        print("🎉 EXCELLENT - System handles high load well")
    elif total_ops > 20000:
        print("✅ GOOD - System meets production requirements")
    elif total_ops > 10000:
        print("⚠️  ACCEPTABLE - May need optimization for peak loads")
    else:
        print("❌ NEEDS OPTIMIZATION - Below production threshold")


if __name__ == "__main__":
    main()