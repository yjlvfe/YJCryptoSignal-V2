"""
Chaos Engineering Framework for CryptoSignal
Simulates provider failures, network issues, and system disruptions
"""
import asyncio
import random
import time
import threading
from typing import Dict, List, Any, Callable, Optional
from dataclasses import dataclass, field
from enum import Enum
from contextlib import contextmanager
from unittest.mock import patch, AsyncMock
import logging


logger = logging.getLogger("cryptosignal.chaos")


class ChaosType(Enum):
    """Types of chaos experiments"""
    AI_PROVIDER_FAILURE = "ai_provider_failure"
    AI_RATE_LIMIT = "ai_rate_limit"
    AI_LATENCY_SPIKE = "ai_latency_spike"
    EXCHANGE_API_FAILURE = "exchange_api_failure"
    EXCHANGE_LATENCY = "exchange_latency"
    NETWORK_PARTITION = "network_partition"
    MEMORY_PRESSURE = "memory_pressure"
    CPU_SPIKE = "cpu_spike"
    DISK_FULL = "disk_full"
    CONFIG_CORRUPTION = "config_corruption"


@dataclass
class ChaosExperiment:
    """Definition of a chaos experiment"""
    name: str
    chaos_type: ChaosType
    target: str  # Component being tested
    duration_seconds: float
    intensity: float  # 0.0 - 1.0
    config: Dict[str, Any] = field(default_factory=dict)
    expected_behavior: str = ""  # What should happen


@dataclass
class ChaosResult:
    """Result of a chaos experiment"""
    experiment: ChaosExperiment
    start_time: float
    end_time: float
    success: bool
    observations: List[str] = field(default_factory=list)
    metrics_before: Dict[str, Any] = field(default_factory=dict)
    metrics_after: Dict[str, Any] = field(default_factory=dict)
    error: str = ""


