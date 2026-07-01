"""
📊 Core Metrics — Prometheus-compatible metrics for CryptoSignal
عرض المقاييس على /metrics endpoint مع دعم Prometheus
"""
import time
import threading
from typing import Dict, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import logging

logger = logging.getLogger("yjcrypto-metrics")

@dataclass
class Counter:
    """Simple thread-safe counter"""
    value: float = 0.0
    _labels: Dict[str, str] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def inc(self, amount: float = 1.0):
        with self._lock:
            self.value += amount
    
    def get(self) -> float:
        with self._lock:
            return self.value
    
    def labels(self, labels: Dict[str, str]):
        """Prometheus-compatible: return counter with specified labels"""
        return _registry.counter(self.name if hasattr(self, 'name') else "unknown", labels)
    
    @property
    def label_dict(self) -> Dict[str, str]:
        return self._labels

@dataclass
class Gauge:
    """Simple thread-safe gauge"""
    value: float = 0.0
    _labels: Dict[str, str] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def set(self, value: float):
        with self._lock:
            self.value = value
    
    def inc(self, amount: float = 1.0):
        with self._lock:
            self.value += amount
    
    def dec(self, amount: float = 1.0):
        with self._lock:
            self.value -= amount
    
    def get(self) -> float:
        with self._lock:
            return self.value
    
    def labels(self, labels: Dict[str, str]):
        """Prometheus-compatible: return gauge with specified labels"""
        return _registry.gauge(self.name if hasattr(self, 'name') else "unknown", labels)
    
    @property
    def label_dict(self) -> Dict[str, str]:
        return self._labels

@dataclass
class Histogram:
    """Simple histogram with buckets"""
    buckets: Dict[float, int] = field(default_factory=dict)
    sum: float = 0.0
    count: int = 0
    _labels: Dict[str, str] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def __post_init__(self):
        if not self.buckets:
            self.buckets = {
                0.005: 0, 0.01: 0, 0.025: 0, 0.05: 0, 0.1: 0,
                0.25: 0, 0.5: 0, 1.0: 0, 2.5: 0, 5.0: 0, 10.0: 0,
                float('inf'): 0
            }
    
    def observe(self, value: float):
        with self._lock:
            self.sum += value
            self.count += 1
            for bucket in sorted(self.buckets.keys()):
                if value <= bucket:
                    self.buckets[bucket] += 1
                    break
    
    def labels(self, labels: Dict[str, str]):
        """Prometheus-compatible: return histogram with specified labels"""
        return _registry.histogram(self.name if hasattr(self, 'name') else "unknown", labels)
    
    @property
    def label_dict(self) -> Dict[str, str]:
        return self._labels

@dataclass
class Summary:
    """Simple summary with quantiles"""
    values: list = field(default_factory=list)
    max_samples: int = 1000
    labels: Dict[str, str] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def observe(self, value: float):
        with self._lock:
            if len(self.values) >= self.max_samples:
                self.values.pop(0)
            self.values.append(value)
    
    def quantile(self, q: float) -> float:
        with self._lock:
            if not self.values:
                return 0.0
            sorted_vals = sorted(self.values)
            idx = int(q * (len(sorted_vals) - 1))
            return sorted_vals[min(idx, len(sorted_vals) - 1)]

