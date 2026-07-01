"""
🌐 YJCryptoSignal — AI HTTP Client
Session pooling, retry logic, and multi-provider failover calling.
"""
import time
import threading
import logging
import requests
from requests.adapters import HTTPAdapter
from typing import Optional

import core.providers as providers
from core.providers import (
    PROVIDERS, _p_lock, _p_key_idx, _p_rpm_calls, _p_rpd_calls,
    _p_fails, _p_last_fail, _p_healthy,
    AI_MAX_TOKENS, AI_TIMEOUT, AI_MAX_RETRIES, AI_RETRY_BASE_DELAY, AI_GLOBAL_GATE_SECONDS,
    _reset_stale_counts,
)

logger = logging.getLogger("yjcrypto-core-ai")

# ═══════════════ HTTP Session Pool ═══════════════
_http_session = None
_http_session_lock = threading.Lock()


def _get_session() -> requests.Session:
    global _http_session
    with _http_session_lock:
        if _http_session is None:
            session = requests.Session()
            adapter = HTTPAdapter(
                pool_connections=20,
                pool_maxsize=50,
                max_retries=0,
            )
            session.mount("https://", adapter)
            session.mount("http://", adapter)
            _http_session = session
        return _http_session


# ═══════════════ Retry Helper ═══════════════
def _request_with_retry(
    url: str,
    headers: dict,
    json_payload: dict,
    timeout: int,
    max_retries: int = AI_MAX_RETRIES,
    provider_name: str = "?"
) -> Optional[requests.Response]:
    session = _get_session()
    last_err = None

    for attempt in range(1, max_retries + 1):
        try:
            resp = session.post(url, headers=headers, json=json_payload, timeout=timeout)

            if resp.status_code == 200:
                if attempt > 1:
                    logger.info(f"🔁 {provider_name}: succeeded on attempt {attempt}/{max_retries}")
                return resp

            # Permanent client errors — fail fast
            if resp.status_code in (400, 401, 402, 403, 404):
                return resp

            # Transient errors — retry
            if resp.status_code in (408, 429, 500, 502, 503, 504) or resp.status_code >= 500:
                last_err = f"HTTP {resp.status_code}"

                # 429 = rate-limited / quota exhausted. Retrying the SAME provider
                # rarely helps and just delays failover. Cap 429 retries low so we
                # move to the next provider fast.
                effective_max = min(max_retries, 2) if resp.status_code == 429 else max_retries

                if attempt >= effective_max:
                    logger.warning(f"🔁 {provider_name}: gave up after {attempt} attempts ({last_err})")
                    return resp

                if resp.status_code == 429:
                    delay = min(30, AI_RETRY_BASE_DELAY * (2 ** (attempt - 1)))
                else:
                    delay = min(16, AI_RETRY_BASE_DELAY * (2 ** (attempt - 1)))

                logger.debug(f"🔁 {provider_name}: {last_err} (attempt {attempt}/{effective_max}), retry in {delay:.1f}s")
                time.sleep(delay)
                continue

            last_err = f"HTTP {resp.status_code}"
            if attempt >= max_retries:
                return resp
            delay = min(8, AI_RETRY_BASE_DELAY * (2 ** (attempt - 1)))
            time.sleep(delay)

        except requests.exceptions.Timeout as e:
            last_err = "timeout"
            if attempt >= max_retries:
                logger.warning(f"🔁 {provider_name}: gave up after {max_retries} attempts (timeout)")
                raise
            delay = min(8, AI_RETRY_BASE_DELAY * (2 ** (attempt - 1)))
            logger.debug(f"🔁 {provider_name}: timeout (attempt {attempt}/{max_retries}), retry in {delay:.1f}s")
            time.sleep(delay)

        except requests.exceptions.ConnectionError as e:
            last_err = f"connection: {str(e)[:50]}"
            if attempt >= max_retries:
                logger.warning(f"🔁 {provider_name}: gave up after {max_retries} attempts (connection)")
                raise
            delay = min(8, AI_RETRY_BASE_DELAY * (2 ** (attempt - 1)))
            logger.debug(f"🔁 {provider_name}: {last_err} (attempt {attempt}/{max_retries}), retry in {delay:.1f}s")
            time.sleep(delay)

        except Exception as e:
            logger.error(f"❌ {provider_name}: unexpected error: {e}")
            raise

    return None


# ═══════════════ Core Call Function ═══════════════
def call_ai(system: str, user: str, max_tokens: int = AI_MAX_TOKENS) -> Optional[str]:
    """Public API — Multi-provider failover with key rotation."""
    return _call_ai(system, user, max_tokens)