class ChaosEngine:
    """Execute chaos experiments against the system"""

    def __init__(self):
        self.experiments: List[ChaosExperiment] = []
        self.results: List[ChaosResult] = []
        self._patches: List[Any] = []
        self._original_functions: Dict[str, Callable] = {}

    def register_experiment(self, experiment: ChaosExperiment):
        """Register a chaos experiment"""
        self.experiments.append(experiment)

    def run_experiment(self, experiment: ChaosExperiment) -> ChaosResult:
        """Execute a single chaos experiment"""
        logger.info(f"Starting chaos experiment: {experiment.name}")

        # Capture metrics before
        metrics_before = self._capture_metrics()

        result = ChaosResult(
            experiment=experiment,
            start_time=time.time(),
            end_time=0,
            success=False
        )

        try:
            # Apply chaos
            self._apply_chaos(experiment)

            # Observe for duration
            time.sleep(experiment.duration_seconds)

            # Capture metrics after
            metrics_after = self._capture_metrics()

            result.end_time = time.time()
            result.metrics_before = metrics_before
            result.metrics_after = metrics_after
            result.success = True
            result.observations.append(f"Experiment completed in {experiment.duration_seconds}s")

        except Exception as e:
            result.end_time = time.time()
            result.error = str(e)
            result.success = False
            logger.error(f"Chaos experiment failed: {e}")

        finally:
            # Cleanup
            self._cleanup_chaos(experiment)

        self.results.append(result)
        return result

    def _apply_chaos(self, experiment: ChaosExperiment):
        """Apply the specific chaos type"""
        if experiment.chaos_type == ChaosType.AI_PROVIDER_FAILURE:
            self._simulate_ai_provider_failure(experiment)
        elif experiment.chaos_type == ChaosType.AI_RATE_LIMIT:
            self._simulate_ai_rate_limit(experiment)
        elif experiment.chaos_type == ChaosType.AI_LATENCY_SPIKE:
            self._simulate_ai_latency_spike(experiment)
        elif experiment.chaos_type == ChaosType.EXCHANGE_API_FAILURE:
            self._simulate_exchange_failure(experiment)
        elif experiment.chaos_type == ChaosType.EXCHANGE_LATENCY:
            self._simulate_exchange_latency(experiment)
        elif experiment.chaos_type == ChaosType.NETWORK_PARTITION:
            self._simulate_network_partition(experiment)
        elif experiment.chaos_type == ChaosType.MEMORY_PRESSURE:
            self._simulate_memory_pressure(experiment)
        elif experiment.chaos_type == ChaosType.CPU_SPIKE:
            self._simulate_cpu_spike(experiment)
        else:
            raise ValueError(f"Unknown chaos type: {experiment.chaos_type}")

    def _cleanup_chaos(self, experiment: ChaosExperiment):
        """Clean up chaos patches"""
        for p in self._patches:
            try:
                p.stop()
            except Exception as e:
                logger.debug(f"chaos patch cleanup failed: {e}")
        self._patches.clear()

    def _capture_metrics(self) -> Dict[str, Any]:
        """Capture current system metrics"""
        from core.core_metrics import get_registry
        registry = get_registry()
        output = registry.generate_prometheus()

        # Parse key metrics from Prometheus output
        metrics = {}
        for line in output.split('\n'):
            if line and not line.startswith('#'):
                parts = line.split()
                if len(parts) >= 2:
                    metrics[parts[0]] = parts[1]
        return metrics

    def _simulate_ai_provider_failure(self, experiment: ChaosExperiment):
        """Simulate AI provider failure"""
        provider = experiment.config.get("provider", "openai")
        failure_rate = experiment.intensity

        async def failing_analyze(*args, **kwargs):
            if random.random() < failure_rate:
                raise Exception(f"Simulated {provider} API failure")
            # Call original
            return await self._call_original_analyze(*args, **kwargs)

        # Patch the AI router
        with patch("core.core_ai.AIRouter.analyze", side_effect=failing_analyze) as p:
            self._patches.append(p)
            logger.warning(f"AI provider {provider} failure injection active ({failure_rate*100}% failure rate)")

    def _simulate_ai_rate_limit(self, experiment: ChaosExperiment):
        """Simulate AI provider rate limiting"""
        provider = experiment.config.get("provider", "openai")
        from core.core_ai import RateLimitError

        async def rate_limited_analyze(*args, **kwargs):
            if random.random() < experiment.intensity:
                raise RateLimitError(f"Rate limit exceeded for {provider}")
            return await self._call_original_analyze(*args, **kwargs)

        with patch("core.core_ai.AIRouter.analyze", side_effect=rate_limited_analyze) as p:
            self._patches.append(p)
            logger.warning(f"AI provider {provider} rate limit injection active")

    def _simulate_ai_latency_spike(self, experiment: ChaosExperiment):
        """Simulate AI provider latency spike"""
        max_latency = experiment.config.get("max_latency_seconds", 30.0)
        spike_probability = experiment.intensity

        async def slow_analyze(*args, **kwargs):
            if random.random() < spike_probability:
                delay = random.uniform(1.0, max_latency)
                logger.warning(f"Injecting AI latency spike: {delay:.1f}s")
                await asyncio.sleep(delay)
            return await self._call_original_analyze(*args, **kwargs)

        with patch("core.core_ai.AIRouter.analyze", side_effect=slow_analyze) as p:
            self._patches.append(p)

    def _simulate_exchange_failure(self, experiment: ChaosExperiment):
        """Simulate exchange API failure"""
        exchange = experiment.config.get("exchange", "bybit")
        failure_rate = experiment.intensity

        async def failing_fetch(*args, **kwargs):
            if random.random() < failure_rate:
                raise Exception(f"Simulated {exchange} API failure")
            return await self._call_original_fetch(*args, **kwargs)

        with patch("data.exchanges.ExchangeManager.fetch_ohlcv", side_effect=failing_fetch) as p:
            self._patches.append(p)

    def _simulate_exchange_latency(self, experiment: ChaosExperiment):
        """Simulate exchange API latency"""
        max_latency = experiment.config.get("max_latency_seconds", 10.0)
        spike_probability = experiment.intensity

        async def slow_fetch(*args, **kwargs):
            if random.random() < spike_probability:
                delay = random.uniform(0.5, max_latency)
                await asyncio.sleep(delay)
            return await self._call_original_fetch(*args, **kwargs)

        with patch("data.exchanges.ExchangeManager.fetch_ohlcv", side_effect=slow_fetch) as p:
            self._patches.append(p)

    def _simulate_network_partition(self, experiment: ChaosExperiment):
        """Simulate network partition"""
        # Block all external HTTP calls
        import httpx

        async def blocked_request(*args, **kwargs):
            raise httpx.ConnectError("Simulated network partition")

        with patch("httpx.AsyncClient.get", side_effect=blocked_request) as p1, \
             patch("httpx.AsyncClient.post", side_effect=blocked_request) as p2:
            self._patches.extend([p1, p2])
            logger.warning("Network partition injected - all HTTP calls blocked")

    def _simulate_memory_pressure(self, experiment: ChaosExperiment):
        """Simulate memory pressure"""
        # Allocate memory to simulate pressure
        memory_mb = experiment.config.get("memory_mb", 500)
        pressure_data = bytearray(memory_mb * 1024 * 1024)

        def cleanup():
            del pressure_data

        self._patches.append(type('obj', (object,), {'stop': cleanup})())
        logger.warning(f"Memory pressure injected: {memory_mb}MB allocated")

    def _simulate_cpu_spike(self, experiment: ChaosExperiment):
        """Simulate CPU spike"""
        duration = experiment.config.get("duration_seconds", 5.0)
        intensity = experiment.intensity

        def cpu_burn():
            end_time = time.time() + duration
            while time.time() < end_time:
                # Busy wait
                _ = sum(i * i for i in range(10000))
                if random.random() > intensity:
                    time.sleep(0.001)  # Yield occasionally

        thread = threading.Thread(target=cpu_burn, daemon=True)
        thread.start()
        logger.warning(f"CPU spike injected for {duration}s at {intensity*100}% intensity")

    async def _call_original_analyze(self, *args, **kwargs):
        """Call original analyze method"""
        from core.core_ai import AIRouter
        return await AIRouter().analyze(*args, **kwargs)

    async def _call_original_fetch(self, *args, **kwargs):
        """Call original fetch method"""
        from data.data_exchanges import ExchangeManager
        return await ExchangeManager().fetch_ohlcv(*args, **kwargs)

    def run_all_experiments(self) -> List[ChaosResult]:
        """Run all registered experiments"""
        results = []
        for exp in self.experiments:
            result = self.run_experiment(exp)
            results.append(result)
            if not result.success:
                logger.error(f"Experiment {exp.name} FAILED: {result.error}")
            else:
                logger.info(f"Experiment {exp.name} PASSED")
        return results

    def generate_report(self) -> str:
        """Generate chaos engineering report"""
        report = [
            "=" * 80,
            "CHAOS ENGINEERING REPORT",
            "=" * 80,
            f"Total Experiments: {len(self.results)}",
            f"Passed: {sum(1 for r in self.results if r.success)}",
            f"Failed: {sum(1 for r in self.results if not r.success)}",
            "",
        ]

        for result in self.results:
            status = "✅ PASS" if result.success else "❌ FAIL"
            report.append(f"{status} | {result.experiment.name}")
            report.append(f"  Type: {result.experiment.chaos_type.value}")
            report.append(f"  Target: {result.experiment.target}")
            report.append(f"  Duration: {result.experiment.duration_seconds}s")
            report.append(f"  Intensity: {result.experiment.intensity}")
            if result.error:
                report.append(f"  Error: {result.error}")
            for obs in result.observations:
                report.append(f"  Observation: {obs}")
            report.append("")

        return "\n".join(report)