class MetricsRegistry:
    """Registry for all metrics"""
    
    def __init__(self):
        self._counters: Dict[str, Counter] = {}
        self._gauges: Dict[str, Gauge] = {}
        self._histograms: Dict[str, Histogram] = {}
        self._summaries: Dict[str, Summary] = {}
        self._lock = threading.Lock()
        self._initialized = False
    
    def _make_key(self, name: str, labels: Dict[str, str] = None) -> str:
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
    
    def counter(self, name: str, labels: Dict[str, str] = None, description: str = "") -> Counter:
        key = self._make_key(name, labels or {})
        with self._lock:
            if key not in self._counters:
                c = Counter(_labels=labels or {})
                c.name = name
                c.description = description
                self._counters[key] = c
            return self._counters[key]
    
    def gauge(self, name: str, labels: Dict[str, str] = None, description: str = "") -> Gauge:
        key = self._make_key(name, labels or {})
        with self._lock:
            if key not in self._gauges:
                g = Gauge(_labels=labels or {})
                g.name = name
                g.description = description
                self._gauges[key] = g
            return self._gauges[key]
    
    def histogram(self, name: str, labels: Dict[str, str] = None, description: str = "") -> Histogram:
        key = self._make_key(name, labels or {})
        with self._lock:
            if key not in self._histograms:
                h = Histogram(_labels=labels or {})
                h.name = name
                h.description = description
                self._histograms[key] = h
            return self._histograms[key]
    
    def summary(self, name: str, labels: Dict[str, str] = None, description: str = "") -> Summary:
        key = self._make_key(name, labels or {})
        with self._lock:
            if key not in self._summaries:
                self._summaries[key] = Summary(labels=labels or {})
            return self._summaries[key]
    
    def generate_prometheus(self) -> str:
        """Generate Prometheus text format output"""
        lines = [
            "# HELP cryptosignal_info CryptoSignal bot information",
            "# TYPE cryptosignal_info gauge",
            'cryptosignal_info{version="3.0.0",project="YJCryptoSignal"} 1',
            ""
        ]
        
        with self._lock:
            # Counters
            for key, counter in self._counters.items():
                label_part = ""
                if counter.label_dict:
                    label_part = "{" + ",".join(f'{k}="{v}"' for k, v in counter.label_dict.items()) + "}"
                name = key.split("{")[0] if "{" in key else key
                lines.append(f"# HELP {name} {counter.description or 'Counter'}")
                lines.append(f"# TYPE {name} counter")
                lines.append(f"{name}{label_part} {counter.get()}")
                lines.append("")
            
            # Gauges
            for key, gauge in self._gauges.items():
                label_part = ""
                if gauge.label_dict:
                    label_part = "{" + ",".join(f'{k}="{v}"' for k, v in gauge.label_dict.items()) + "}"
                name = key.split("{")[0] if "{" in key else key
                lines.append(f"# HELP {name} {gauge.description or 'Gauge'}")
                lines.append(f"# TYPE {name} gauge")
                lines.append(f"{name}{label_part} {gauge.get()}")
                lines.append("")
            
            # Histograms
            for key, hist in self._histograms.items():
                label_part = ""
                if hist.label_dict:
                    label_part = "{" + ",".join(f'{k}="{v}"' for k, v in hist.label_dict.items()) + "}"
                name = key.split("{")[0] if "{" in key else key
                lines.append(f"# HELP {name} {hist.description or 'Histogram'}")
                lines.append(f"# TYPE {name} histogram")
                
                cumulative = 0
                for bucket, count in sorted(hist.buckets.items()):
                    bucket_label = "inf" if bucket == float('inf') else str(bucket)
                    full_label = f'{label_part.rstrip("}")},le="{bucket_label}"}}' if label_part else f'{{le="{bucket_label}"}}'
                    cumulative += count
                    lines.append(f"{name}_bucket{full_label} {cumulative}")
                lines.append(f"{name}_sum{label_part} {hist.sum}")
                lines.append(f"{name}_count{label_part} {hist.count}")
                lines.append("")
            
            # Summaries
            for key, summ in self._summaries.items():
                label_part = ""
                if summ.label_dict:
                    label_part = "{" + ",".join(f'{k}="{v}"' for k, v in summ.label_dict.items()) + "}"
                name = key.split("{")[0] if "{" in key else key
                lines.append(f"# HELP {name} Summary")
                lines.append(f"# TYPE {name} summary")
                for q in [0.5, 0.9, 0.95, 0.99]:
                    labels_str = ",".join(f'{k}="{v}"' for k, v in summ.label_dict.items())
                    if labels_str:
                        lines.append(f'{name}{{quantile="{q}",{labels_str}}} {summ.quantile(q)}')
                    else:
                        lines.append(f'{name}{{quantile="{q}"}} {summ.quantile(q)}')
                lines.append(f"{name}_sum{label_part} {sum(v for v in summ.values) if hasattr(summ, 'values') and summ.values else 0}")
                lines.append(f"{name}_count{label_part} {len(summ.values) if hasattr(summ, 'values') and summ.values else 0}")
                lines.append("")
        
        return "\n".join(lines)

