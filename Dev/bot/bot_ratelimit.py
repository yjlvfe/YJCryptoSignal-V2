"""
⏱️ CryptoSignal Bot — Rate Limiting, Pending State & Broadcast
Per-user rate limiting, pending entry/sale state, and global broadcast with rate tracking.
"""
import json
import time
import threading
import logging
from bot.bot_config import *

logger = logging.getLogger("yjcrypto-bot")

# ─── Global Rate Tracker — 429 prevention ───
_broadcast_timestamps = {}
_BROADCAST_INTERVAL = 0.5
_GLOBAL_MAX_MSG = 20
_GLOBAL_WINDOW = 30
_global_send_times = []
_global_rate_lock = threading.Lock()


def _check_global_rate() -> bool:
    """Enforce max 20 msgs / 30s window — sleep if exceeded."""
    global _global_send_times
    now = time.time()
    with _global_rate_lock:
        _global_send_times = [t for t in _global_send_times if now - t < _GLOBAL_WINDOW]
        if len(_global_send_times) >= _GLOBAL_MAX_MSG:
            oldest = _global_send_times[0] if _global_send_times else now
            wait = _GLOBAL_WINDOW - (now - oldest)
            if wait > 0:
                logger.warning(f"⏳ Global rate limit reached ({len(_global_send_times)}/{_GLOBAL_WINDOW}s) — waiting {wait:.1f}s")
                time.sleep(wait)
        _global_send_times.append(now)
    return True


def broadcast(text: str, reply_markup: dict = None, return_msg_ids: bool = False):
    """إرسال لجميع المشتركين — يدعم أزرار، الآن مع إيموجي Premium متحرك"""
    from bot.bot_admin import load_subscribers
    from bot.bot_messaging import send_msg_premium
    subs = load_subscribers()
    sent = 0
    msg_ids = {} if return_msg_ids else None
    for cid in subs:
        try:
            _check_global_rate()
            mid = send_msg_premium(cid, text, reply_markup=reply_markup)
            if mid:
                sent += 1
                if return_msg_ids:
                    msg_ids[cid] = mid
            time.sleep(_BROADCAST_INTERVAL)
        except Exception as e:
            logger.debug(f"Broadcast send error: {e}")
    if sent > 0:
        logger.info(f"Broadcast sent to {sent}/{len(subs)} subscribers")
    return msg_ids if return_msg_ids else None

# ─── Rate Limiting (thread-safe) ───
RATE_LOCK = threading.Lock()

def parse_time_window(s: str) -> int:
    """Parse '4h', '30m', '1m', '1d' to seconds"""
    s = s.strip().lower()
    if s.endswith('h'):
        return int(s[:-1]) * 3600
    elif s.endswith('m'):
        return int(s[:-1]) * 60
    elif s.endswith('d'):
        return int(s[:-1]) * 86400
    elif s.endswith('s'):
        return int(s[:-1])
    return 3600

def check_rate_limit(chat_id: int) -> dict:
    """
    Returns: {"allowed": bool, "remaining": int, "reset_in": str, "warning": str}
    """
    now = time.time()
    data = read_rate_config()
    window = data.get("window_seconds", 3600)
    max_req = data.get("max_per_window", 5)
    per_user = data.get("per_user", {})

    sid = str(chat_id)
    user_data = per_user.get(sid, {"count": 0, "window_start": now})

    if now - user_data.get("window_start", 0) > window:
        user_data = {"count": 0, "window_start": now}

    used = user_data.get("count", 0)
    remaining = max(0, max_req - used)
    allowed = remaining > 0

    warning = ""
    if used > 0 and max_req > 0:
        pct = used / max_req * 100
        if pct >= 80:
            reset_sec = int(window - (now - user_data.get("window_start", now)))
            warning = f"⚠️ تبقت {remaining} طلبة فقط. يتجدد بعد {reset_sec // 60} دقيقة."

    reset_in_sec = int(window - (now - user_data.get("window_start", now)))
    if reset_in_sec < 0:
        reset_in_sec = 0

    return {
        "allowed": allowed,
        "remaining": remaining,
        "reset_in": f"{reset_in_sec // 60} دقيقة",
        "warning": warning,
        "user_data": user_data,
        "sid": sid,
    }

def consume_rate_limit(chat_id: int):
    """Increment rate counter for a user"""
    now = time.time()
    with RATE_LOCK:
        data = read_rate_config()
        window = data.get("window_seconds", 3600)
        per_user = data.get("per_user", {})
        sid = str(chat_id)
        user_data = per_user.get(sid, {"count": 0, "window_start": now})

        if now - user_data.get("window_start", 0) > window:
            user_data = {"count": 0, "window_start": now}

        user_data["count"] = user_data.get("count", 0) + 1
        per_user[sid] = user_data
        data["per_user"] = per_user
        save_rate_config(data)


# ─── Pending entry price input ───
PENDING_ENTRY = {}
PENDING_ENTRY_LOCK = threading.Lock()

def get_pending_entry(chat_id: int) -> dict:
    with PENDING_ENTRY_LOCK:
        return PENDING_ENTRY.get(chat_id)

def set_pending_entry(chat_id: int, data: dict):
    with PENDING_ENTRY_LOCK:
        PENDING_ENTRY[chat_id] = data

def clear_pending_entry(chat_id: int):
    with PENDING_ENTRY_LOCK:
        PENDING_ENTRY.pop(chat_id, None)


# ─── Pending sale price input (تم البيع) ───
PENDING_SALE = {}
PENDING_SALE_LOCK = threading.Lock()

def get_pending_sale(chat_id: int) -> dict:
    with PENDING_SALE_LOCK:
        return PENDING_SALE.get(chat_id)

def set_pending_sale(chat_id: int, data: dict):
    with PENDING_SALE_LOCK:
        PENDING_SALE[chat_id] = data

def clear_sale_entry(chat_id: int):
    with PENDING_SALE_LOCK:
        PENDING_SALE.pop(chat_id, None)