def _call_ai(system: str, user: str, max_tokens: int = AI_MAX_TOKENS) -> Optional[str]:
    if not PROVIDERS:
        logger.error("No AI providers configured!")
        return None

    # Global rate gate: minimum seconds between ANY provider call
    now = time.time()
    elapsed = now - providers._last_call_time
    if elapsed < AI_GLOBAL_GATE_SECONDS:
        time.sleep(AI_GLOBAL_GATE_SECONDS - elapsed)
    providers._last_call_time = time.time()

    now = time.time()
    _reset_stale_counts(now)

    errors = []

    for prov in PROVIDERS:
        name = prov["name"]

        # ═══ State checks (under lock) ═══
        with _p_lock:
            # Skip unhealthy (5-min cooldown for recovery)
            if not _p_healthy[name]:
                since_fail = now - _p_last_fail[name]
                if since_fail < 300:
                    errors.append(f"{name} 🔄 cooling down ({int(since_fail)}s)")
                    continue
                # Recovery attempt
                _p_healthy[name] = True
                _p_fails[name] = 0
                logger.info(f"🔄 Recovery attempt: {name}")

            # RPM check: count calls in last 60s
            cutoff = now - 60
            recent = _p_rpm_calls[name]
            _p_rpm_calls[name] = [t for t in recent if t > cutoff]
            if len(_p_rpm_calls[name]) >= prov.get("max_rpm", 30):
                errors.append(f"{name} ⏳ RPM limit")
                continue

            # RPD check
            if _p_rpd_calls[name] >= prov.get("max_rpd", 50000):
                errors.append(f"{name} 📆 daily limit")
                continue

            # Round-robin key selection
            keys = prov["keys"]
            if not keys:
                errors.append(f"{name} 🔑 no keys")
                continue
            ki = _p_key_idx[name]
            _p_key_idx[name] = (ki + 1) % len(keys)
            key = keys[ki]

            # Reserve this call
            _p_rpm_calls[name].append(now)
            _p_rpd_calls[name] += 1

        # ═══ Try the request (outside lock) with retries ═══
        model = prov["models"][0]
        # Cloudflare Workers AI uses /run/{model} and nests the response under "result"
        is_cloudflare = "cloudflare.com" in prov["base_url"]
        if is_cloudflare:
            url = f"{prov['base_url']}/{model}"
        else:
            url = f"{prov['base_url']}/chat/completions"

        try:
            resp = _request_with_retry(
                url=url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {key}"
                },
                json_payload={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user}
                    ],
                    "max_tokens": max_tokens,
                    "temperature": 0.2,
                },
                timeout=AI_TIMEOUT,
                max_retries=AI_MAX_RETRIES,
                provider_name=name,
            )
            if resp is None:
                errors.append(f"{name} ❌ no response")
                with _p_lock:
                    _p_fails[name] += 1
                    _p_last_fail[name] = now
                continue

            if resp.status_code == 200:
                data = resp.json()
                # Cloudflare nests the OpenAI-shaped payload under "result"
                if is_cloudflare and isinstance(data, dict) and "result" in data:
                    data = data["result"]
                msg = data["choices"][0].get("message", {})
                content = msg.get("content") or msg.get("reasoning_content") or msg.get("reasoning") or ""
                if content.strip():
                    with _p_lock:
                        _p_fails[name] = 0
                        _p_healthy[name] = True
                    logger.info(f"✅ AI: {name}/{model}")
                    return content.strip()

            # HTTP errors
            if resp.status_code == 429:
                errors.append(f"{name} ⏳ 429")
            elif resp.status_code == 402:
                errors.append(f"{name} 💸 402 credits")
            elif resp.status_code == 401:
                errors.append(f"{name} 🔑 401 bad key")
            else:
                err_body = resp.text[:80] if resp.text else "no body"
                errors.append(f"{name} HTTP {resp.status_code}")
                logger.debug(f"  {name} {resp.status_code}: {err_body}")

            with _p_lock:
                _p_fails[name] += 1
                _p_last_fail[name] = now
                if _p_fails[name] >= 3:
                    _p_healthy[name] = False
                    logger.warning(f"🔴 {name}: marked UNHEALTHY (3 fails)")

        except requests.exceptions.Timeout:
            errors.append(f"{name} ⏱️ timeout")
            with _p_lock:
                _p_fails[name] += 1
                _p_last_fail[name] = now

        except requests.exceptions.ConnectionError as e:
            errors.append(f"{name} 🔌 connection")
            logger.debug(f"  {name} connection: {e}")
            with _p_lock:
                _p_fails[name] += 1
                _p_last_fail[name] = now

        except Exception as e:
            errors.append(f"{name} ❌ {str(e)[:80]}")
            with _p_lock:
                _p_fails[name] += 1
                _p_last_fail[name] = now

        # Try next provider
        continue

    logger.warning(f"⚠️ AI: all providers failed — {'; '.join(errors)}")
    return None
