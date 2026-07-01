"""
🔐 CryptoSignal Bot — Admin & Slot Management
Thread-safe admin, subscriber, and slot operations.
"""
import json
import time
import threading
import logging
from bot.bot_config import *

logger = logging.getLogger("yjcrypto-bot")

# ─── Admin Management (thread-safe) ───
ADMINS_LOCK = threading.Lock()

def _read_admins() -> set:
    try:
        if ADMINS_FILE.exists():
            data = json.loads(ADMINS_FILE.read_text())
            return set(data.get("admins", [OWNER_ID])) | {OWNER_ID}
    except Exception as e:
        logger.debug(f"load_owners failed: {e}")
    return {OWNER_ID}

def _write_admins(admins: set):
    try:
        ADMINS_FILE.write_text(json.dumps({"admins": list(admins)}, indent=2))
    except Exception as e:
        logger.error(f"Failed to save admins: {e}")

def load_admins() -> set:
    with ADMINS_LOCK:
        return _read_admins()

def add_admin(uid: int) -> str:
    with ADMINS_LOCK:
        admins = _read_admins()
        if uid in admins:
            return f"⚠️ `{uid}` مشرف بالفعل."
        admins.add(uid)
        _write_admins(admins)
        return f"✅ تم رفع `{uid}` مشرف."


# ─── Subscriber Management (thread-safe) ───
SUBS_LOCK = threading.Lock()

def _read_subs() -> list:
    """داخلي — يقرأ الملف بدون قفل (المتصل يملك القفل)"""
    try:
        if SUBS_FILE.exists():
            return json.loads(SUBS_FILE.read_text())
    except Exception as e:
        logger.debug(f"load_slots failed: {e}")
    return []

def load_subscribers() -> list:
    with SUBS_LOCK:
        return _read_subs()

def save_subscribers(subs: list):
    with SUBS_LOCK:
        try:
            SUBS_FILE.write_text(json.dumps(subs))
        except Exception as e:
            logger.error(f"Failed to save subscribers: {e}")

def add_subscriber(chat_id: int, username: str = "", first_name: str = ""):
    with SUBS_LOCK:
        subs = _read_subs()
        if chat_id not in subs:
            subs.append(chat_id)
            try:
                SUBS_FILE.write_text(json.dumps(subs))
            except Exception as e:
                logger.error(f"Failed to save subscribers: {e}")
            logger.info(f"New subscriber: {chat_id} (@{username})")


# ─── Allow Slots (thread-safe) ───
SLOTS_LOCK = threading.Lock()

def _read_slots() -> dict:
    """{max_slots: 5, active: [chat_id1, chat_id2, ...]}"""
    try:
        if ALLOW_SLOTS_FILE.exists():
            return json.loads(ALLOW_SLOTS_FILE.read_text())
    except Exception as e:
        logger.debug(f"load_allow_slots failed: {e}")
    return {"max_slots": 0, "active": []}

def save_slots(data: dict):
    try:
        ALLOW_SLOTS_FILE.write_text(json.dumps(data, indent=2))
    except Exception as e:
        logger.error(f"Failed to save slots: {e}")

def try_assign_slot(chat_id: int) -> tuple:
    """
    Try to assign a user to an available slot.
    Returns (success: bool, message: str)
    - Already in slots → True
    - Slots available → True, assign
    - Slots full → False
    """
    with SLOTS_LOCK:
        data = _read_slots()
        active = data.get("active", [])
        max_slots = data.get("max_slots", 0)
        timestamps = data.get("assigned_at", {})

        if str(chat_id) in active_str(active):
            return True, "موجود"

        if max_slots <= 0:
            return False, "المساحة مقفولة حالياً. تواصل مع المشرف."

        if len(active) >= max_slots:
            oldest_ts = min(timestamps.values()) if timestamps else time.time()
            ago_min = int((time.time() - oldest_ts) / 60)
            ago_str = f"{ago_min} دقيقة" if ago_min < 60 else f"{ago_min // 60} ساعة"
            return False, f"⚠️ المقاعد ممتلئة ({max_slots}/{max_slots})\nأقدم مقعد محجوز منذ {ago_str}\nسيتم إشعارك عند توفر مقعد."

        active.append(chat_id)
        timestamps[str(chat_id)] = time.time()
        data["active"] = active
        data["assigned_at"] = timestamps
        save_slots(data)
        logger.info(f"✅ Slot assigned: {chat_id} ({len(active)}/{max_slots})")
        return True, "تم التفعيل ✅"

def active_str(active: list) -> list:
    """Convert all active IDs to strings for comparison"""
    return [str(a) for a in active]

def set_max_slots(number: int) -> str:
    """Admin sets max slots"""
    with SLOTS_LOCK:
        data = _read_slots()
        old = data.get("max_slots", 0)
        data["max_slots"] = number
        active = data.get("active", [])
        if len(active) > number:
            data["active"] = active[:number]
        save_slots(data)
        return f"✅ تم تعديل المساحة: {old} → {number}"

def add_uid_to_slots(uid: int) -> str:
    """Admin adds a specific user to slots"""
    with SLOTS_LOCK:
        data = _read_slots()
        active = data.get("active", [])
        if uid in active:
            return f"⚠️ `{uid}` لديه مقعد بالفعل."
        active.append(uid)
        data["active"] = active
        save_slots(data)
        return f"✅ تم إعطاء مقعد لـ `{uid}`."

def get_slots_status() -> str:
    """Get current slot usage with full details"""
    data = _read_slots()
    max_s = data.get("max_slots", 0)
    active = data.get("active", [])
    subs = load_subscribers()
    info = [
        f"🪑 **المساحة:** {len(active)}/{max_s} مستخدم",
        f"📋 **المشتركين:** {len(subs)}",
        f"👑 **المالك:** `{OWNER_ID}` (غير محسوب)",
    ]
    if active:
        info.append(f"👤 **المستخدمين النشطين:** {len(active)}")
    return "\n".join(info)

def remove_slot(chat_id: int) -> bool:
    """Remove a user from slots. Returns True if slot was freed."""
    with SLOTS_LOCK:
        data = _read_slots()
        active = data.get("active", [])
        max_s = data.get("max_slots", 0)
        timestamps = data.get("assigned_at", {})
        was_full = (len(active) >= max_s and max_s > 0)

        if chat_id in active:
            active.remove(chat_id)
            timestamps.pop(str(chat_id), None)
            data["active"] = active
            data["assigned_at"] = timestamps
            save_slots(data)
            logger.info(f"🪑 Slot removed: {chat_id} ({len(active)}/{max_s} remaining)")

            return True
    return False