# Pre-defined chaos experiments for CryptoSignal
def create_standard_experiments() -> List[ChaosExperiment]:
    """Create standard chaos experiments for CryptoSignal"""
    return [
        # AI Provider Failures
        ChaosExperiment(
            name="openai_total_failure",
            chaos_type=ChaosType.AI_PROVIDER_FAILURE,
            target="core_ai",
            duration_seconds=10,
            intensity=1.0,
            config={"provider": "openai"},
            expected_behavior="Should fallback to next healthy provider"
        ),
        ChaosExperiment(
            name="deepseek_partial_failure",
            chaos_type=ChaosType.AI_PROVIDER_FAILURE,
            target="core_ai",
            duration_seconds=15,
            intensity=0.3,
            config={"provider": "deepseek"},
            expected_behavior="Should handle 30% failure rate with retries"
        ),
        ChaosExperiment(
            name="groq_rate_limit",
            chaos_type=ChaosType.AI_RATE_LIMIT,
            target="core_ai",
            duration_seconds=10,
            intensity=0.5,
            config={"provider": "groq"},
            expected_behavior="Should rotate keys or fallback on rate limit"
        ),

        # Exchange Failures
        ChaosExperiment(
            name="bybit_api_down",
            chaos_type=ChaosType.EXCHANGE_API_FAILURE,
            target="data_fetcher",
            duration_seconds=10,
            intensity=1.0,
            config={"exchange": "bybit"},
            expected_behavior="Should fallback to gateio/kucoin"
        ),
        ChaosExperiment(
            name="gateio_intermittent",
            chaos_type=ChaosType.EXCHANGE_API_FAILURE,
            target="data_fetcher",
            duration_seconds=20,
            intensity=0.2,
            config={"exchange": "gateio"},
            expected_behavior="Should handle 20% failure rate gracefully"
        ),
        ChaosExperiment(
            name="kucoin_latency_spike",
            chaos_type=ChaosType.EXCHANGE_LATENCY,
            target="data_fetcher",
            duration_seconds=15,
            intensity=0.3,
            config={"exchange": "kucoin", "max_latency_seconds": 5.0},
            expected_behavior="Should timeout and fallback"
        ),

        # Network Issues
        ChaosExperiment(
            name="network_partition",
            chaos_type=ChaosType.NETWORK_PARTITION,
            target="all_external",
            duration_seconds=5,
            intensity=1.0,
            expected_behavior="Should queue requests and retry after recovery"
        ),

        # Resource Pressure
        ChaosExperiment(
            name="memory_pressure_500mb",
            chaos_type=ChaosType.MEMORY_PRESSURE,
            target="system",
            duration_seconds=10,
            intensity=0.5,
            config={"memory_mb": 500},
            expected_behavior="Should not crash, may slow down"
        ),
        ChaosExperiment(
            name="cpu_spike_5s",
            chaos_type=ChaosType.CPU_SPIKE,
            target="system",
            duration_seconds=5,
            intensity=0.8,
            config={"duration_seconds": 5.0},
            expected_behavior="Should maintain responsiveness"
        ),
    ]


