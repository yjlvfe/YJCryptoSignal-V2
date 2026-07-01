# 🏗️ YJCryptoSignal — Implementation Plan

**Date:** 2026-06-18  
**Priority:** Fix critical bugs → High issues → Medium → Low  

---

## WAVE 1: CRITICAL FIXES (DO FIRST)

### Task 1.1: Fix `start_bot.sh`

- **Objective:** Update directory path and log path from old system to new system
- **Files Affected:** `/root/projects/YJCryptoSignal/start_bot.sh`
- **Changes:**
  - `cd /root/projects/crypto-signal` → `cd /root/projects/YJCryptoSignal`
  - `>> /root/projects/crypto-signal/logs/stdout.log` → `>> /root/projects/YJCryptoSignal/logs/stdout.log`
- **Risk Level:** CRITICAL
- **Validation:** Run script with `--once` flag, verify correct paths
- **Rollback:** Revert to original content (git revert)
- **Status:** ✅ COMPLETED

### Task 1.2: Fix `start_v2_scanner.sh`

- **Objective:** Same as 1.1 for scanner script
- **Files Affected:** `/root/projects/YJCryptoSignal/start_v2_scanner.sh`
- **Changes:**
  - `cd /root/projects/crypto-signal` → `cd /root/projects/YJCryptoSignal`
  - `>> /root/projects/crypto-signal/logs/v2_scanner.log` → `>> /root/projects/YJCryptoSignal/logs/v2_scanner.log`
- **Risk Level:** CRITICAL
- **Validation:** Run script, verify correct paths
- **Rollback:** Revert to original content
- **Status:** ✅ COMPLETED

---

## WAVE 2: HIGH PRIORITY FIXES

### Task 2.1: Fix Undefined `logger` in `health_check.py`

- **Objective:** Add proper logger initialization
- **Files Affected:** `/root/projects/YJCryptoSignal/health_check.py`
- **Changes:**
  - Add `logger = logging.getLogger("crypto-signal-health")` after `logging` import
- **Risk Level:** HIGH
- **Validation:** Run `python3 health_check.py` — no NameError
- **Rollback:** Revert logger addition
- **Status:** ✅ COMPLETED

### Task 2.2: Update `.env.example`

- **Objective:** Document all new configuration variables
- **Files Affected:** `/root/projects/YJCryptoSignal/.env.example`
- **Changes:**
  - Add AI_PROVIDER_1 through AI_PROVIDER_6 configuration documentation
  - Add SCANNER_MIN_CONFIDENCE, SCANNER_MIN_STRENGTH, SCANNER_LIQUIDITY_MIN_SCORE, SCANNER_ALIGNMENT_MIN
  - Add MAX_ACTIVE_TRADES, DEFAULT_POSITION_PCT, MAX_PORTFOLIO_HEAT, MAX_DRAWDOWN_PCT
  - Add SCAN_INTERVAL_MINUTES, SIGNAL_COOLDOWN_MINUTES
  - Add FETCHER_CACHE_TTL, FETCHER_TIMEOUT, FETCHER_MAX_RETRIES
  - Add AI_MAX_RETRIES, AI_RETRY_BASE_DELAY, AI_GLOBAL_MIN_INTERVAL
  - Add DATA_DIR documentation
  - Add LOG_LEVEL, TZ documentation
- **Risk Level:** HIGH
- **Validation:** Compare `.env` vs `.env.example` — every active variable documented
- **Rollback:** Revert to original
- **Status:** ✅ COMPLETED

### Task 2.3: Isolate Legacy Bot Files

- **Objective:** Move legacy `bot/main.py`, etc. to `_archive/` to prevent accidental execution
- **Files Affected:** Create `bot/_archive/` directory, move legacy files
- **Changes:**
  - `mv bot/main.py bot/_archive/main.py`
  - `mv bot/config.py bot/_archive/config.py`
  - `mv bot/handlers.py bot/_archive/handlers.py`
  - `mv bot/trading.py bot/_archive/trading.py`
  - `mv bot/tracker.py bot/_archive/tracker.py`
  - `mv bot/keyboard.py bot/_archive/keyboard.py`
  - `mv bot/user_lists.py bot/_archive/user_lists.py`
  - `mv bot/custom_emoji.py bot/_archive/custom_emoji.py`
- **Risk Level:** HIGH (verify new bot_main.py works independently first)
- **Validation:** `python3 bot/bot_main.py --help` works; all old imports updated
- **Rollback:** Restore files from `_archive/`
- **Status:** ✅ COMPLETED

---

## WAVE 3: MEDIUM PRIORITY FIXES

### Task 3.1: Remove Duplicate `run_sectors` in `trading.py`

