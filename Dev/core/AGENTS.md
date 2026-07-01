# core/ — AI, Metrics, Logging, Scanner Orchestration

12 files, 3.5K LOC. AI provider router, structured logging, custom Prometheus metrics, scanner loop. Central hub connected to both entry points.

## STRUCTURE

```
core/
├── core_ai.py           # Facade: re-exports from providers + ai_client + ai_parser
├── core_scanner.py      # universal_scan_loop() — V3 scanner main loop (661 LOC)
├── core_analyzer.py     # Analyzer class — runs 11 strategies, aggregates results (378 LOC)
├── core_logging.py      # JSONFormatter + ContextLogger + 6 pre-configured loggers
├── core_metrics.py      # Custom Counter/Gauge/Histogram/Summary (no prometheus_client)
├── core_metrics_server.py  # HTTP /metrics endpoint (Scanner :9090, Bot :9091)
├── core_regime.py       # Market regime detection (311 LOC)
├── core_smart_targets.py   # AI-powered target generation (255 LOC)
├── providers.py         # AI provider config from .env (6 providers, key rotation)
├── ai_client.py         # HTTP session + retry logic for AI API calls (264 LOC)
├── ai_parser.py         # AI response parsing (283 LOC)
└── __init__.py          # Re-exports 10 symbols with __all__
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Main scan loop | `core_scanner.py` → `universal_scan_loop()` | Entry point for scanner service |
| AI decision per coin | `core_ai.py` (facade) → `ai_client.py` | Routes to providers with failover |
| Multi-strategy analysis | `core_analyzer.py` → `Analyzer.run_all()` | Runs all 11 strategies via strategies/ |
| Setup logging | `core_logging.py` → `setup_json_logging()` | JSON stdout + rotating file |
| Define metrics | `core_metrics.py` | Counter, Gauge, Histogram, Summary classes |
| AI provider config | `providers.py` | Reads AI_PROVIDER_{1-6}_* from .env |
| Regime detection | `core_regime.py` | Classifies bull/sideways/bear regimes |
| Smart targets | `core_smart_targets.py` | AI-generated TP/SL targets |
| Start metrics server | `core_metrics_server.py` | `MetricsServer(host, port).start()` |

## CONVENTIONS

- **Facade pattern**: `core_ai.py` re-exports but contains zero logic. Actual implementation in `providers.py`, `ai_client.py`, `ai_parser.py`.
- **Imports**: Clean absolute imports. No wildcards. Explicit `__all__` in `__init__.py`.
- **Logging**: Uses `core/core_logging.py` structured JSON. Logger names: `"yjcrypto-{component}"` (e.g., `"yjcrypto-core-ai"`, `"yjcrypto-core-scanner"`). Renamed from `crypto-signal-*` in Wave 2.
- **Type hints**: Present on most function signatures. Better than rest of codebase.
- **Docstrings**: Arabic + English, emoji-prefixed. Consistent style.
- **Metrics**: Custom in-memory implementation (no external prometheus_client dependency). Thread-safe.

## ANTI-PATTERNS

1. **`except Exception` with silent fallback** — `core_scanner.py` (lines 283, 460) returns empty dict on AI failure. Use `logger.exception()`.
2. **Hardcoded paths** — `core_scanner.py` (lines 16-20) hardcodes `/root/.yjcryptosignal-bot/*.json`. Use env var.
3. **Do NOT edit `core_ai.py`** to add logic — it's a facade. Add to the underlying module.
