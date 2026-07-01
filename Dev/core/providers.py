"""
🔌 YJCryptoSignal — AI Provider Configuration & Runtime State
Manages provider loading from .env, key rotation, rate limits, and health tracking.
"""
import os
import json
import time
import threading
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger("yjcrypto-core-ai")

# ═══════════════ Load .env ═══════════════
def _load_env():
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ[key.strip()] = val.strip().strip('"').strip("'")

_load_env()

# ═══════════════ Global Config ═══════════════
AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "900"))
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "45"))
AI_MAX_RETRIES = int(os.getenv("AI_MAX_RETRIES", "10"))
AI_RETRY_BASE_DELAY = float(os.getenv("AI_RETRY_BASE_DELAY", "0.5"))
AI_GLOBAL_GATE_SECONDS = float(os.getenv("AI_GLOBAL_GATE_SECONDS", "2.0"))

# ═══════════════ Load Providers from .env ═══════════════
def _load_providers() -> List[Dict[str, Any]]:
    """Load all AI_PROVIDER_N_* configs from environment."""
    providers = []
    i = 1
    while True:
        name = os.getenv(f"AI_PROVIDER_{i}_NAME")
        if not name:
            break
        base_url = os.getenv(f"AI_PROVIDER_{i}_BASE_URL", "")
        models_str = os.getenv(f"AI_PROVIDER_{i}_MODELS", "")
        keys_str = os.getenv(f"AI_PROVIDER_{i}_KEYS", "")
        max_rpm = int(os.getenv(f"AI_PROVIDER_{i}_MAX_RPM", "30"))
        max_rpd = int(os.getenv(f"AI_PROVIDER_{i}_MAX_RPD", "5000"))
        priority = int(os.getenv(f"AI_PROVIDER_{i}_PRIORITY", str(i)))

        models = [m.strip() for m in models_str.split(",") if m.strip()]
        keys = [k.strip() for k in keys_str.split(",") if k.strip()]

        if not models:
            logger.warning(f"Provider {name}: no models defined, skipping")
            i += 1
            continue
        if not keys:
            logger.warning(f"Provider {name}: no API keys defined, skipping")
            i += 1
            continue

        providers.append({
            "name": name,
            "base_url": base_url.rstrip("/"),
            "models": models,
            "keys": keys,
            "max_rpm": max_rpm,
            "max_rpd": max_rpd,
            "priority": priority,
        })
        i += 1

    providers.sort(key=lambda p: p["priority"])
    logger.info(f"🤖 Loaded {len(providers)} AI providers from .env: {[p['name'] for p in providers]}")
    return providers


PROVIDERS = _load_providers()

if not PROVIDERS:
    logger.error("❌ NO AI PROVIDERS LOADED FROM .env — CHECK CONFIG!")
    PROVIDERS = []

# ═══════════════ Provider Runtime State ═══════════════
_p_lock = threading.Lock()
_p_key_idx = {p["name"]: 0 for p in PROVIDERS}
_p_rpm_calls = {p["name"]: [] for p in PROVIDERS}
_p_rpd_calls = {p["name"]: 0 for p in PROVIDERS}
_p_rpd_reset = {p["name"]: time.time() for p in PROVIDERS}
_p_fails = {p["name"]: 0 for p in PROVIDERS}
_p_last_fail = {p["name"]: 0.0 for p in PROVIDERS}
_p_healthy = {p["name"]: True for p in PROVIDERS}
_last_call_time = 0.0


def _reset_stale_counts(now: float):
    """Reset daily counters for providers with stale timestamps (>24h)"""
    for p in PROVIDERS:
        name = p["name"]
        if now - _p_rpd_reset.get(name, 0) > 86400:
            with _p_lock:
                _p_rpd_calls[name] = 0
                _p_rpd_reset[name] = now


def get_provider_status() -> dict:
    """Get current status of all AI providers for monitoring."""
    with _p_lock:
        return {
            name: {
                "healthy": _p_healthy[name],
                "consecutive_fails": _p_fails[name],
                "keys_available": len([p for p in PROVIDERS if p["name"] == name][0]["keys"]) if any(p["name"] == name for p in PROVIDERS) else 0,
                "rpm_used": len(_p_rpm_calls[name]),
                "rpd_used": _p_rpd_calls[name],
                "last_fail_ago": int(time.time() - _p_last_fail[name]) if _p_last_fail[name] > 0 else None,
            }
            for name in _p_healthy
        }


def force_provider_recovery(provider_name: str) -> bool:
    """Manually force recovery for a specific provider (admin use)."""
    with _p_lock:
        if provider_name in _p_healthy:
            _p_healthy[provider_name] = True
            _p_fails[provider_name] = 0
            _p_last_fail[provider_name] = 0
            logger.info(f"🔄 Manual recovery forced for {provider_name}")
            return True
    return False


def health_check() -> dict:
    """Quick health check — returns summary for /health endpoint."""
    healthy_count = sum(1 for h in _p_healthy.values() if h)
    total = len(PROVIDERS)
    return {
        "status": "OK" if healthy_count > 0 else "DEGRADED",
        "providers_total": total,
        "providers_healthy": healthy_count,
        "providers_unhealthy": total - healthy_count,
        "last_call_ago": int(time.time() - _last_call_time) if _last_call_time > 0 else None,
    }