- **Files Affected:** `bot/_archive/trading.py` (legacy, archived)
- **Risk Level:** MEDIUM
- **Validation:** Syntax check passes
- **Status:** ✅ COMPLETED (file archived, no longer relevant)

### Task 3.2: Add Metrics Endpoint Authentication

- **Files Affected:** `core/core_metrics_server.py`
- **Risk Level:** MEDIUM
- **Validation:** Unauthenticated /metrics returns 401
- **Status:** ✅ COMPLETED

### Task 3.3: Configure Log Rotation

- **Files Affected:** `core/core_logging.py` (RotatingFileHandler)
- **Risk Level:** MEDIUM
- **Validation:** `logrotate --debug` passes (in-code rotation configured)
- **Status:** ✅ COMPLETED

### Task 3.4: Move OWNER_ID to `.env`

- **Files Affected:** `bot/bot_config.py`, `core/core_scanner.py`, `engine/universal_scanner.py`, `scripts/health_monitor.py`
- **Risk Level:** MEDIUM
- **Validation:** Bot reads OWNER_ID from .env correctly
- **Status:** ✅ COMPLETED

---

## WAVE 3.5: CREDENTIAL SEPARATION & SECURITY REMEDIATION

### Task 3.5: Fix Hardcoded Old-System Path in `bot/bot_keyboard.py`

- **Files Affected:** `bot/bot_keyboard.py`
- **Changes:** `Path("/root/projects/crypto-signal")` → `Path(__file__).resolve().parent.parent`
- **Risk Level:** MEDIUM
- **Status:** ✅ COMPLETED

### Task 3.6: Fix Old-System Paths in `scripts/health_monitor.py`

- **Files Affected:** `scripts/health_monitor.py`
- **Changes:** Auto-detect project from `__file__`, use TELEGRAM_BOT_TOKEN primary, BOT_TOKEN fallback
- **Risk Level:** MEDIUM
- **Status:** ✅ COMPLETED

### Task 3.7: Fix Old-System Paths in `scripts/monitor_bot.py`

- **Files Affected:** `scripts/monitor_bot.py`
- **Changes:** Env-var-configurable LOG_FILE, DATA_DIR with dynamic defaults
- **Risk Level:** MEDIUM
- **Status:** ✅ COMPLETED

### Task 3.8: Standardize `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` Env Vars

- **Files Affected:** `bot/bot_config.py`, `.env.example`, `utils/alerting.py`, `scripts/health_monitor.py`
- **Changes:** TELEGRAM_BOT_TOKEN primary / BOT_TOKEN fallback; TELEGRAM_CHAT_ID primary / OWNER_ID fallback
- **Risk Level:** MEDIUM
- **Validation:** Graceful degradation test passed; token priority confirmed
- **Status:** ✅ COMPLETED

### Task 3.9: Add `create_telegram_webhook_from_env()` to `utils/alerting.py`

- **Files Affected:** `utils/alerting.py`
- **Changes:** Added env-var-aware Telegram webhook helper
- **Risk Level:** MEDIUM
- **Status:** ✅ COMPLETED

---

## WAVE 4: LOW PRIORITY IMPROVEMENTS

### Task 4.1: Create CI/CD Pipeline
### Task 4.2: Integrate Backtesting with Live Trading
### Task 4.3: Implement Redis Caching
### Task 4.4: Refactor `core/core_ai.py`

---

## EXECUTION ORDER

```
WAVE 1 ─── Task 1.1 → Task 1.2 (parallel)                 ✅ COMPLETED
                │
WAVE 2 ─── Task 2.1 → Task 2.2 → Task 2.3 (sequential)    ✅ COMPLETED
                │
WAVE 3 ─── Tasks 3.1-3.4 (parallel, independent)           ✅ COMPLETED
                │
WAVE 3.5 ─ Tasks 3.5-3.9 (parallel, independent)           ✅ COMPLETED
                │
WAVE 4 ─── Tasks 4.1-4.4 (independent, can be parallel)    ⬜ DEFERRED
```

## VALIDATION GATES

After each wave, run:
1. `python3 health_check.py` — all checks pass
2. `python3 -m py_compile` on all changed files — zero syntax errors
3. `pytest tests/` if tests exist for changed modules — all pass
4. Verify script paths: `grep -n "crypto-signal" start_*.sh` shows only YJCryptoSignal paths

## ROLLBACK PROCEDURE

For any individual task:
```bash
# If git-tracked:
git checkout -- <file>

# If not git-tracked:
cp <file>.backup <file>
```

For full rollback:
```bash
systemctl stop yjcryptosignal-scanner yjcryptosignal-bot
# Original system remains running (cryptosignal-v1, cryptosignal-scanner)
```
