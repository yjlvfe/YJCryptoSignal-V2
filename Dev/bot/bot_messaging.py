"""CryptoSignal Bot — Messaging & Command Registration

Domain: message sending (Markdown, HTML, Premium emoji), API command registration.
Extracted from bot_handlers.py to reduce module size.
"""
import json, logging, re, time
import requests
from bot.bot_config import (
    API_BASE, OWNER_ID,
    PUBLIC_COMMAND_LIST, MEMBER_COMMAND_LIST, PREMIUM_COMMAND_LIST,
    ADMIN_COMMAND_LIST, OWNER_COMMAND_LIST,
)
from bot.bot_admin import load_admins, load_subscribers, save_subscribers, remove_slot

# 📊 Observability imports
try:
    from core.core_metrics import record_bot_message, HAS_BOT_METRICS
except ImportError:
    HAS_BOT_METRICS = False
    def record_bot_message(msg_type): pass

logger = logging.getLogger("yjcrypto-bot")


def send_msg(chat_id, text, parse_mode="Markdown", reply_markup: dict = None, reply_to_msg_id: int = None):
    """إرسال رسالة تليجرام مع fallback إذا فشل Markdown — يدعم أزرار
    Returns: message_id (int) on success, None on failure.
    يدعم reply_to_msg_id للرد على رسالة سابقة."""
    if not API_BASE:
        logger.warning("Cannot send message: API_BASE empty (TELEGRAM_BOT_TOKEN not configured)")
        return None
    # 🔍 Determine message type for metrics
    msg_type = "default"
    if "📊" in text or "🎯" in text or "🦅" in text:
        if "إشعار" in text or "توصيه" in text:
            msg_type = "signal"
        elif "التقرير" in text:
            msg_type = "daily_report"
        elif "قائمة" in text or "list" in text.lower():
            msg_type = "list"
        elif "خطأ" in text or "❌" in text or "🔴" in text:
            msg_type = "error"
        elif "إضافة" in text or "اشتراك" in text:
            msg_type = "subscription"

    try:
        if len(text) > 4000:
            text = text[:3990] + "\n\n... (مختصر)"

        payload = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup:
            payload["reply_markup"] = reply_markup
        if reply_to_msg_id:
            payload["reply_to_message_id"] = reply_to_msg_id

        # المحاولة الأولى مع Markdown
        if parse_mode:
            resp = requests.post(
                f"{API_BASE}/sendMessage",
                json=payload,
                timeout=15
            )
            data = resp.json()
            if data.get("ok"):
                # 📊 Record metrics
                if HAS_BOT_METRICS:
                    record_bot_message(msg_type)
                return data["result"].get("message_id")

            # إذا فشل بسبب Markdown — حاول بدون parse_mode
            error = data.get("description", "")
            if "parse" in error.lower() or "can't parse" in error.lower() or "markdown" in error.lower():
                logger.warning(f"Markdown error, retrying without parse_mode: {error[:100]}")
                payload.pop("parse_mode", None)
                resp = requests.post(
                    f"{API_BASE}/sendMessage",
                    json=payload,
                    timeout=15
                )
                data = resp.json()
                if data.get("ok"):
                    if HAS_BOT_METRICS:
                        record_bot_message(msg_type)
                    return data["result"].get("message_id")
                logger.error(f"Send still failed without markdown: {data}")
                return None

        # المحاولة بدون parse_mode
        payload.pop("parse_mode", None)
        resp = requests.post(
            f"{API_BASE}/sendMessage",
            json=payload,
            timeout=15
        )
        result = resp.json()
        if result.get("ok"):
            if HAS_BOT_METRICS:
                record_bot_message(msg_type)
            return result["result"].get("message_id")

        # 🛡️ 429 Rate Limited — انتظار تلقائي وإعادة المحاولة
        if result.get("error_code") == 429:
            retry_after = result.get("parameters", {}).get("retry_after", 5)
            logger.warning(f"⏳ 429 rate limited (send_msg) — retry after {retry_after}s")
            time.sleep(retry_after)
            resp = requests.post(f"{API_BASE}/sendMessage", json=payload, timeout=15)
            retry_data = resp.json()
            if retry_data.get("ok"):
                if HAS_BOT_METRICS:
                    record_bot_message(msg_type)
                return retry_data["result"].get("message_id")
            error_desc = retry_data.get('description', 'unknown')
        else:
            error_desc = result.get('description', 'unknown')
        if "Unauthorized" in error_desc:
            try:
                reg_resp = requests.get(f"{API_BASE}/getMe", timeout=10)
                if reg_resp.ok:
                    logger.info(f"🔑 Token re-registered during send — retrying...")
                    resp2 = requests.post(
                        f"{API_BASE}/sendMessage",
                        json=payload,
                        timeout=15
                    )
                    resp2_data = resp2.json()
                    if resp2_data.get("ok"):
                        return resp2_data["result"].get("message_id")
                    error_desc = resp2_data.get('description', 'unknown')
            except Exception as e:
                logger.debug(f"Telegram send error: {e}")
        if "blocked by the user" in error_desc.lower():
            subs = load_subscribers()
            if chat_id in subs:
                subs.remove(chat_id)
                save_subscribers(subs)
                logger.warning(f"Removed blocked user {chat_id} from subscribers")
            freed = remove_slot(chat_id)
            if freed:
                logger.info(f"🪑 Slot freed from blocked user {chat_id}")
        logger.error(f"Send error: {error_desc}")
        return None
    except Exception as e:
        logger.error(f"Send error: {e}")
        return None