# Global registry
_registry = MetricsRegistry()

def get_registry() -> MetricsRegistry:
    return _registry

# ═══════════════════════════════════════════
# Pre-defined metrics for CryptoSignal
# ═══════════════════════════════════════════

# System metrics
SYSTEM_UPTIME = _registry.gauge("cryptosignal_system_uptime_seconds", description="System uptime in seconds")
SYSTEM_CYCLE_COUNT = _registry.counter("cryptosignal_cycles_total", description="Total scanner cycles")
SYSTEM_LAST_CYCLE_DURATION = _registry.gauge("cryptosignal_last_cycle_duration_seconds", description="Duration of last scan cycle")

# Scanner metrics
SCANNER_COINS_SCANNED = _registry.counter("cryptosignal_scanner_coins_scanned_total", description="Total coins scanned")
SCANNER_SIGNALS_GENERATED = _registry.counter("cryptosignal_scanner_signals_generated_total", description="Total signals generated")
SCANNER_AI_CALLS = _registry.counter("cryptosignal_scanner_ai_calls_total", description="Total AI API calls", labels={"provider": "unknown", "result": "unknown"})
SCANNER_SCAN_DURATION = _registry.histogram("cryptosignal_scanner_scan_duration_seconds", description="Time spent scanning coins")

# AI metrics
AI_REQUEST_DURATION = _registry.histogram("cryptosignal_ai_request_duration_seconds", description="AI request latency", labels={"provider": "unknown"})
AI_REQUESTS_TOTAL = _registry.counter("cryptosignal_ai_requests_total", description="Total AI requests", labels={"provider": "unknown", "model": "unknown", "status": "unknown"})
AI_TOKENS_USED = _registry.counter("cryptosignal_ai_tokens_used_total", description="Total tokens consumed", labels={"provider": "unknown"})
AI_KEY_ROTATIONS = _registry.counter("cryptosignal_ai_key_rotations_total", description="Total key rotations", labels={"provider": "unknown"})

# Trade metrics
TRADES_ACTIVE = _registry.gauge("cryptosignal_trades_active", description="Currently active trades")
TRADES_OPENED = _registry.counter("cryptosignal_trades_opened_total", description="Total trades opened", labels={"direction": "unknown"})
TRADES_CLOSED = _registry.counter("cryptosignal_trades_closed_total", description="Total trades closed", labels={"result": "unknown"})
TRADE_PNL = _registry.histogram("cryptosignal_trade_pnl_percent", description="Trade PnL percentage")
TRADE_DURATION = _registry.histogram("cryptosignal_trade_duration_hours", description="Trade duration in hours")

# Bot metrics
BOT_MESSAGES_SENT = _registry.counter("cryptosignal_bot_messages_sent_total", description="Total messages sent", labels={"type": "unknown"})
BOT_COMMANDS_RECEIVED = _registry.counter("cryptosignal_bot_commands_received_total", description="Total commands received", labels={"command": "unknown"})
BOT_ACTIVE_SUBSCRIBERS = _registry.gauge("cryptosignal_bot_active_subscribers", description="Active subscribers")

# Exchange metrics
EXCHANGE_API_CALLS = _registry.counter("cryptosignal_exchange_api_calls_total", description="Exchange API calls", labels={"exchange": "unknown", "endpoint": "unknown", "status": "unknown"})
EXCHANGE_ERRORS = _registry.counter("cryptosignal_exchange_errors_total", description="Exchange errors", labels={"exchange": "unknown", "error_type": "unknown"})
EXCHANGE_LATENCY = _registry.histogram("cryptosignal_exchange_latency_seconds", description="Exchange API latency", labels={"exchange": "unknown"})

