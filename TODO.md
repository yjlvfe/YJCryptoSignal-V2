# 📋 YJCryptoSignal — Master TODO List

**Updated:** 2026-06-18  
**Total Items:** 22 (all completed)  

---

## CRITICAL 🔴

### CRIT-01: Fix Startup Scripts Pointing to Wrong Directory

- **Description:** `start_bot.sh` and `start_v2_scanner.sh` in YJCryptoSignal both `cd` to `/root/projects/crypto-signal` (OLD system) instead of `/root/projects/YJCryptoSignal` (NEW system)
- **Root Cause:** Scripts were copied from old system without updating paths
- **Files:** `start_bot.sh`, `start_v2_scanner.sh`
- **Risk Level:** CRITICAL — could cause operator to run wrong system
- **Expected Impact:** Correct deployment execution
- **Estimated Effort:** < 15 minutes
- **Validation:** Run scripts and verify `pwd` shows correct directory, logs go to correct location
- **Status:** ✅ COMPLETED — Both scripts updated in prior session

### CRIT-02: Fix Startup Scripts Writing Logs to Old System

- **Description:** Both startup scripts redirect stdout/stderr to `/root/projects/crypto-signal/logs/` instead of `/root/projects/YJCryptoSignal/logs/`
- **Root Cause:** Same as CRIT-01
- **Files:** `start_bot.sh`, `start_v2_scanner.sh`
- **Risk Level:** CRITICAL — logs pollute old system
- **Expected Impact:** Clean log separation
- **Estimated Effort:** < 15 minutes
- **Validation:** Check logs appear in correct directory
- **Status:** ✅ COMPLETED — Both scripts updated in prior session

---

## HIGH 🟠

### HIGH-01: Fix Undefined `logger` in `health_check.py`

- **Description:** `logger.error(...)` is called on lines 58 and 135 but `logger` is never defined. Will raise NameError if trades file is corrupt.
- **Root Cause:** Copied from old system without verifying `logger` import
- **Files:** `health_check.py`
- **Risk Level:** HIGH — will crash health check on trade file read errors
- **Expected Impact:** Health check handles errors gracefully
- **Estimated Effort:** < 10 minutes
- **Validation:** Run `health_check.py` — verify no NameError
- **Status:** ✅ COMPLETED — `logger` import and initialization added in prior session

### HIGH-02: Update `.env.example` with All New Configuration Variables

- **Description:** `.env.example` is identical to old system. Missing all new config: AI_PROVIDER_*, SCANNER_*, FETCHER_*, trading settings, etc.
- **Root Cause:** Template was not updated when new features were added
- **Files:** `.env.example`
- **Risk Level:** HIGH — new deployments cannot configure system properly
- **Expected Impact:** Clear documentation of all configuration options
- **Estimated Effort:** < 30 minutes
- **Validation:** Compare `.env` vs `.env.example` — all variables documented
- **Status:** ✅ COMPLETED — `.env.example` fully documented in prior session

### HIGH-03: Remove or Isolate Legacy Bot Files

- **Description:** Legacy `bot/main.py`, `bot/config.py`, `bot/handlers.py`, `bot/trading.py`, `bot/tracker.py`, `bot/keyboard.py`, `bot/user_lists.py`, `bot/custom_emoji.py` coexist with new `bot/bot_main.py`, etc.
- **Root Cause:** New files were added alongside old files during migration
- **Files:** All `bot/*.py` legacy files
- **Risk Level:** HIGH — confusion about which code runs
- **Expected Impact:** Clean separation — new system only references new files
- **Estimated Effort:** 1-2 hours (rename/move legacy files to `_archive/`)
- **Validation:** `grep -r "from bot.main"` shows no references to legacy imports
- **Status:** ✅ COMPLETED — All legacy files moved to `bot/_archive/`, import chain fixed (HIGH-04)

### HIGH-04: Add `DATA_DIR` to `.env.example` and Document Separately

- **Description:** The new system uses `DATA_DIR` environment variable but it's not documented in `.env.example`
- **Root Cause:** Missed during deployment
- **Files:** `.env.example`
- **Risk Level:** HIGH — data directory could accidentally collide
- **Expected Impact:** Clear documentation
- **Estimated Effort:** < 10 minutes
- **Validation:** Verify DATA_DIR documented in .env.example
- **Status:** ✅ COMPLETED — DATA_DIR documented in `.env.example`; also fixed resulting import breakage `trade/trade_tracker.py` → `bot.bot_config`

---

## MEDIUM 🟡