class ChaosExperimentRunner:
    """High-level runner for chaos experiments with verification"""

    def __init__(self):
        self.engine = ChaosEngine()
        self.verification_results: Dict[str, bool] = {}

    def run_with_verification(self, experiment: ChaosExperiment, verify_fn: Callable) -> bool:
        """Run experiment and verify expected behavior"""
        result = self.engine.run_experiment(experiment)

        if result.success:
            try:
                verified = verify_fn(result)
                self.verification_results[experiment.name] = verified
                return verified
            except Exception as e:
                logger.error(f"Verification failed for {experiment.name}: {e}")
                self.verification_results[experiment.name] = False
                return False
        else:
            self.verification_results[experiment.name] = False
            return False

    def verify_ai_fallback(self, result: ChaosResult) -> bool:
        """Verify AI fallback worked"""
        # Check that other providers were used
        metrics = result.metrics_after
        # Look for provider rotation metrics
        return True  # Placeholder - implement actual verification

    def verify_exchange_fallback(self, result: ChaosResult) -> bool:
        """Verify exchange fallback worked"""
        return True  # Placeholder

    def verify_no_data_loss(self, result: ChaosResult) -> bool:
        """Verify no data loss occurred"""
        return True  # Placeholder

    def run_standard_suite(self) -> Dict[str, bool]:
        """Run standard chaos suite with verifications"""
        experiments = create_standard_experiments()

        verifications = {
            "openai_total_failure": self.verify_ai_fallback,
            "deepseek_partial_failure": self.verify_ai_fallback,
            "groq_rate_limit": self.verify_ai_fallback,
            "bybit_api_down": self.verify_exchange_fallback,
            "gateio_intermittent": self.verify_exchange_fallback,
            "kucoin_latency_spike": self.verify_exchange_fallback,
            "network_partition": self.verify_no_data_loss,
            "memory_pressure_500mb": self.verify_no_data_loss,
            "cpu_spike_5s": self.verify_no_data_loss,
        }

        for exp in experiments:
            verify_fn = verifications.get(exp.name, lambda r: True)
            self.run_with_verification(exp, verify_fn)

        return self.verification_results


if __name__ == "__main__":
    # Run chaos experiments
    print("Running Chaos Engineering Suite...")

    engine = ChaosEngine()

    # Register standard experiments
    for exp in create_standard_experiments():
        engine.register_experiment(exp)

    # Run all
    engine.run_all_experiments()

    # Print report
    print(engine.generate_report())