# Learning metrics
LEARNING_TRADES_RECORDED = _registry.counter("cryptosignal_learning_trades_recorded_total", description="Trades recorded for learning")
LEARNING_WEIGHT_UPDATES = _registry.counter("cryptosignal_learning_weight_updates_total", description="Strategy weight updates")
LEARNING_KILL_SWITCHES = _registry.counter("cryptosignal_learning_kill_switches_total", description="Kill switches activated", labels={"strategy": "unknown"})

# Regime metrics
REGIME_CURRENT = _registry.gauge("cryptosignal_regime_current", description="Current market regime", labels={"regime": "unknown"})
REGIME_CONFIDENCE = _registry.gauge("cryptosignal_regime_confidence", description="Regime detection confidence")

# ═══════════════════════════════════════════
# Helper functions
# ═══════════════════════════════════════════

_start_time = time.time()

def record_scan_cycle(coins_scanned: int, signals: int, duration: float):
    """Record a completed scan cycle"""
    SYSTEM_CYCLE_COUNT.inc()
    SYSTEM_LAST_CYCLE_DURATION.set(duration)
    SCANNER_COINS_SCANNED.inc(coins_scanned)
    SCANNER_SIGNALS_GENERATED.inc(signals)

def record_ai_call(provider: str, model: str, duration: float, success: bool, tokens: int = 0):
    """Record an AI API call"""
    AI_REQUEST_DURATION.labels({"provider": provider}).observe(duration)
    AI_REQUESTS_TOTAL.labels({"provider": provider, "model": model, "status": "success" if success else "error"}).inc()
    if tokens > 0:
        AI_TOKENS_USED.labels({"provider": provider}).inc(tokens)

def record_key_rotation(provider: str):
    """Record a key rotation event"""
    AI_KEY_ROTATIONS.labels({"provider": provider}).inc()

def record_trade_opened(direction: str):
    """Record a trade opening"""
    TRADES_OPENED.labels({"direction": direction}).inc()
    TRADES_ACTIVE.inc()

def record_trade_closed(result: str, pnl_pct: float, duration_hours: float):
    """Record a trade closing"""
    TRADES_CLOSED.labels({"result": result}).inc()
    TRADES_ACTIVE.dec()
    TRADE_PNL.observe(pnl_pct)
    TRADE_DURATION.observe(duration_hours)

def record_bot_message(message_type: str):
    """Record a bot message sent"""
    BOT_MESSAGES_SENT.labels({"type": message_type}).inc()

def record_bot_command(command: str):
    """Record a bot command received"""
    BOT_COMMANDS_RECEIVED.labels({"command": command}).inc()

def set_active_subscribers(count: int):
    """Set active subscriber count"""
    BOT_ACTIVE_SUBSCRIBERS.set(count)

def record_exchange_call(exchange: str, endpoint: str, duration: float, success: bool, error_type: str = None):
    """Record an exchange API call"""
    EXCHANGE_API_CALLS.labels({"exchange": exchange, "endpoint": endpoint, "status": "success" if success else "error"}).inc()
    EXCHANGE_LATENCY.labels({"exchange": exchange}).observe(duration)
    if not success and error_type:
        EXCHANGE_ERRORS.labels({"exchange": exchange, "error_type": error_type}).inc()

def record_learning_trade():
    """Record a trade for learning"""
    LEARNING_TRADES_RECORDED.inc()

def record_weight_update():
    """Record a weight update"""
    LEARNING_WEIGHT_UPDATES.inc()

def record_kill_switch(strategy: str):
    """Record a kill switch activation"""
    LEARNING_KILL_SWITCHES.labels({"strategy": strategy}).inc()

def set_regime(regime: str, confidence: float):
    """Set current market regime"""
    REGIME_CURRENT.labels({"regime": regime}).set(1)
    REGIME_CONFIDENCE.set(confidence)

# Startup time
def update_uptime():
    SYSTEM_UPTIME.set(time.time() - _start_time)