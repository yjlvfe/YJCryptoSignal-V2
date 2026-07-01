# ⚠️ YJCryptoSignal — Risk & Collision Report

**Date:** 2026-06-18  
**Risk Level:** HIGH (Critical deployment bugs present)

---

## 1. COLLISION AUDIT

### 1.1 Port Conflicts

| Port | Old System | New System | Conflict? |
|------|-----------|------------|-----------|
| 9090 | Not used | Scanner Metrics `/metrics`, `/health`, `/ready` | ✅ Unique to new system |
| 9091 | Not used | Bot Metrics `/metrics`, `/health`, `/ready` | ✅ Unique to new system |
| Telegram API | 443 (outbound) | 443 (outbound) | ✅ No conflict (uses different BOT_TOKEN) |

**Verdict:** No port conflicts. Both systems can run simultaneously.

### 1.2 Database / Data Directory Conflicts

| Resource | Old System | New System | Conflict? |
|----------|-----------|------------|-----------|
| Trades file | `/root/.crypto-signal-bot/trades.json` | `/root/.yjcryptosignal-bot/trades.json` | ✅ Separate |
| Subscribers | `/root/.crypto-signal-bot/subscribers.json` | `/root/.yjcryptosignal-bot/subscribers.json` | ✅ Separate |
| Broadcast cache | `/root/.crypto-signal-bot/broadcast_cache.json` | `/root/.yjcryptosignal-bot/broadcast_cache.json` | ✅ Separate |
| Signal messages | `/root/.crypto-signal-bot/signal_messages.json` | `/root/.yjcryptosignal-bot/signal_messages.json` | ✅ Separate |
| Progress file | `/root/.crypto-signal-bot/universal_progress.json` | `/root/.yjcryptosignal-bot/universal_progress.json` | ✅ Separate |
| User roles | `/root/.crypto-signal-bot/user_roles.json` | `/root/.yjcryptosignal-bot/user_roles.json` | ✅ Separate |
| Trades history | `/root/.crypto-signal-bot/trades_history.json` | `/root/.yjcryptosignal-bot/trades_history.json` | ✅ Separate |
| Runtime logs | `/root/.crypto-signal-bot/bot_runtime.log` | `/root/.yjcryptosignal-bot/bot_runtime.log` | ✅ Separate |

**Verdict:** Data directories are properly isolated (verified in DEPLOYMENT_COMPLETE.md).

### 1.3 Lock File Conflicts

| Lock File | Old System | New System | Conflict? |
|-----------|-----------|------------|-----------|
| Bot lock | `/tmp/cryptosignal.lock` | `/tmp/yjcryptosignal-bot.lock` | ✅ Separate |
| Scanner lock | `/tmp/cryptosignal-scanner.lock` | `/tmp/yjcryptosignal-scanner.lock` | ✅ Separate |

**Verdict:** Lock files are properly isolated.

### 1.4 Environment Variable Conflicts

| Variable | Old System | New System | Conflict? |
|----------|-----------|------------|-----------|
| `BOT_TOKEN` | `8771994519:AAHD...` | `8865442794:AAHK...` | ✅ Different tokens |
| `AI_MAX_TOKENS` | Not set (uses `CRYPTOSIGNAL_AI_MAX_TOKENS=900`) | `900` | ✅ Different variable names |
| `AI_TIMEOUT` | Not set (uses `CRYPTOSIGNAL_AI_TIMEOUT=90`) | `45` (seconds) | ✅ Different variable names |
| `DATA_DIR` | Not set | **Could conflict** | ⚠️ See below |
| `CRYPTOSIGNAL_AI_*` | `CRYPTOSIGNAL_AI_MAX_TOKENS=900`, `CRYPTOSIGNAL_AI_TIMEOUT=90` | Not used | ✅ Separate namespaces |

**Risk:** The new system's `bot_config.py` uses `DATA_DIR` environment variable. If both systems share the same environment (e.g., systemd, Docker), and one sets `DATA_DIR` globally, the other could pick it up. This is mitigated by systemd service files using `Environment=` directives.

**Verdict:** Environment variables are largely separated by naming convention, with one minor risk around `DATA_DIR`.

### 1.5 Process/Services Conflicts

| Service | Old | New | Conflict? |
|---------|-----|-----|-----------|
| Bot service | `cryptosignal-v1.service` | `yjcryptosignal-bot.service` | ✅ Separate |
| Scanner service | `cryptosignal-scanner.service` | `yjcryptosignal-scanner.service` | ✅ Separate |

**Verdict:** Services are named differently — no conflict.

### 1.6 File Path Conflicts