# ═══════════════════════════════════════
# 📱 HTML send — مثالية للأيموجي المميز
# ═══════════════════════════════════════

def md_to_html(text: str) -> str:
    """تحويل Markdown بسيط إلى HTML
    **bold** → <b>bold</b>
    *italic* → <i>italic</i>
    `code` → <code>code</code>
    ```block``` → <pre>block</pre>
    """
    # Code blocks first (```...```) — نحميها من التعديل
    text = re.sub(r'```(\w*)\n?(.*?)```', r'<pre>\2</pre>', text, flags=re.DOTALL)
    # Inline code
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # Italic (single *)
    text = re.sub(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', r'<i>\1</i>', text)
    # Links [text](url)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    return text


def html_escape(text: str) -> str:
    """Escape HTML special characters — يحمي النص من كسر HTML"""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def send_msg_premium(chat_id, text, parse_mode=None, reply_markup: dict = None, reply_to_msg_id: int = None):
    """إرسال رسالة مع إيموجي متحرك (Premium) عبر entities.
    يحول Markdown + custom emoji إلى entities ويُرسل بدون parse_mode.
    """
    from bot.bot_custom_emoji import get_all_mappings, build_entities

    try:
        if len(text) > 4000:
            text = text[:3990] + "\n\n... (مختصر)"

        emoji_map = get_all_mappings()
        clean_text, entities = build_entities(text, emoji_map)

        payload = {"chat_id": chat_id, "text": clean_text}
        if entities:
            payload["entities"] = entities
        if reply_markup:
            payload["reply_markup"] = reply_markup
        if reply_to_msg_id:
            payload["reply_to_message_id"] = reply_to_msg_id

        # جرب مع entities (بدون parse_mode)
        resp = requests.post(f"{API_BASE}/sendMessage", json=payload, timeout=15)
        data = resp.json()
        if data.get("ok"):
            return data["result"].get("message_id")

        # 🛡️ 429 Rate Limited — انتظار تلقائي
        if data.get("error_code") == 429:
            retry_after = data.get("parameters", {}).get("retry_after", 5)
            logger.warning(f"⏳ 429 rate limited (premium) — retry after {retry_after}s")
            time.sleep(retry_after)
            resp = requests.post(f"{API_BASE}/sendMessage", json=payload, timeout=15)
            data = resp.json()
            if data.get("ok"):
                return data["result"].get("message_id")

        # فشل بسبب entities — حاول بدون entities (نص عادي)
        error = data.get("description", "")
        logger.warning(f"Premium entities error ({error[:80]}), retrying plain text...")
        payload.pop("entities", None)
        resp = requests.post(f"{API_BASE}/sendMessage", json=payload, timeout=15)
        data = resp.json()
        if data.get("ok"):
            return data["result"].get("message_id")

        # 🛡️ 429 Rate Limited — بعد entities retry
        if data.get("error_code") == 429:
            retry_after = data.get("parameters", {}).get("retry_after", 5)
            logger.warning(f"⏳ 429 rate limited (premium plain) — retry after {retry_after}s")
            time.sleep(retry_after)
            resp = requests.post(f"{API_BASE}/sendMessage", json=payload, timeout=15)
            data = resp.json()
            if data.get("ok"):
                return data["result"].get("message_id")

        logger.error(f"Send premium failed: {data}")
        return None
    except Exception as e:
        logger.error(f"Send premium error: {e}")
        return None


def send_msg_html(chat_id, text, reply_markup: dict = None, reply_to_msg_id: int = None):
    """إرسال رسالة تليجرام بصيغة HTML"""
    try:
        if len(text) > 4000:
            text = text[:3990] + "\n\n... (مختصر)"

        html_text = md_to_html(text)

        payload = {"chat_id": chat_id, "text": html_text, "parse_mode": "HTML"}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        if reply_to_msg_id:
            payload["reply_to_message_id"] = reply_to_msg_id

        resp = requests.post(f"{API_BASE}/sendMessage", json=payload, timeout=15)
        data = resp.json()
        if data.get("ok"):
            return data["result"].get("message_id")

        error = data.get("description", "")
        logger.warning(f"HTML send error, retrying without parse_mode: {error[:100]}")
        payload.pop("parse_mode", None)
        resp = requests.post(f"{API_BASE}/sendMessage", json=payload, timeout=15)
        data = resp.json()
        if data.get("ok"):
            return data["result"].get("message_id")
        logger.error(f"Send still failed without html: {data}")
        return None

    except Exception as e:
        logger.error(f"Send HTML error: {e}")
        return None


def _api_set_commands(commands: list, scope: dict) -> bool:
    """استدعاء setMyCommands في تيليجرام — بدون language_code عشان يظهر للكل."""
    try:
        payload = [{"command": c, "description": d} for c, d in commands]
        resp = requests.post(
            f"{API_BASE}/setMyCommands",
            json={"commands": payload, "scope": scope},
            timeout=10
        )
        return resp.json().get("ok", False)
    except Exception as e:
        logger.error(f"setMyCommands failed: {e}")
        return False


def _api_delete_commands(scope: dict) -> bool:
    """استدعاء deleteMyCommands — مسح الأوامر القديمة."""
    try:
        resp = requests.post(
            f"{API_BASE}/deleteMyCommands",
            json={"scope": scope},
            timeout=10
        )
        return resp.json().get("ok", False)
    except Exception as e:
        logger.error(f"deleteMyCommands failed: {e}")
        return False


def set_user_commands(chat_id: int, role: str) -> bool:
    """تعيين أوامر البوت لمستخدم محدد حسب رتبته.
    
    يستخدم BotCommandScopeChat(chat_id=X) — كل مستخدم يشوف أوامره فقط.
    
    الأدوار: owner | admin | premium | member
    الزوار (public) لا يُستخدم لهم هذا الاستدعاء — يعتمدون على default scope.
    """
    role_map = {
        "member": MEMBER_COMMAND_LIST,
        "premium": PREMIUM_COMMAND_LIST,
        "admin": ADMIN_COMMAND_LIST,
        "owner": OWNER_COMMAND_LIST,
    }
    cmds = role_map.get(role)
    if not cmds:
        logger.warning(f"Unknown role '{role}' for {chat_id}")
        return False
    
    scope = {"type": "chat", "chat_id": chat_id}
    ok = _api_set_commands(cmds, scope)
    if ok:
        logger.info(f"📋 Commands set — {chat_id} ({role}): {len(cmds)} commands")
    else:
        logger.warning(f"⚠️ Failed to set commands for {chat_id} ({role})")
    return ok


def init_all_commands():
    """
    تُستدعى عند بدء التشغيل فقط.
    1. يمسح الأوامر القديمة من default scope.
    2. يعيّن الأوامر العامة (default) ليظهر 5 أوامر للزوار الجدد.
    3. يعيد تعيين أوامر كل مشترك / مشرف / مالك حسب scope الخاص به.
    """
    logger.info("📋 Initializing bot commands...")
    
    # 1️⃣ امسح الأوامر القديمة من default scope (بدون لغة + لغة ar القديمة)
    _api_delete_commands({"type": "default"})
    try:
        requests.post(f"{API_BASE}/deleteMyCommands",
                     json={"scope": {"type": "default"}, "language_code": "ar"},
                     timeout=10)
    except Exception as e:
        logger.debug(f"Old AR commands cleanup: {e}")  # تنظيف الأوامر القديمة
    
    # 2️⃣ عيّن الأوامر العامة — لكل الزوار
    _api_set_commands(PUBLIC_COMMAND_LIST, {"type": "default"})
    logger.info(f"  ✅ Default scope: {len(PUBLIC_COMMAND_LIST)} public commands")
    
    # 3️⃣ أعِد تعيين أوامر كل المشتركين
    admins = load_admins()
    subs = load_subscribers()
    done = set()
    
    # المالك أولاً
    set_user_commands(OWNER_ID, "owner")
    done.add(OWNER_ID)
    
    # المشرفين
    for uid in admins:
        if uid not in done:
            set_user_commands(uid, "admin")
            done.add(uid)
    
    # باقي المشتركين
    for uid in subs:
        if uid not in done:
            set_user_commands(uid, "member")
            done.add(uid)
    
    logger.info(f"📋 Commands initialized: {len(done)} users total")
