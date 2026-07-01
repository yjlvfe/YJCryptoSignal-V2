# scripts/ — Ops, Health, Validation, Chaos Tools

8 files, 3.3K LOC. Operational scripts called by operators/systemd, NOT imported by the main app. Largest file (health_monitor.py) is the biggest single file in the project at 1457 LOC.

## STRUCTURE

```
scripts/
├── health_monitor.py        # 1457 LOC — 30-min cycle: 9 checks + auto-repair + Telegram report
├── validate_imports.py      # AST-based: orphan/circular/missing/duplicate import detection
├── load_test.py             # LoadTestResult dataclass + ThreadPool + asyncio load frameworks
├── run_stress_tests.py      # CLI runner: metrics/logging/alerting load tests + optional chaos
├── chaos_engineering.py     # 10 experiment types (provider fail, lag, crash, etc.)
├── monitor_bot.py           # Bot log watcher: error detection + recommendation analysis
├── rebuild_learning.py      # One-shot: rebuild learn_adaptive data from trade_history.json
└── __init__.py              # Package marker only
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Production health check | `health_monitor.py` | 14-day expiry, auto-repair, Telegram alerts |
| Import validation | `validate_imports.py` | Run before large refactors |
| Load/chaos testing | `run_stress_tests.py` | Orchestrator; `RUN_CHAOS=true` for chaos |
| Bot log monitoring | `monitor_bot.py` | Checks every 10 min, reads BOT_LOG_FILE |
| Rebuild learning data | `rebuild_learning.py` | One-shot from trade_history.json |
| Chaos experiments | `chaos_engineering.py` | 10 types, used by run_stress_tests |

## CONVENTIONS

- **CLI-only**: These scripts are executed directly (`python3 scripts/foo.py`) or via systemd timers. None expose importable APIs consumed by the main app (except `chaos_engineering.py` and `load_test.py` → `run_stress_tests.py`).
- **Conditional imports**: `health_monitor.py` and `chaos_engineering.py` import heavy deps (requests, etc.) inside functions, not at module level.
- **Magic main patterns**: Scripts use both `if __name__ == "__main__"` and `def main()` — each file decides independently.
- **Shebangs**: `#!/usr/bin/env python3` on scripts meant for cron/systemd (`health_monitor.py`, `monitor_bot.py`, `rebuild_learning.py`).

## ANTI-PATTERNS

1. **`health_monitor.py` is 1457 LOC** — the largest single file in the project. Should be split (check→repair→report phases).
2. **`health_monitor.py` references legacy module names** (lines 935, 950: `engine.position_sizing_v2`, `engine.portfolio_heat`) — should reference `trade.trade_sizing` and `trade.trade_heat`.
3. **`monitor_bot.py` hardcodes `DATA_DIR` fallback** to `/root/.yjcryptosignal-bot` — same stale path pattern as the rest of the project.
4. **`rebuild_learning.py` runs immediately on import** (top-level code blocks at module level, not inside `main()`).
5. **No tests** for any script in `tests/`. These are critically important ops tools with zero coverage.
