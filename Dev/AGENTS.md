# YJCryptoSignal v5.8.0

Two-service crypto trading signal system. Scanner + Telegram bot, communicating via JSON files + optional Unix socket IPC. Python 3.11, no framework.

## STRUCTURE

```
Dev/
├── bot/           # Telegram bot (11 files, 4.3K LOC)
├── core/          # AI routing, logging, metrics, scanner loop (12 files, 3.5K LOC)
├── engine/        # Trading engines: scanner, backtest, optimizer, safety (25 files, 9.8K LOC)
├── strategies/    # 11 TA strategies + BaseStrategy (13 files, 1.9K LOC)
├── trade/         # Trade tracking, sizing, safety (6 files, 2.3K LOC)
├── data/          # Exchange data fetchers (5 files, 1.5K LOC)
├── learn/         # Adaptive strategy learning (1 active, 611 LOC)
├── scripts/       # Ops: health monitor, load test, chaos, validation (8 files, 3.3K LOC)
├── tests/         # 113 tests across 12 files (2.4K LOC)
├── report/        # Telegram/sector report formatters (3 files, 0.6K LOC)
├── sectors/       # Crypto sector categorization (3 files, 0.5K LOC)
├── utils/         # AlertManager singleton (2 files, 0.3K LOC)
└── docs/          # OPERATIONAL_RUNBOOKS.md + PRODUCTION_READINESS_CHECKLIST.md
```

## WHERE TO LOOK

| Task | Go To | Notes |
|------|-------|-------|
| AI decision logic | `core/core_ai.py` → `core/ai_client.py`, `core/ai_parser.py` | Facade pattern, routes to 3 sub-modules |
| 11-strategy ensemble | `core/core_analyzer.py` + `strategies/*.py` | Imported by scanner and bot |
| Scanner main loop | `core/core_scanner.py` | `universal_scan_loop()` |
| Telegram handlers | `bot/bot_handlers.py` | 1261 lines, manual if/elif routing, no decorators |
| Trading scheduler | `bot/bot_trading.py` | `scheduler_loop()` + `run_scan()` |
| Multi-exchange fetch | `data/data_fetcher.py` | 5 exchanges with fallback |
| Backtesting | `engine/engine_backtest.py` | Walk-forward + Monte Carlo |
| Safety/circuit breaker | `engine/safety_walls.py` | Daily loss caps, drawdown |
| Position sizing | `trade/trade_sizing.py` | Kelly Criterion |
| Trade tracking | `trade/trade_tracker.py` | Cross-process fcntl locks, JSON persistence |
| Metrics endpoint | `core/core_metrics_server.py` | :9090 (scanner), :9091 (bot) |
| Adaptive learning | `learn/learn_adaptive.py` | Strategy weight adjustment |
| Health monitoring | `scripts/health_monitor.py` | 9 checks, auto-repair, 14-day expiry |
| Chaos testing | `scripts/chaos_engineering.py` | 10 experiment types |
| Import validation | `scripts/validate_imports.py` | Circular/orphan/missing import checks |
| Production runbooks | `docs/OPERATIONAL_RUNBOOKS.md` | 14 runbooks (incident, backup, scaling) |

## ENTRY POINTS

```
run_scanner.py              # systemd: yjcryptosignal-scanner (core_scanner.universal_scan_loop)
bot/bot_main.py             # systemd: yjcryptosignal-bot (Telegram long-poll + scheduler loop)
health_check.py             # One-shot diagnostics
yjcryptosignal-ctl          # Bash CLI: status|start|stop|restart|doctor|venv|logs|watch
```

## ⚠️ DUPLICATE FILE PAIRS — 0 REMAINING (ALL RESOLVED IN WAVE 4)

The project underwent V2→V3 refactor. Old files were NOT always deleted. **15 duplicate files were deleted in Wave 2 (Jun 2026); the remaining 13 were deleted in Wave 4 (Jun 2026) after import migration.** Active code now imports ONLY canonical (prefixed) names:

