"""
🦅🌍 YJCryptoSignal Scanner Runner — with Observability
"""
import os
import sys
import time
import threading
from pathlib import Path

# Force unbuffered output
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
os.environ['PYTHONUNBUFFERED'] = '1'

# Load .env first
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ[key.strip()] = val.strip().strip('"').strip("'")
    print("📄 .env loaded", flush=True)

# ─── Observability: Metrics Server ───
try:
    from core.core_metrics_server import MetricsServer
    _metrics_port = int(os.getenv("SCANNER_METRICS_PORT", "9090"))
    _metrics_server = MetricsServer(host="0.0.0.0", port=_metrics_port)
    _metrics_server.start(blocking=False)
    print(f"📊 Metrics server started on :{_metrics_port}", flush=True)
except Exception as e:
    print(f"⚠️ Metrics server failed to start: {e}", flush=True)
    _metrics_server = None

# ─── Observability: Structured Logging ───
try:
    from core.core_logging import setup_json_logging, get_context_logger, log_scan_start, log_scan_complete
    _default_log = str(Path(__file__).resolve().parent / "logs" / "scanner.json")
    _scanner_log_file = os.getenv("SCANNER_LOG_FILE", _default_log)
    setup_json_logging("cryptosignal-scanner", "INFO", log_file=_scanner_log_file)
    SCAN_LOGGER = get_context_logger("cryptosignal.scanner", {"component": "scanner"})
    HAS_STRUCTURED_LOGGING = True
except Exception as e:
    print(f"⚠️ Structured logging unavailable: {e}", flush=True)
    HAS_STRUCTURED_LOGGING = False
    # Fallback logging
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    SCAN_LOGGER = logging.getLogger("cryptosignal.scanner")

# ─── Observability: AI Metrics ───
try:
    from core.core_metrics import record_ai_call, record_scan_cycle
    HAS_METRICS = True
except Exception as e:
    print(f"⚠️ Metrics unavailable: {e}", flush=True)
    HAS_METRICS = False

# Log provider status at startup
from core.core_ai import get_provider_status
providers = get_provider_status()
healthy = sum(1 for p in providers.values() if p['healthy'])
print(f"🤖 AI Providers: {healthy}/{len(providers)} healthy", flush=True)
for name, status in providers.items():
    icon = "🟢" if status['healthy'] else "🔴"
    print(f"  {icon} {name}: {status['keys_available']} keys, {status['rpd_used']}/60 RPM used", flush=True)

# Monkey-patch universal_scanner to add metrics
_original_universal_scan = None
try:
    import core.core_scanner as us
    _original_universal_scan = us.universal_scan_loop
    
    def instrumented_scan_loop(*args, **kwargs):
        """Wrapper that adds metrics around scan cycles"""
        import core.core_scanner as us_module
        from core.core_ai import analyze_coin_pure as original_analyze_coin_pure
        
        # Actually wrap the internal loop by replacing a helper
        original_gather = us_module._gather_all_exchange_coins
        
        def tracked_gather(fetcher, min_volume=500000):
            start = time.time()
            result = original_gather(fetcher, min_volume)
            duration = time.time() - start
            if HAS_METRICS:
                from core.core_metrics import EXCHANGE_LATENCY
                EXCHANGE_LATENCY.labels({"exchange": "multipool"}).observe(duration)
            return result
        
        def tracked_analyze(symbol, price, df, regime_data):
            start = time.time()
            result = original_analyze_coin_pure(symbol, price, df, regime_data)
            duration = time.time() - start
            if HAS_METRICS:
                from core.core_metrics import AI_REQUEST_DURATION
                AI_REQUEST_DURATION.labels({"provider": "scanner_analyzer"}).observe(duration)
            return result
        
        us_module._gather_all_exchange_coins = tracked_gather
        us_module.analyze_coin_pure = tracked_analyze
        
        try:
            return _original_universal_scan(*args, **kwargs)
        finally:
            us_module._gather_all_exchange_coins = original_gather
            us_module.analyze_coin_pure = original_analyze_coin_pure
    
    us.universal_scan_loop = instrumented_scan_loop
    print("🔧 Scanner instrumented with metrics", flush=True)
except Exception as e:
    print(f"⚠️ Scanner instrumentation failed: {e}", flush=True)

# Run the scanner
from core.core_scanner import universal_scan_loop

# Log scan start
if HAS_STRUCTURED_LOGGING:
    log_scan_start(1, 0)  # unknown count at start

print("🦅🌍 Starting Universal Scanner v3...", flush=True)
universal_scan_loop()