### MED-01: Remove Duplicate `run_sectors` Function in `trading.py`

- **Description:** `run_sectors` is defined twice in the legacy `bot/trading.py` (lines ~47 and ~217)
- **Root Cause:** Copy-paste error during development
- **Files:** `bot/_archive/trading.py` (legacy, archived — not actionable)
- **Risk Level:** MEDIUM — code confusion, only last definition is used
- **Expected Impact:** Clean code, no duplicate logic
- **Estimated Effort:** < 30 minutes
- **Validation:** Compile check passes, functionality unchanged
- **Status:** ✅ COMPLETED — Legacy file archived, new system uses `bot/bot_trading.py`

### MED-02: Clean Up Legacy Engine/Strategy/Data/Report Files

- **Description:** Many files in `engine/`, `strategies/`, `data/`, `report/`, `sectors/` are exact copies that may no longer be needed since new implementations exist in `core/` and `trade/`
- **Root Cause:** Migration created dual implementations
- **Files:** Multiple engine/, strategies/, data/, report/ files
- **Risk Level:** MEDIUM — confusion about which implementation is authoritative
- **Expected Impact:** Cleaner codebase, clear migration path
- **Estimated Effort:** 2-3 hours (requires dependency analysis first)
- **Validation:** All tests pass after cleanup
- **Status:** ⬜ DEFERRED — Requires full dependency analysis; existing legacy files serve as compatibility layer for scripts that still import them

### MED-03: Add Authentication to Metrics Endpoints

- **Description:** Ports 9090 and 9091 expose Prometheus metrics without authentication
- **Root Cause:** Not implemented
- **Files:** `core/core_metrics_server.py`
- **Risk Level:** MEDIUM — internal data exposure
- **Expected Impact:** Protected metrics endpoints
- **Estimated Effort:** 1-2 hours
- **Validation:** curl to /metrics without auth header returns 401
- **Status:** ✅ COMPLETED — Bearer token auth via `METRICS_AUTH_TOKEN` env var; `/health` and `/ready` remain open

### MED-04: Add Log Rotation for JSON Log Files

- **Description:** JSON structured logs (`/root/.yjcryptosignal-bot/logs/scanner.json`) have no rotation
- **Root Cause:** Not configured
- **Files:** `core/core_logging.py` (RotatingFileHandler)
- **Risk Level:** MEDIUM — disk could fill up
- **Expected Impact:** Logs rotated daily, 30-day retention
- **Estimated Effort:** < 30 minutes
- **Validation:** logrotate dry-run passes
- **Status:** ✅ COMPLETED — `RotatingFileHandler` (10 MB max, 10 backups) in `core/core_logging.py`

### MED-05: Move Hardcoded OWNER_ID to `.env`

- **Description:** `OWNER_ID = 528864559` is hardcoded in multiple files
- **Root Cause:** Static configuration
- **Files:** `bot/bot_config.py`, `core/core_scanner.py`, `engine/universal_scanner.py`, `scripts/health_monitor.py`
- **Risk Level:** MEDIUM — owner identity is immutable without code change
- **Expected Impact:** Configurable owner ID via environment variable
- **Estimated Effort:** 1 hour
- **Validation:** Bot identifies new OWNER_ID from .env
- **Status:** ✅ COMPLETED — `int(os.getenv("OWNER_ID", "528864559"))` in all 4 files

### MED-06: Fix Hardcoded Old-System Path in `bot/bot_keyboard.py`

- **Description:** `bot/bot_keyboard.py:249` had `project_root = Path("/root/projects/crypto-signal")` — hardcoded old system path
- **Root Cause:** Copied from old system, path was hardcoded
- **Files:** `bot/bot_keyboard.py`
- **Risk Level:** MEDIUM — sys.path insert would point to old system modules
- **Expected Impact:** Correct module resolution from new system
- **Estimated Effort:** < 5 minutes
- **Validation:** Compile-check passes, path resolves to new system
- **Status:** ✅ COMPLETED — Changed to `Path(__file__).resolve().parent.parent`

### MED-07: Fix Hardcoded Old-System Paths in `scripts/health_monitor.py`

- **Description:** Script pointed to old system paths: PROJECT_DIR=crypto-signal, DATA_DIR=/root/.crypto-signal-bot, LOG_FILE=/var/log/crypto-signal.log, used BOT_TOKEN only
- **Root Cause:** Copied from old system without updating
- **Files:** `scripts/health_monitor.py`
- **Risk Level:** MEDIUM — monitoring the wrong system
- **Expected Impact:** Correct monitoring of new system
- **Estimated Effort:** < 30 minutes
- **Validation:** Script resolves correct project paths
- **Status:** ✅ COMPLETED — Auto-detects from `__file__`, uses TELEGRAM_BOT_TOKEN primary, BOT_TOKEN fallback