| Status | Old (Legacy) | New (Active) |
|--------|---|---|
| ✅ Deleted (Wave 2) | `engine/scanner.py` | `engine/engine_scanner.py` |
| ✅ | `engine/genetic_optimizer.py` | `engine/engine_optimizer.py` |
| ✅ | `engine/smart_entry.py` | `engine/engine_smart_entry.py` |
| ✅ | `engine/sentiment.py` | `engine/engine_sentiment.py` |
| ✅ | `engine/kronos.py` | `engine/engine_kronos.py` |
| ✅ | `engine/layers.py` | `engine/engine_layers.py` |
| ✅ | `engine/smart_targets.py` | `core/core_smart_targets.py` |
| ✅ | `engine/universal_hunter.py` | (V3 replacement) |
| ✅ | `engine/ai_analyst.py` | (V3 replacement) |
| ✅ | `learn/learn_expectancy.py` | `learn/learn_adaptive.py` |
| ✅ | `learn/learn_regime.py` | `learn/learn_adaptive.py` |
| ✅ | `learn/learn_weights.py` | `learn/learn_adaptive.py` |
| ✅ | `report/telegram.py` | `report/report_telegram.py` |
| ✅ | `report/sectors.py` | `report/report_sectors.py` |
| ✅ | `chart/__init__.py` | Deleted (empty) |
| ✅ Deleted (Wave 4) | `data/fetcher.py` | `data/data_fetcher.py` |
| ✅ | `data/exchanges.py` | `data/data_exchanges.py` |
| ✅ | `engine/backtesting.py` | `engine/engine_backtest.py` |
| ✅ | `engine/breakout_hunter.py` | `engine/engine_breakout.py` |
| ✅ | `engine/liquidity_intel.py` | `engine/engine_liquidity.py` |
| ✅ | `engine/position_sizing_v2.py` | `trade/trade_sizing.py` |
| ✅ | `engine/self_learning_v2.py` | `learn/learn_adaptive.py` |
| ✅ | `engine/weights.py` | `engine/engine_weights.py` |
| ✅ | `engine/analyzer.py` | `core/core_analyzer.py` |
| ✅ | `engine/multi_analyzer.py` | `engine/engine_multi_tf.py` |
| ✅ | `engine/regime.py` | `core/core_regime.py` |
| ✅ | `engine/volume_advanced.py` | `engine/engine_volume_advanced.py` |
| ✅ | `engine/portfolio_heat.py` | `trade/trade_heat.py` |
| ✅ | `sectors/categories.py` | `sectors/sectors_categories.py` |
| ✅ | `bot/bot_userlists.py` | `trade/trade_userlists.py` |
| ✅ Deleted (Wave 0) | `engine/universal_scanner.py` | `core/core_scanner.py` |

**Rule for agents**: All legacy duplicates have been deleted. Always use the canonical (prefixed) module names.

## CONVENTIONS (Project-Specific Deviations)

- **Imports**: Absolute from project root (`from core.x import y`). `bot/` uses wildcard `import *` (legacy only — do NOT propagate).
- **Logging**: Structured JSON via `core/core_logging.py` (`JSONFormatter`, `ContextLogger`). Logger names: `logging.getLogger("yjcrypto-{component}")`. Renamed from `crypto-signal-*` in Wave 2.
- **Config**: ENV-ONLY (no YAML/TOML). `.env` manually parsed in each entry point. No `python-dotenv`.
- **State**: JSON files with `fcntl.flock()` cross-process locking. No database.
- **Testing**: pytest class-based. `asyncio_mode=auto`. SUT imported inside test body. `reset_singletons` autouse fixture.
- **Docstrings**: Bilingual (Arabic + English), emoji-prefixed. Do NOT "fix" to English.
- **Type hints**: Partial/inconsistent. Only `dataclass` fields and `core/` modules use them. No static type checking configured.
- **No linter/formatter** configured (`validate_imports.py` is the only quality gate).
- **No decorator-based handlers** — Telegram routing is manual `if/elif` in `handle_update()` / `handle_callback()`.

## ANTI-PATTERNS (DO NOT)

1. **`except Exception: pass`** — 30+ occurrences across engine/, bot/, core/. Root cause of invisible failures in production. Always `logger.exception()`.
2. **Hardcoded paths** — `DATA_DIR` redefined independently in 5+ modules. All paths must use `os.environ` or centralize in one config module.
3. **Wildcard imports in new code** — `from x import *` is legacy bot pattern only. Use explicit imports everywhere else.
4. **Bare `except:`** — Already found in archived code. Never. Catches `SystemExit`/`KeyboardInterrupt`.
5. **Creating duplicate files** — The 19+ duplicates are a known maintenance burden. Always consolidate, never duplicate.

## COMMANDS

```bash
python3 run_scanner.py                                  # Start scanner
python3 bot/bot_main.py                                 # Start bot
pytest tests/ -v                                        # Run tests
python3 scripts/validate_imports.py                     # Validate imports
python3 health_check.py                                 # Quick health check
./yjcryptosignal-ctl status|start|stop|restart|doctor     # Ops CLI
python3 scripts/run_stress_tests.py                     # Stress + chaos tests
```

## KEY ARCHITECTURE

- **Two systemd services**: Scanner (`:9090` metrics) + Bot (`:9091` metrics), independent processes
- **IPC**: Shared JSON files (`/root/.yjcryptosignal-bot/`) + optional Unix socket (`/tmp/cryptosignal-bus.sock`)
- **AI Router**: 6 providers with priority failover, key rotation, rate limits (`core/providers.py`)
- **11 strategy schools** × 3 timeframes (1H/4H/1D), unified via `core/core_analyzer.py`
- **Safety walls**: Circuit breaker, daily loss caps, drawdown tracking
- **Observability**: JSON logs (ELK-compatible) + Prometheus /metrics + /health

## NOTES

- `engine/engine_layers.py` has `DISABLED` flag — not operational
- `bus_client.py` is a symlink to `/opt/cryptosignal-bus/client.py` — external dependency
- **Wave 2 cleanup (Jun 2026)**: 15 duplicate files deleted, 42 loggers renamed from `crypto-signal-*` to `yjcrypto-*`, M-03 log paths unified to `Dev/logs/`
- **Wave 4 cleanup (Jun 2026)**: 13 remaining duplicate files deleted after import migration — all 17 legacy pairs now resolved, no active imports point to legacy modules
- **~31% of codebase is dead/duplicate** (~7K LOC legacy + ~4.8K LOC archive = ~11.8K of ~38K LOC)
- **engine/ (25 files) has ZERO direct tests** — highest risk area
