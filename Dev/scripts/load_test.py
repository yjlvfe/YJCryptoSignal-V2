"""
Production Load Testing Framework for CryptoSignal
Tests system components under concurrent load
"""
import asyncio
import time
import threading
import statistics
from typing import Dict, List, Any, Callable
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
import json


@dataclass
class LoadTestResult:
    """Results from a load test"""
    test_name: str
    duration_seconds: float
    total_operations: int
    successful_operations: int
    failed_operations: int
    operations_per_second: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    max_latency_ms: float
    errors: List[str] = field(default_factory=list)


@dataclass
class StressTestConfig:
    """Configuration for stress testing"""
    num_workers: int = 50
    operations_per_worker: int = 100
    ramp_up_seconds: float = 1.0
    target_rps: int = 1000
    timeout_seconds: float = 30.0


class LoadTester:
    """Execute load tests against system components"""

    def __init__(self, config: StressTestConfig = None):
        self.config = config or StressTestConfig()
        self.results: List[LoadTestResult] = []

    def run_load_test(
        self,
        test_name: str,
        operation: Callable,
        *args,
        workers: int = None,
        ops_per_worker: int = None,
        **kwargs
    ) -> LoadTestResult:
        """Run a load test with specified concurrency"""
        workers = workers or self.config.num_workers
        ops_per_worker = ops_per_worker or self.config.operations_per_worker
        total_ops = workers * ops_per_worker

        latencies: List[float] = []
        errors: List[str] = []
        successful = 0
        failed = 0
        start_time = time.perf_counter()

        def worker_task(worker_id: int):
            nonlocal successful, failed
            worker_latencies = []
            worker_errors = []

            for i in range(ops_per_worker):
                op_start = time.perf_counter()
                try:
                    operation(*args, **kwargs)
                    worker_latencies.append((time.perf_counter() - op_start) * 1000)
                    successful += 1
                except Exception as e:
                    failed += 1
                    worker_errors.append(f"Worker {worker_id}, op {i}: {str(e)}")
                    worker_latencies.append((time.perf_counter() - op_start) * 1000)

            latencies.extend(worker_latencies)
            errors.extend(worker_errors)

        # Execute with thread pool
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(worker_task, i) for i in range(workers)]
            for future in as_completed(futures, timeout=self.config.timeout_seconds):
                try:
                    future.result()
                except Exception as e:
                    errors.append(f"Future error: {e}")

        duration = time.perf_counter() - start_time

        if latencies:
            latencies.sort()
            result = LoadTestResult(
                test_name=test_name,
                duration_seconds=duration,
                total_operations=total_ops,
                successful_operations=successful,
                failed_operations=failed,
                operations_per_second=total_ops / duration if duration > 0 else 0,
                avg_latency_ms=statistics.mean(latencies),
                p50_latency_ms=latencies[len(latencies) // 2],
                p95_latency_ms=latencies[int(len(latencies) * 0.95)],
                p99_latency_ms=latencies[int(len(latencies) * 0.99)],
                max_latency_ms=max(latencies),
                errors=errors[:100]  # Limit errors stored
            )
        else:
            result = LoadTestResult(
                test_name=test_name,
                duration_seconds=duration,
                total_operations=total_ops,
                successful_operations=0,
                failed_operations=failed,
                operations_per_second=0,
                avg_latency_ms=0,
                p50_latency_ms=0,
                p95_latency_ms=0,
                p99_latency_ms=0,
                max_latency_ms=0,
                errors=errors
            )

        self.results.append(result)
        return result

    def run_concurrent_mixed_test(
        self,
        test_name: str,
        operations: Dict[str, Callable],
        weights: Dict[str, float] = None,
        total_operations: int = 10000,
        workers: int = 50
    ) -> LoadTestResult:
        """Run mixed workload test with weighted operations"""
        weights = weights or {k: 1.0 for k in operations}
        weight_sum = sum(weights.values())
        op_counts = {k: int(total_operations * v / weight_sum) for k, v in weights.items()}

        latencies: List[float] = []
        errors: List[str] = []
        successful = 0
        failed = 0
        start_time = time.perf_counter()

        def worker_task(worker_id: int):
            nonlocal successful, failed
            for op_name, op_func in operations.items():
                count = op_counts.get(op_name, 0) // workers
                for i in range(count):
                    op_start = time.perf_counter()
                    try:
                        op_func()
                        latencies.append((time.perf_counter() - op_start) * 1000)
                        successful += 1
                    except Exception as e:
                        failed += 1
                        errors.append(f"{op_name}: {e}")
                        latencies.append((time.perf_counter() - op_start) * 1000)

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(worker_task, i) for i in range(workers)]
            for future in as_completed(futures, timeout=self.config.timeout_seconds):
                future.result()

        duration = time.perf_counter() - start_time

        if latencies:
            latencies.sort()
            return LoadTestResult(
                test_name=test_name,
                duration_seconds=duration,
                total_operations=total_operations,
                successful_operations=successful,
                failed_operations=failed,
                operations_per_second=total_operations / duration if duration > 0 else 0,
                avg_latency_ms=statistics.mean(latencies),
                p50_latency_ms=latencies[len(latencies) // 2],
                p95_latency_ms=latencies[int(len(latencies) * 0.95)],
                p99_latency_ms=latencies[int(len(latencies) * 0.99)],
                max_latency_ms=max(latencies),
                errors=errors[:100]
            )
        return LoadTestResult(
            test_name=test_name,
            duration_seconds=duration,
            total_operations=total_operations,
            successful_operations=successful,
            failed_operations=failed,
            operations_per_second=0,
            avg_latency_ms=0,
            p50_latency_ms=0,
            p95_latency_ms=0,
            p99_latency_ms=0,
            max_latency_ms=0,
            errors=errors
        )

    def print_results(self):
        """Print all test results in a formatted table"""
        print("\n" + "=" * 100)
        print(f"{'TEST NAME':<35} {'OPS':>8} {'OK':>8} {'FAIL':>8} {'OPS/s':>10} {'AVG ms':>10} {'P95 ms':>10} {'P99 ms':>10}")
        print("=" * 100)
        for r in self.results:
            print(f"{r.test_name:<35} {r.total_operations:>8} {r.successful_operations:>8} {r.failed_operations:>8} "
                  f"{r.operations_per_second:>10.1f} {r.avg_latency_ms:>10.2f} {r.p95_latency_ms:>10.2f} {r.p99_latency_ms:>10.2f}")
        print("=" * 100)

    def save_results(self, filepath: str):
        """Save results to JSON file"""
        data = [
            {
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
                "error_count": len(r.errors),
                "sample_errors": r.errors[:10]
            }
            for r in self.results
        ]
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)