| Path | Conflict? |
|------|-----------|
| `/root/projects/crypto-signal/` | ✅ Only old system |
| `/root/projects/YJCryptoSignal/` | ✅ Only new system |
| `/root/.crypto-signal-bot/` | ✅ Only old system |
| `/root/.yjcryptosignal-bot/` | ✅ Only new system |
| Symlink `/opt/cryptosignal-bus/client.py` | **⚠️ SHARED** — both systems reference this |

**Verdict:** File paths are isolated except the shared `bus_client.py` symlink.

---

## 2. CRITICAL RISKS

### RISK-01: Startup Scripts Execute Old System Code ⚠️ CRITICAL

**Risk Level:** CRITICAL  
**Probability:** HIGH  
**Impact:** Catastrophic  
**Description:** Both `start_bot.sh` and `start_v2_scanner.sh` in the new system directory `cd` to the OLD system path (`/root/projects/crypto-signal`). Running these scripts from YJCryptoSignal would execute the old bot code against the old data directory while the operator thinks they're running the new system.

**Mitigation:** Fix the startup scripts to use the correct paths.

### RISK-02: Legacy Bot Files Cause Execution Confusion ⚠️ HIGH

**Risk Level:** HIGH  
**Probability:** MEDIUM  
**Impact:** HIGH  
**Description:** The new system has both legacy `bot/main.py` (points to old DATA_DIR) and new `bot/bot_main.py`. If someone runs `python3 bot/main.py` or the systemd service still references the old entry point, the old bot will start instead of the new one.

**Mitigation:** Either remove legacy files or ensure systemd services point to the correct entry point.

### RISK-03: Shared Symlink Bus Client ⚠️ MEDIUM

**Risk Level:** MEDIUM  
**Probability:** LOW  
**Impact:** HIGH  
**Description:** Both systems share `/opt/cryptosignal-bus/client.py` via symlink. If this file is updated for one system's needs, it could break the other.

**Mitigation:** Copy the client to each project's directory and have independent copies.

### RISK-04: No Authentication on Metrics Endpoints ⚠️ MEDIUM

**Risk Level:** MEDIUM  
**Probability:** LOW (internal network)  
**Impact:** MEDIUM  
**Description:** Metrics endpoints on ports 9090 and 9091 are open to the network. Anyone who can reach these ports can read Prometheus metrics (which may include trade counts, signal data, etc.).

**Mitigation:** Add authentication or restrict to localhost.

### RISK-05: `logger` Undefined in Health Check ⚠️ HIGH

**Risk Level:** HIGH  
**Probability:** HIGH (will fail on corrupt trade file)  
**Impact:** MEDIUM  
**Description:** In `health_check.py` line 58 and 135, `logger` is used but never defined (only `logging` module is imported). Any error reading `trades.json` will raise a NameError instead of logging.

```python
except Exception as e:
    logger.error(f"Failed to read trades file: {e}", exc_info=True)  # NameError!
```

**Mitigation:** Initialize a logger or use `logging` module directly.

---

## 3. OPERATIONAL RISKS

| Risk ID | Description | Level | Mitigation |
|---------|-------------|-------|------------|
| OPS-01 | No log rotation for JSON logs could fill disk | MEDIUM | Add logrotate config |
| OPS-02 | No backup of trade data before cutover | HIGH | Implement backup scripts |
| OPS-03 | No monitoring dashboards for metrics | MEDIUM | Configure Grafana |
| OPS-04 | No alerting rules for system health | MEDIUM | Add alertmanager rules |
| OPS-05 | Manual deployment only (no CI/CD) | LOW | Set up GitHub Actions |

---

## 4. SECURITY RISKS

| Risk ID | Description | Level | Mitigation |
|---------|-------------|-------|------------|
| SEC-01 | API keys in plaintext `.env` | HIGH | Use secrets manager or encrypted vault |
| SEC-02 | Hardcoded OWNER_ID (528864559) | LOW | Move to .env |
| SEC-03 | `except: pass` patterns hide errors | MEDIUM | Audit and fix bare excepts |
| SEC-04 | No Telegram webhook validation | MEDIUM | Verify Telegram origin |
| SEC-05 | No input sanitization on commands | MEDIUM | Validate all user input |

---

## 5. COLLISION SUMMARY

| Category | Status |
|----------|--------|
| Ports | ✅ No conflicts |
| Data Directories | ✅ Isolated |
| Lock Files | ✅ Isolated |
| Environment Variables | ⚠️ Minor risk (DATA_DIR) |
| Services | ✅ Separate |
| File Paths | ⚠️ Startup scripts point to wrong dir |
| Shared Resources | ⚠️ bus_client.py symlink shared |

**Overall Risk Level:** HIGH — primarily due to the critical startup script bugs and legacy file confusion that could cause the wrong system to execute.
