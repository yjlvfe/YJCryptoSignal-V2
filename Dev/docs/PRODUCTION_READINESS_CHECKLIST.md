<!--
===========================================================
CRYPTOSIGNAL v3.0 — PRODUCTION READINESS CHECKLIST
===========================================================

Complete pre-deployment validation checklist for YJCryptoSignal v3.0
All items MUST pass before production deployment.

Version: 3.0.0
Date: 2026-06-17
Reviewer: _________________
Approval: _________________
-->

# ✅ CryptoSignal v3.0 — Production Readiness Checklist

---

## 📊 Overview

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Test Coverage (Critical Paths) | ≥ 80% | ___% | ☐ |
| Load Test (1000 RPS) | < 100ms p99 | ___ms | ☐ |
| Chaos Engineering | All pass | ___/11 | ☐ |
| Security Scan | 0 Critical | ___ | ☐ |
| Documentation | 100% | ___% | ☐ |
| Runbooks | All tested | ___/14 | ☐ |

---

## 🏗️ Infrastructure & Deployment

### [ ] Container/VM Preparation
- [ ] Base OS: Ubuntu 22.04+ / Debian 12+
- [ ] Python 3.11+ installed
- [ ] Virtual environment created at `/root/projects/YJCryptoSignal/venv`
- [ ] All dependencies installed (`pip install -r requirements.txt`)
- [ ] Node.js 18+ (for browser tools if needed)
- [ ] Sufficient disk space (> 5GB free)
- [ ] Sufficient memory (> 2GB RAM)
- [ ] Swap configured (2GB minimum)

### [ ] Network Configuration
- [ ] Outbound HTTPS (443) to AI providers
- [ ] Outbound HTTPS (443) to exchanges (bybit, gateio, kucoin)
- [ ] Outbound HTTPS (443) to Telegram API
- [ ] Localhost ports 9090, 9091 accessible for Prometheus
- [ ] No inbound ports required (prometheus pulls)
- [ ] DNS resolution working for all APIs

### [ ] Storage
- [ ] Data directory `/root/.crypto-signal-bot` exists with correct permissions
- [ ] Logs directory `/root/projects/YJCryptoSignal/logs` exists
- [ ] Backup directory configured
- [ ] Disk monitoring alert at 80% usage

### [ ] Systemd Services
- [ ] `yjcryptosignal-scanner.service` installed and enabled
- [ ] `yjcryptosignal-bot.service` installed and enabled
- [ ] Services start automatically on boot
- [ ] Restart policy: `Restart=always`, `RestartSec=10`
- [ ] Log output to `/root/projects/YJCryptoSignal/logs/`
- [ ] Resource limits configured (MemoryLimit, CPUQuota if needed)
- [ ] Watchdog cron job installed (60s interval)

---

## 🔐 Security

### [ ] Credentials Management
- [ ] `.env` file permissions: `chmod 600`
- [ ] BOT_TOKEN configured and valid
- [ ] ADMIN_ID configured correctly
- [ ] At least 3 AI provider API keys configured
- [ ] API keys NOT committed to git
- [ ] API keys rotated within last 30 days
- [ ] No hardcoded secrets in codebase

### [ ] Access Control
- [ ] Service runs as non-root user (recommended)
- [ ] File ownership: `root:root` or dedicated user
- [ ] SSH access restricted to key-based auth
- [ ] Firewall: Only SSH (22) inbound allowed
- [ ] Fail2ban configured for SSH

### [ ] Network Security
- [ ] Metrics endpoints bound to 127.0.0.1 only
- [ ] No database exposed externally
- [ ] Telegram webhook uses secret token (if webhook mode)
- [ ] TLS certificates for any external endpoints

### [ ] Compliance
- [ ] No PII logged (user IDs are numeric only)
- [ ] Trade data encrypted at rest (if required)
- [ ] Audit logging for admin actions
- [ ] Incident response plan documented

---

## 🧪 Testing & Quality Assurance

### [ ] Unit Tests
- [ ] `tests/test_core_metrics.py` — 24 tests PASS
- [ ] `tests/test_core_logging.py` — 24 tests PASS
- [ ] Core modules compile without errors
- [ ] All imports resolve correctly

### [ ] Integration Tests
- [ ] Full scan cycle test passes
- [ ] Trade lifecycle test passes
- [ ] Regime → Weight learning flow works
- [ ] Metrics + Logging integration works
- [ ] Alerting integration works