class AsyncLoadTester:
    """Async load tester for async operations"""

    def __init__(self, config: StressTestConfig = None):
        self.config = config or StressTestConfig()
        self.results: List[LoadTestResult] = []

    async def run_async_load_test(
        self,
        test_name: str,
        async_operation: Callable,
        workers: int = None,
        ops_per_worker: int = None
    ) -> LoadTestResult:
        """Run async load test"""
        workers = workers or self.config.num_workers
        ops_per_worker = ops_per_worker or self.config.operations_per_worker
        total_ops = workers * ops_per_worker

        latencies: List[float] = []
        errors: List[str] = []
        successful = 0
        failed = 0
        start_time = time.perf_counter()

        async def worker_task(worker_id: int):
            nonlocal successful, failed
            for i in range(ops_per_worker):
                op_start = time.perf_counter()
                try:
                    await async_operation()
                    latencies.append((time.perf_counter() - op_start) * 1000)
                    successful += 1
                except Exception as e:
                    failed += 1
                    errors.append(f"Worker {worker_id}, op {i}: {str(e)}")
                    latencies.append((time.perf_counter() - op_start) * 1000)

        # Run all workers concurrently
        tasks = [worker_task(i) for i in range(workers)]
        await asyncio.gather(*tasks, return_exceptions=True)

        duration = time.perf_counter() - start_time

        if latencies:
            latencies.sort()
            result = LoadTestResult(
                test_name=test_name,
                duration_seconds=duration,
                total_operations=total_ops,
                successful_operations=successful,
                failed_operations=failed,
                operations_per_second=total_ops / duration if duration > 0 else 0,
                avg_latency_ms=statistics.mean(latencies),
                p50_latency_ms=latencies[len(latencies) // 2],
                p95_latency_ms=latencies[int(len(latencies) * 0.95)],
                p99_latency_ms=latencies[int(len(latencies) * 0.99)],
                max_latency_ms=max(latencies),
                errors=errors[:100]
            )
        else:
            result = LoadTestResult(
                test_name=test_name,
                duration_seconds=duration,
                total_operations=total_ops,
                successful_operations=successful,
                failed_operations=failed,
                operations_per_second=0,
                avg_latency_ms=0,
                p50_latency_ms=0,
                p95_latency_ms=0,
                p99_latency_ms=0,
                max_latency_ms=0,
                errors=errors
            )

        self.results.append(result)
        return result


@contextmanager
def measure_latency():
    """Context manager to measure operation latency"""
    start = time.perf_counter()
    yield lambda: (time.perf_counter() - start) * 1000


if __name__ == "__main__":
    # Demo usage
    print("Load Testing Framework - Ready for use")

    # Example: test counter increment
    from core.core_metrics import get_registry
    registry = get_registry()
    counter = registry.counter("load_test_counter")

    tester = LoadTester(StressTestConfig(num_workers=20, operations_per_worker=500))
    result = tester.run_load_test("counter_increment", counter.inc)
    print(f"Result: {result.operations_per_second:.0f} ops/s, p95: {result.p95_latency_ms:.2f}ms")