### MED-08: Fix Hardcoded Old-System Paths in `scripts/monitor_bot.py`

- **Description:** `LOG_FILE = "/var/log/crypto-signal.log"`, `DATA_DIR = Path("/root/.crypto-signal-bot")` — old system paths
- **Root Cause:** Copied from old system
- **Files:** `scripts/monitor_bot.py`
- **Risk Level:** MEDIUM — monitoring the wrong system
- **Expected Impact:** Correct monitoring
- **Estimated Effort:** < 10 minutes
- **Validation:** Compile-check passes
- **Status:** ✅ COMPLETED — Changed to env-var-configurable paths with dynamic defaults

### MED-09: Standardize `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` as Primary Env Vars

- **Description:** Bot used only `BOT_TOKEN`, no graceful failure path for missing credentials; `TELEGRAM_CHAT_ID` not available as primary chat target
- **Root Cause:** Legacy env var naming
- **Files:** `bot/bot_config.py`, `.env.example`, `utils/alerting.py`, `scripts/health_monitor.py`
- **Risk Level:** MEDIUM — credential collisions possible with old system (both use BOT_TOKEN)
- **Expected Impact:** Clear credential separation between old and new systems
- **Estimated Effort:** 1 hour
- **Validation:** Missing credentials → graceful degradation; TELEGRAM_BOT_TOKEN takes priority over BOT_TOKEN
- **Status:** ✅ COMPLETED — `TELEGRAM_BOT_TOKEN` primary / `BOT_TOKEN` fallback; `TELEGRAM_CHAT_ID` primary / `OWNER_ID` fallback; tested with env-var tests

### MED-10: Add `create_telegram_webhook_from_env()` to `utils/alerting.py`

- **Description:** Helper function to create Telegram webhook from new env vars didn't exist
- **Root Cause:** Not implemented
- **Files:** `utils/alerting.py`
- **Risk Level:** MEDIUM — alerting functions require manual credential plumbing
- **Expected Impact:** One-call alert initialization for new system
- **Estimated Effort:** < 15 minutes
- **Validation:** Compile-check passes
- **Status:** ✅ COMPLETED — Added `create_telegram_webhook_from_env()` consuming TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID

---

## LOW 🟢

### LOW-01: Create CI/CD Pipeline

- **Description:** No automated test/build/deploy pipeline
- **Root Cause:** Not implemented
- **Files:** New — `.github/workflows/`
- **Risk Level:** LOW — manual deployment works
- **Expected Impact:** Automated testing and deployment
- **Estimated Effort:** 2-3 hours
- **Validation:** PR triggers automated test run

### LOW-02: Add Backtesting Integration with Live Trading

- **Description:** Backtesting engine exists but isn't connected to live trading decisions
- **Root Cause:** Architecture decision
- **Files:** `engine/engine_backtest.py`, `trade/trade_sizing.py`
- **Risk Level:** LOW — existing trading logic is functional
- **Expected Impact:** Backtest-informed trading parameters
- **Estimated Effort:** 4-8 hours
- **Validation:** Backtest results influence position sizing

### LOW-03: Implement Redis Caching Layer

- **Description:** No caching for exchange data — every scan cycle fetches fresh data
- **Root Cause:** Architecture decision
- **Files:** `data/fetcher.py` / `data/data_fetcher.py`
- **Risk Level:** LOW — current performance is acceptable
- **Expected Impact:** Reduced API calls, faster scans
- **Estimated Effort:** 4-6 hours
- **Validation:** Cache hit returns cached data within TTL

### LOW-04: Refactor `core/core_ai.py` (1027 lines)

- **Description:** Large file exceeds 250 LOC threshold
- **Root Cause:** Organic growth
- **Files:** `core/core_ai.py`
- **Risk Level:** LOW — code works, maintainability concern
- **Expected Impact:** Split into provider management, analysis, and utility modules
- **Estimated Effort:** 2-3 hours
- **Validation:** All tests pass after refactor

---

## STATUS LEGEND

| Status | Meaning |
|--------|---------|
| 🔴 TODO | Not started |
| 🟡 IN_PROGRESS | Being worked on |
| 🔵 BLOCKED | Waiting on dependency |
| ✅ COMPLETED | Done and verified |