### [ ] Load Testing
- [ ] **Metrics Load Test**: 10,000 ops @ 50 workers
  - Target: > 5,000 ops/sec, p99 < 50ms
  - Actual: _____ ops/sec, p99 _____ms
- [ ] **Logging Load Test**: 5,000 log entries @ 20 workers
  - Target: > 2,000 ops/sec, p99 < 100ms
  - Actual: _____ ops/sec, p99 _____ms
- [ ] **Alerting Load Test**: 1000 alerts @ 10 workers
  - Target: > 200 ops/sec, p99 < 500ms
  - Actual: _____ ops/sec, p99 _____ms
- [ ] **Mixed Workload**: 10,000 ops (scan:ai:trade = 5:3:2)
  - Target: > 3,000 ops/sec
  - Actual: _____ ops/sec

### [ ] Chaos Engineering
- [ ] **AI Provider Failure** (openai 100% fail) — Fallback works
- [ ] **AI Partial Failure** (deepseek 30% fail) — Retries work
- [ ] **AI Rate Limit** (groq 50% rate limit) — Key rotation works
- [ ] **Exchange Failure** (bybit 100% fail) — Fallback to gateio/kucoin
- [ ] **Exchange Intermittent** (gateio 20% fail) — Graceful degradation
- [ ] **Exchange Latency** (kucoin 5s spike) — Timeout & fallback
- [ ] **Network Partition** (5s total block) — Queue & retry
- [ ] **Memory Pressure** (500MB) — No crash, slow acceptable
- [ ] **CPU Spike** (5s at 80%) — Responsiveness maintained
- [ ] **All 10 experiments PASS**

### [ ] Performance Benchmarks
- [ ] Scan cycle: < 30 seconds for 150 symbols
- [ ] AI analysis: < 5 seconds per symbol (parallel)
- [ ] Trade open/close: < 100ms
- [ ] Metrics endpoint: < 50ms
- [ ] Health endpoint: < 10ms
- [ ] Memory stable over 24h (no leaks)
- [ ] CPU < 50% average during scan

---

## 📈 Monitoring & Observability

### [ ] Prometheus Metrics
- [ ] Scanner metrics on :9090/metrics
- [ ] Bot metrics on :9091/metrics
- [ ] All 30+ predefined metrics exporting
- [ ] Custom labels working (provider, model, symbol, etc.)
- [ ] Prometheus scrape config tested
- [ ] Metrics retention: 15d minimum

### [ ] Health Endpoints
- [ ] `/health` returns 200 with JSON status
- [ ] `/ready` returns 200 when fully initialized
- [ ] Both endpoints on scanner (9090) and bot (9091)

### [ ] Structured Logging
- [ ] JSON format output verified
- [ ] All 7 component loggers working
- [ ] Context propagation working (thread-local)
- [ ] Exception tracebacks in JSON
- [ ] Log rotation configured (logrotate)
- [ ] ELK/Datadog/Loki ingestion tested

### [ ] Alerting
- [ ] AlertManager initialized
- [ ] Telegram webhook configured (if used)
- [ ] Discord webhook configured (if used)
- [ ] Slack webhook configured (if used)
- [ ] Deduplication working (60s window)
- [ ] Retry logic working (3 retries, exponential backoff)
- [ ] Filter by level/source/tags working
- [ ] Domain alerts tested:
  - [ ] AI failure alert
  - [ ] Exchange failure alert
  - [ ] Trade SL hit alert
  - [ ] Trade TP hit alert
  - [ ] Scanner stalled alert
  - [ ] High error rate alert

### [ ] Dashboards
- [ ] Grafana dashboard imported
- [ ] All panels showing data
- [ ] Alert rules configured in Grafana/Prometheus
- [ ] Notification channels tested

---

## 🤖 Trading Logic Validation

### [ ] Signal Generation
- [ ] Multi-TF prefilter working (alignment ≥ 2)
- [ ] CHOCH/BOS detection working (Phase 3)
- [ ] Order block + volume confirmation working
- [ ] FVG mitigation tracking working
- [ ] Breaker block detection working
- [ ] Liquidity sweep validation working
- [ ] ATR-based duration calculation (not fixed 12h)
- [ ] SL < 3% enforced
- [ ] R:R ≥ 1:1 enforced (SL < TP1)
- [ ] 3 Targets from AI only (no auto-generation)
- [ ] Confidence threshold enforced (default 70%)

### [ ] Trade Management
- [ ] MAX_ACTIVE_TRADES limit enforced (10)
- [ ] 1h signal cache working
- [ ] 30m cooldown per symbol working
- [ ] Active trade block working
- [ ] Trailing stop updates working
- [ ] Trade persistence across restarts
- [ ] PnL calculation correct (simple sum, not compounded)

### [ ] Learning System
- [ ] AdaptiveLearner recording trades
- [ ] Expectancy calculation correct
- [ ] Kill switch activates on sustained losses
- [ ] RegimeLearner tracking per-regime performance
- [ ] WeightLearner updating from expectancy
- [ ] Intra-cluster cap working
- [ ] Inter-cluster bonus working
- [ ] Minimum weight floor enforced

---

## 🚀 Deployment Procedures

### [ ] Pre-Deployment
- [ ] All tests PASS (unit + integration)
- [ ] Load test results meet targets
- [ ] Chaos experiments all PASS
- [ ] Security scan clean
- [ ] Documentation updated
- [ ] Runbooks reviewed
- [ ] Rollback plan documented
- [ ] Stakeholder sign-off

### [ ] Deployment Steps
1. [ ] Backup current version
   ```bash
   cp -r /root/projects/YJCryptoSignal /root/projects/YJCryptoSignal.backup.$(date +%Y%m%d)
   ```
2. [ ] Deploy new code
3. [ ] Update .env if needed
4. [ ] Run database migrations (if any)
5. [ ] Restart scanner service
6. [ ] Verify scanner health
7. [ ] Restart bot service
8. [ ] Verify bot health
9. [ ] Run smoke tests
10. [ ] Monitor for 30 minutes

### [ ] Post-Deployment
- [ ] Health check PASS
- [ ] First scan cycle completes
- [ ] First signal generated (if market conditions allow)
- [ ] Metrics flowing to Prometheus
- [ ] Logs structured and parseable
- [ ] Alerts not firing falsely
- [ ] Dashboard showing green

### [ ] Rollback Plan
- [ ] Stop services: `systemctl stop yjcryptosignal-scanner yjcryptosignal-bot`
- [ ] Restore backup: `cp -r /root/projects/YJCryptoSignal.backup.* /root/projects/YJCryptoSignal`
- [ ] Start services
- [ ] Verify health
- [ ] Time to rollback: < 5 minutes

---

## 📋 Operational Readiness

### [ ] Runbooks
- [ ] RB-001 Scanner Down — Tested
- [ ] RB-002 Bot Down — Tested
- [ ] RB-003 AI All Providers Failed — Tested
- [ ] RB-004 SL Hit Storm — Tested
- [ ] RB-005 High Error Rate — Tested
- [ ] RB-006 AI Provider Degraded — Tested
- [ ] RB-007 Exchange API Issues — Tested
- [ ] RB-008 Low Signal Volume — Tested
- [ ] RB-009 Kill Switch Active — Tested
- [ ] RB-010 High Memory — Tested
- [ ] RB-011 Config Reload — Tested
- [ ] RB-012 Key Rotation — Tested
- [ ] RB-013 Backup Restore — Tested
- [ ] RB-014 Version Upgrade — Tested

### [ ] On-Call
- [ ] Primary on-call identified
- [ ] Secondary on-call identified
- [ ] Escalation path documented
- [ ] PagerDuty/OpsGenie/Telegram alerts configured
- [ ] Runbook access verified for on-call

### [ ] Maintenance Windows
- [ ] Scheduled maintenance window defined
- [ ] Automated updates disabled during trading hours
- [ ] Key rotation schedule documented
- [ ] Log cleanup schedule configured

---

## ✅ Final Sign-Off

| Checklist Section | Reviewer | Date | Signature |
|-------------------|----------|------|-----------|
| Infrastructure & Deployment | | | |
| Security | | | |
| Testing & QA | | | |
| Monitoring & Observability | | | |
| Trading Logic Validation | | | |
| Deployment Procedures | | | |
| Operational Readiness | | | |

### Overall Status

- [ ] **APPROVED FOR PRODUCTION** — All items PASS
- [ ] **CONDITIONAL APPROVAL** — Minor items open (list below)
- [ ] **REJECTED** — Critical items failing

**Open Items:**
1. _______________________________________________
2. _______________________________________________
3. _______________________________________________

**Approved By:** _________________________ **Date:** _______________

---

*Checklist Version: 3.0.0 | Last Updated: 2026-06-17*