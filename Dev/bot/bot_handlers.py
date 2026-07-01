"""CryptoSignal Bot — Telegram Handlers + User Management"""
import sys, os, json, time, threading, re, logging, atexit
from pathlib import Path
import requests
from bot.bot_config import *
from trade.trade_tracker import get_active_trades, add_trade, check_trades, load_trades, save_trades, format_trades_list, update_current_prices, cleanup_trades, MAX_TRADES
from bot.bot_keyboard import build_list_keyboard, build_detail_keyboard, build_back_keyboard, format_trade_detail_text, analyze_support_levels
from trade.trade_userlists import get_user_list, add_to_user_list, remove_from_user_list, subscribe_to_trade, unsubscribe_from_trade, get_trade_subscribers, cleanup_closed_trade, get_all_user_entry_prices, get_user_entry_price, set_user_entry_price, set_user_target_count, get_user_target_count, has_tracking_data, is_tracking_active, mark_user_tracking_complete, mark_user_target_hit, get_active_trackers_for_symbol, cleanup_user_tracking, record_sale, get_user_sales, get_user_sales_summary

# 📊 Observability imports
try:
    from core.core_metrics import record_bot_message, record_bot_command, HAS_BOT_METRICS
except ImportError:
    HAS_BOT_METRICS = False
    def record_bot_message(msg_type): pass
    def record_bot_command(cmd): pass

logger = logging.getLogger("yjcrypto-bot")

# ─── Backward-compat re-exports from bot_admin ───
from bot.bot_admin import (
    ADMINS_LOCK, SUBS_LOCK, SLOTS_LOCK,
    _read_admins, _write_admins, load_admins, add_admin,
    _read_subs, load_subscribers, save_subscribers, add_subscriber,
    _read_slots, save_slots, try_assign_slot, active_str,
    set_max_slots, add_uid_to_slots, get_slots_status, remove_slot,
)

def _notify_one_slot_opened(max_s: int, active_count: int):
    """Notify subscribers without slots that exactly 1 slot opened"""
    subs = load_subscribers()
    active = _read_slots().get("active", [])
    admins = load_admins()
    for cid in subs:
        if cid not in active and cid not in admins:
            try:
                send_msg(cid, f"🪑 **تم توفر مقعد!**\n\nالمقاعد: {active_count}/{max_s}\nاستخدم /start للحجز.")
                time.sleep(0.3)
            except Exception as e:
                logger.debug(f"Slot notify failed for {cid}: {e}")


# ─── Re-exports from bot_ratelimit ───
from bot.bot_ratelimit import (
    RATE_LOCK, parse_time_window, check_rate_limit, consume_rate_limit,
    PENDING_ENTRY, PENDING_ENTRY_LOCK, get_pending_entry, set_pending_entry, clear_pending_entry,
    PENDING_SALE, PENDING_SALE_LOCK, get_pending_sale, set_pending_sale, clear_sale_entry,
    _check_global_rate, broadcast,
)
clear_pending_sale = clear_sale_entry

from bot.bot_security import (
    validate_symbol, validate_callback_data, validate_price_input,
    sanitize_symbol, sanitize_command_args, validate_uid, validate_limit,
)

# ─── Re-exports from bot_messaging ───
from bot.bot_messaging import (
    send_msg, md_to_html, html_escape, send_msg_premium, send_msg_html,
    _api_set_commands, _api_delete_commands, set_user_commands, init_all_commands,
)

def send_trade_alert_to_subscribers(alert: str):
    """
    إرسال تنبيه صفقة فقط للمستخدمين المضافين للصفقة + المالك دايم.
    - المشتركون العاديون: يستلمون التنبيه فقط إذا أضافوا العملة لقائمتهم عبر /list
    - المالك (OWNER_ID): يستقبل كل التنبيهات بدون الحاجة لإضافة العملة
    - الأدمنز: لا يستلمون تنبيهات إلا إذا أضافوا العملة لقائمتهم (مثل أي مشترك)
    
    إذا كان التنبيه عن تحقيق هدف، يضيف زر "تم البيع" تلقائياً.
    """
    import re
    # استخراج الرمز من التنبيه — الصيغة: **SYMBOL**
    match = re.search(r'\*\*(\w+)\*\*', alert)
    if not match:
        # إذا ما قدرنا نستخرج الرمز، نرسل للمالك فقط
        safe_send(OWNER_ID, alert)
        return
    
    sym_clean = match.group(1)
    symbol = sym_clean + "USDT" if not sym_clean.endswith("USDT") else sym_clean
    
    # نجيب المشتركين فقط + المالك دايم
    # الأدمنز ما يستلمون تنبيهات الصفقات إلا إذا أضافوا العملة لقائمتهم
    subscribed = get_trade_subscribers(symbol)
    recipients = set(subscribed) | {OWNER_ID}  # المالك دايم موجود
    
    # 🎯 هل هذا التنبيه عن تحقيق هدف؟ (أضف زر "تم البيع")
    is_target_hit = any(kw in alert for kw in ["هدف ✅", "هدف T", "اول هدف", "هدف تحقق"])
    reply_markup = None
    if is_target_hit:
        # استخراج رقم الهدف من نص التنبيه
        tgt = 0  # افتراضي: هدف أول
        m = re.search(r'هدف T(\d)', alert)
        if m:
            tgt = int(m.group(1)) - 1  # T2→1, T3→2
        reply_markup = {
            "inline_keyboard": [
                [{"text": "💰 تم البيع", "callback_data": f"sold_{tgt}_{symbol}"}]
            ]
        }
    
    sent = 0
    for uid in recipients:
        try:
            show_sold = False
            user_alert = alert
            
            if is_target_hit:
                if has_tracking_data(uid, symbol):
                    user_target_count = get_user_target_count(uid, symbol)
                    is_last_target = (tgt + 1) >= user_target_count
                    
                    if is_last_target:
                        # 🔚 هذا آخر هدف — لا زر, رسالة منتهية + تسجيل تلقائي
                        show_sold = False
                        target_labels = {
                            0: "الهدف",
                            1: "الهدف الثاني",
                            2: "الهدف الثالث",
                        }
                        label = target_labels.get(tgt, f"الهدف {tgt+1}")
                        
                        # استبدال سطر "سجل ربحك" بـ "متابعه منتهيه"
                        for marker in ["💡 سجل ربحك", "\u2066💡 سجل ربحك"]:
                            if marker in user_alert:
                                idx = user_alert.find(marker)
                                line_start = user_alert.rfind('\n', 0, idx)
                                if line_start >= 0:
                                    user_alert = user_alert[:line_start] + f'\n⚠️ متابعه العمله منتهيه لتحقيقها {label}'
                                else:
                                    user_alert = f'⚠️ متابعه العمله منتهيه لتحقيقها {label}'
                                break
                        
                        # 🎯 تسجيل البيع تلقائياً
                        try:
                            entry_price = get_user_entry_price(uid, symbol)
                            if entry_price > 0:
                                price_match = re.search(r'سعر الهدف » [`]*\$?([\d.]+)', alert)
                                if not price_match:
                                    price_match = re.search(r'السعر » [`]*\$?([\d.]+)', alert)
                                if price_match:
                                    target_price = float(price_match.group(1))
                                    record_sale(uid, symbol, entry_price, target_price, tgt)
                                    mark_user_target_hit(uid, symbol, tgt)
                                    mark_user_tracking_complete(uid, symbol)
                                    remove_from_user_list(uid, symbol)
                                    unsubscribe_from_trade(symbol, uid)
                                    logger.info(f"  💰 Auto-sale: {uid} {sym_clean} @ {target_price} (T{tgt+1})")
                        except Exception as e:
                            logger.debug(f"Auto-sale failed for {uid}: {e}")
                    else:
                        # 🖐️ هذا هدف وسيط — أظهر الزر
                        show_sold = True
                else:
                    # 👤 بدون تتبع (مالك/زائر بدون قائمة) — رسالة معلومات فقط
                    show_sold = False
                    for marker in ["💡 سجل ربحك", "\u2066💡 سجل ربحك"]:
                        if marker in user_alert:
                            idx = user_alert.find(marker)
                            line_start = user_alert.rfind('\n', 0, idx)
                            if line_start >= 0:
                                user_alert = user_alert[:line_start] + '\n📊 الهدف الأول تحقق بنجاح'
                            else:
                                user_alert = '📊 الهدف الأول تحقق بنجاح'
                            break
                    
            if show_sold:
                msg_id = send_msg_premium(uid, user_alert, reply_markup=reply_markup)
            else:
                msg_id = send_msg(uid, user_alert)
            if msg_id:
                sent += 1
            time.sleep(0.08)
        except Exception as e:
            logger.debug(f"Alert send failed to {uid}: {e}")
    
    logger.info(f"  📨 {sym_clean} alert → {sent}/{len(recipients)} recipients (owner always)")
    
    # 🧹 إذا التنبيه إغلاق (TP/SL/إلغاء) — نظف القوائم + التتبع
    if any(kw in alert for kw in ["منتهيه", "خساره", "إلغاء", "ملغيه", "انتهت"]):
        cleanup_closed_trade(symbol)
        cleanup_user_tracking(symbol)


def _send_to_admins(text: str):
    """إرسال رسالة للأدمنز فقط"""
    admins = load_admins()
    for uid in admins:
        try:
            send_msg_premium(uid, text)
        except Exception as e:
            logger.debug(f"Admin notify failed for {uid}: {e}")



def safe_send(chat_id, text):
    """Send with premium emoji support — إيموجي متحرك لمستخدم Premium"""
    success = send_msg_premium(chat_id, text)
    if not success:
        # Try without entities
        clean = text.replace("**", "").replace("`", "").replace("*", "")
        success = send_msg(chat_id, clean, parse_mode=None)
    return success

def _pnl_key(t: dict) -> float:
    """Sort key: sort trades by PnL descending (highest profit first)"""
    entry = t.get("entry_price") or 0
    cur = t.get("current_price") or entry
    if entry == 0:
        return 0.0
    return (cur - entry) / entry * 100


# ─── Commands ───
def handle_callback(cb: dict):
    """Handle button press callbacks"""
    try:
        data = cb.get("data", "")
        chat_id = cb.get("message", {}).get("chat", {}).get("id")
        msg_id = cb.get("message", {}).get("message_id")
        
        # ─── Input validation gate ───
        if not validate_callback_data(data):
            logger.warning(f"Invalid callback data from {chat_id}: {data[:50]}")
            return
        
        # Remove loading indicator
        requests.post(f"{API_BASE}/answerCallbackQuery",
                      json={"callback_query_id": cb["id"], "text": ""},
                      timeout=10)
        
        if not chat_id:
            return
        
        trades = update_current_prices(get_active_trades())
        save_trades(trades)

        # ─── Ignore placeholder ───
        if data == "nav_ignore":
            return

        # ─── Signals: Show active (filtered, sorted by PnL desc) ───
        if data == "signals_active":
            filtered = [t for t in trades if t.get("status") == "active"]
            filtered.sort(key=_pnl_key, reverse=True)
            if not filtered:
                text = "🟢 **لا توجد توصيات نشطة حالياً**\n\nكل التوصيات معلقة أو منتهية."
                keyboard = {"inline_keyboard": [[{"text": "🔄 الرجوع", "callback_data": "back_signals"}]]}
            else:
                keyboard = build_list_keyboard(filtered, page=1, mode="signals", filter_type="active")
                total_pages = max(1, (len(filtered) + 9) // 10)
                text = f"🟢 **التوصيات النشطة** ({len(filtered)}) — ص 1/{total_pages}\nاختر عملة للتفاصيل:"
            requests.post(f"{API_BASE}/editMessageText", json={
                "chat_id": chat_id, "message_id": msg_id,
                "text": text, "reply_markup": keyboard,
                "parse_mode": "Markdown"
            }, timeout=10)
            return

        # ─── Signals: Show pending (filtered) ───
        if data == "signals_pending":
            filtered = [t for t in trades if t.get("status") == "pending"]
            if not filtered:
                text = "⏳ **لا توجد توصيات معلقة حالياً**\n\nكل التوصيات نشطة أو منتهية."
                keyboard = {"inline_keyboard": [[{"text": "🔄 الرجوع", "callback_data": "back_signals"}]]}
            else:
                keyboard = build_list_keyboard(filtered, page=1, mode="signals", filter_type="pending")
                total_pages = max(1, (len(filtered) + 9) // 10)
                text = f"⏳ **التوصيات المعلقة** ({len(filtered)}) — ص 1/{total_pages}\nاختر عملة للتفاصيل:"
            requests.post(f"{API_BASE}/editMessageText", json={
                "chat_id": chat_id, "message_id": msg_id,
                "text": text, "reply_markup": keyboard,
                "parse_mode": "Markdown"
            }, timeout=10)
            return

        # ─── Signals: Filtered page nav ───
        if data.startswith("signals_active_page_"):
            page = int(data.replace("signals_active_page_", ""))
            filtered = [t for t in trades if t.get("status") == "active"]
            filtered.sort(key=_pnl_key, reverse=True)
            keyboard = build_list_keyboard(filtered, page=page, mode="signals", filter_type="active")
            total_pages = max(1, (len(filtered) + 9) // 10)
            text = f"🟢 **التوصيات النشطة** ({len(filtered)}) — ص {page}/{total_pages}\nاختر عملة للتفاصيل:"
            requests.post(f"{API_BASE}/editMessageText", json={
                "chat_id": chat_id, "message_id": msg_id,
                "text": text, "reply_markup": keyboard,
                "parse_mode": "Markdown"
            }, timeout=10)
            return

        if data.startswith("signals_pending_page_"):
            page = int(data.replace("signals_pending_page_", ""))
            filtered = [t for t in trades if t.get("status") == "pending"]
            keyboard = build_list_keyboard(filtered, page=page, mode="signals", filter_type="pending")
            total_pages = max(1, (len(filtered) + 9) // 10)
            text = f"⏳ **التوصيات المعلقة** ({len(filtered)}) — ص {page}/{total_pages}\nاختر عملة للتفاصيل:"
            requests.post(f"{API_BASE}/editMessageText", json={
                "chat_id": chat_id, "message_id": msg_id,
                "text": text, "reply_markup": keyboard,
                "parse_mode": "Markdown"
            }, timeout=10)
            return

        # ─── Page navigation: signals ───
        if data.startswith("signals_page_"):
            page = int(data.replace("signals_page_", ""))
            trades = update_current_prices(get_active_trades())
            save_trades(trades)
            keyboard = build_list_keyboard(trades, page=page, mode="signals")
            active_count = len([t for t in trades if t.get("status") == "active"])
            pending_count = len([t for t in trades if t.get("status") == "pending"])
            total_pages = max(1, (len(trades) + 9) // 10)
            text = f"📡 **التوصيات النشطة** ({len(trades)}) — ص {page}/{total_pages}\n✅ {active_count} نشطة"
            if pending_count > 0:
                text += f" | ⏳ {pending_count} معلقة"
            text += "\nاختر عملة للتفاصيل:"
            requests.post(f"{API_BASE}/editMessageText", json={
                "chat_id": chat_id, "message_id": msg_id,
                "text": text, "reply_markup": keyboard,
                "parse_mode": "Markdown"
            }, timeout=10)
            return
        
        # ─── Page navigation: my list ───
        if data.startswith("mylist_page_"):
            page = int(data.replace("mylist_page_", ""))
            user_symbols = get_user_list(chat_id)
            all_trades = update_current_prices(get_active_trades())
            save_trades(all_trades)
            my_trades = [t for t in all_trades if t["symbol"] in user_symbols]
            keyboard = build_list_keyboard(my_trades, page=page, mode="list")
            total_pages = max(1, (len(my_trades) + 9) // 10)
            text = f"📋 **قائمتك الشخصية** ({len(my_trades)} عملة) — ص {page}/{total_pages}\nاختر عملة للتفاصيل:"
            requests.post(f"{API_BASE}/editMessageText", json={
                "chat_id": chat_id, "message_id": msg_id,
                "text": text, "reply_markup": keyboard,
                "parse_mode": "Markdown"
            }, timeout=10)
            return
        
        # ─── Back to signals filter ───
        if data in ("back_list", "back_signals"):
            trades = update_current_prices(get_active_trades())
            save_trades(trades)
            if not trades:
                requests.post(f"{API_BASE}/editMessageText", json={
                    "chat_id": chat_id, "message_id": msg_id,
                    "text": "📡 **لا توجد توصيات حالياً**",
                    "parse_mode": "Markdown"
                }, timeout=10)
                return
            active_count = len([t for t in trades if t.get("status") == "active"])
            pending_count = len([t for t in trades if t.get("status") == "pending"])
            text = f"📡 **اختر نوع التوصيات**\n\n✅ {active_count} نشطة | ⏳ {pending_count} معلقة\n\nاختر النوع لعرض القائمة:"
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": f"🟢 نشطه ({active_count})", "callback_data": "signals_active"},
                        {"text": f"⏳ معلقه ({pending_count})", "callback_data": "signals_pending"},
                    ]
                ]
            }
            requests.post(f"{API_BASE}/editMessageText", json={
                "chat_id": chat_id, "message_id": msg_id,
                "text": text, "reply_markup": keyboard,
                "parse_mode": "Markdown"
            }, timeout=10)
            return
        
        # ─── Back to my list ───
        if data == "back_mylist":
            user_symbols = get_user_list(chat_id)
            all_trades = update_current_prices(get_active_trades())
            save_trades(all_trades)
            my_trades = [t for t in all_trades if t["symbol"] in user_symbols]
            keyboard = build_list_keyboard(my_trades, page=1, mode="list")
            text = f"📋 **قائمتك الشخصية** ({len(my_trades)} عملة)\nاختر عملة للتفاصيل:"
            requests.post(f"{API_BASE}/editMessageText", json={
                "chat_id": chat_id, "message_id": msg_id,
                "text": text, "reply_markup": keyboard,
                "parse_mode": "Markdown"
            }, timeout=10)
            return
        
        # ─── 🎯 Target selection (premium users) ───
        if data.startswith("target_"):
            # data format: target_1_SYMBOL → target_{count}_{symbol}
            parts = data.split("_", 2)  # max split = 2 → ["target", "1", "SYMBOL"]
            if len(parts) < 3:
                return
            count = int(parts[1])
            symbol = parts[2]
            sym_clean = symbol.replace("USDT", "")
            
            pending = get_pending_entry(chat_id)
            if not pending or pending.get("phase") != "target":
                requests.post(f"{API_BASE}/answerCallbackQuery", json={
                    "callback_query_id": cb["id"], "text": "انتهت صلاحية الطلب، استخدم /signals من جديد"
                }, timeout=10)
                return
            
            user_entry = pending.get("entry_price", pending.get("original_entry"))
            
            # Add to list with target count
            clear_pending_entry(chat_id)
            added = add_to_user_list(chat_id, symbol)
            subscribe_to_trade(symbol, chat_id)
            
            if added:
                set_user_entry_price(chat_id, symbol, user_entry)
                # تخزين أهداف الصفقة في التتبع للمراقبة بعد إغلاق الصفقة العالمية
                trade_targets = pending.get("trade", {}).get("targets", [])
                set_user_target_count(chat_id, symbol, count, targets=trade_targets, entry_price=user_entry)
                
                target_text = {1: "هدف واحد 🎯", 2: "هدفين 🎯🎯", 3: "3 أهداف 🎯🎯🎯"}.get(count, f"{count} أهداف")
                text = (
                    f"✅ **{sym_clean}** أضيفت إلى قائمتك!\n\n"
                    f"📥 سعر دخولك: **${user_entry}**\n"
                    f"🎯 المتابعة: {target_text}\n"
                    f"ستصلك تنبيهات لكل هدف يتحقق\n\n"
                    f"📋 /list | 📊 /portfolio"
                )
            else:
                text = f"ℹ️ **{sym_clean}** موجودة فعلاً في قائمتك."
            
            requests.post(f"{API_BASE}/editMessageText", json={
                "chat_id": chat_id, "message_id": msg_id,
                "text": text,
                "parse_mode": "Markdown",
            }, timeout=10)
            return
        
        # ─── 💰 تم البيع button ───
        if data.startswith("sold_"):
            # Format: sold_{target_idx}_{symbol} (جديد) أو sold_{symbol} (قديم)
            parts = data.split("_", 2)
            if len(parts) < 2:
                return
            if len(parts) == 2:
                # صيغة قديمة: sold_SYMBOL → توافق عكسي
                target_idx = 0
                symbol = parts[1]
            else:
                # صيغة جديدة: sold_TARGET_SYMBOL
                try:
                    target_idx = int(parts[1])
                except ValueError:
                    target_idx = 0
                symbol = parts[2]
            sym_clean = symbol.replace("USDT", "")
            
            # Get user's entry price for this symbol
            entry_price = get_user_entry_price(chat_id, symbol)
            if entry_price <= 0:
                requests.post(f"{API_BASE}/answerCallbackQuery", json={
                    "callback_query_id": cb["id"], "text": "لم نعثر على سعر الدخول!"
                }, timeout=10)
                return
            
            set_pending_sale(chat_id, {
                "symbol": symbol,
                "sym_clean": sym_clean,
                "entry_price": entry_price,
                "target_idx": target_idx,
                "msg_id": msg_id,
            })
            
            requests.post(f"{API_BASE}/editMessageText", json={
                "chat_id": chat_id, "message_id": msg_id,
                "text": (
                    f"💰 **{sym_clean} — تم البيع**\n\n"
                    f"سعر دخولك: **${entry_price}**\n"
                    f"الرجاء إرسال **سعر البيع الفعلي**:\n"
                    f"(أرسل الرقم فقط)"
                ),
                "parse_mode": "Markdown",
            }, timeout=10)
            return
        
        # ─── Add to personal list — Auto-calculate entry price 🔥 ───
        if data.startswith("add_"):
            symbol = data.replace("add_", "")
            sym_clean = symbol.replace("USDT", "")
            
            # Find the trade
            trade = next((t for t in trades if t["symbol"] == symbol), None)
            if not trade:
                requests.post(f"{API_BASE}/editMessageText", json={
                    "chat_id": chat_id, "message_id": msg_id,
                    "text": f"⚠️ **{sym_clean}** لم تعد متاحة.",
                    "parse_mode": "Markdown"
                }, timeout=10)
                return
            
            sig_entry = trade["entry_price"]
            
            # 🔥 Auto-calculate entry price: min(current_price, signal_entry)
            current_price = trade.get("current_price", sig_entry)
            try:
                from data.data_fetcher import get_fetcher
                prices = get_fetcher().fetch_all_prices()
                live_price = prices.get(symbol)
                if live_price and live_price > 0:
                    current_price = live_price
            except Exception as e:
                logger.debug(f"Live price fetch failed for {symbol}: {e}")  # use trade's current_price as fallback
            
            user_entry = min(current_price, sig_entry)
            dec = 8 if user_entry < 1 else 6 if user_entry < 100 else 4
            sig_dec = 8 if sig_entry < 1 else 6 if sig_entry < 100 else 4
            
            role = get_role(chat_id)
            
            # ── Premium/Admin/Owner → ask target count first ──
            if role in ("premium", "admin", "owner"):
                set_pending_entry(chat_id, {
                    "symbol": symbol,
                    "sym_clean": sym_clean,
                    "trade": trade,
                    "phase": "target",
                    "entry_price": user_entry,
                    "original_entry": sig_entry,
                    "current_price": current_price,
                    "msg_id": msg_id,
                })
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "🎯 هدف واحد", "callback_data": f"target_1_{symbol}"}],
                        [{"text": "🎯 هدفين", "callback_data": f"target_2_{symbol}"}],
                        [{"text": "🎯 3 أهداف", "callback_data": f"target_3_{symbol}"}],
                    ]
                }
                requests.post(f"{API_BASE}/editMessageText", json={
                    "chat_id": chat_id, "message_id": msg_id,
                    "text": (
                        f"📝 **كم هدف تريد متابعة {sym_clean} عليه؟**\n\n"
                        f"📥 سعر دخولك التلقائي: **${user_entry:.{dec}f}**\n"
                        f"💡 سعر الإشارة الأصلي: ${sig_entry:.{sig_dec}f}\n"
                        f"📊 السعر الحالي: ${current_price:.{dec}f}\n\n"
                        f"✅ تم احتساب أفضل سعر دخول لك تلقائياً!\n\n"
                        f"اختر عدد الأهداف للمتابعة:"
                    ),
                    "reply_markup": keyboard,
                    "parse_mode": "Markdown",
                }, timeout=10)
                return
            
            # ── Regular member → add directly ──
            clear_pending_entry(chat_id)
            added = add_to_user_list(chat_id, symbol)
            subscribe_to_trade(symbol, chat_id)
            
            if added:
                set_user_entry_price(chat_id, symbol, user_entry)
                cp_dec = 8 if current_price < 1 else 6 if current_price < 100 else 4
                text = (
                    f"✅ **{sym_clean}** أضيفت إلى قائمتك!\n\n"
                    f"📥 سعر دخولك التلقائي: **${user_entry:.{dec}f}**\n"
                    f"💡 سعر الإشارة الأصلي: ${sig_entry:.{sig_dec}f}\n"
                    f"📊 السعر الحالي: ${current_price:.{cp_dec}f}\n"
                    f"🟢 تم احتساب أفضل سعر لك!\n\n"
                    f"📋 /list | 📊 /portfolio"
                )
            else:
                text = f"ℹ️ **{sym_clean}** موجودة فعلاً في قائمتك.\n\n📋 /list | 📊 /portfolio"
            
            requests.post(f"{API_BASE}/editMessageText", json={
                "chat_id": chat_id, "message_id": msg_id,
                "text": text,
                "parse_mode": "Markdown",
            }, timeout=10)
            return
        
        # ─── Remove from personal list ───
        if data.startswith("remove_"):
            symbol = data.replace("remove_", "")
            sym_clean = symbol.replace("USDT", "")
            
            removed = remove_from_user_list(chat_id, symbol)
            unsubscribe_from_trade(symbol, chat_id)
            
            if removed:
                text = f"🗑️ **{sym_clean}** حذفت من قائمتك.\n\nلن تصلك تنبيهاتها بعد الآن.\n\n📡 /signals | 📋 /list"
            else:
                text = f"ℹ️ **{sym_clean}** غير موجودة في قائمتك."
            
            requests.post(f"{API_BASE}/editMessageText", json={
                "chat_id": chat_id, "message_id": msg_id,
                "text": text,
                "parse_mode": "Markdown"
            }, timeout=10)
            return
        
        # ─── View trade details ───
        if data.startswith("trade_"):
            symbol = data.replace("trade_", "")
            trade = next((t for t in trades if t["symbol"] == symbol), None)
            # Detect which mode we're coming from
            user_symbols = get_user_list(chat_id)
            from_mode = "list" if symbol in user_symbols else "signals"
            if trade:
                trade["current_price"] = trade.get("current_price", trade["entry_price"])
                text = format_trade_detail_text(trade)
                keyboard = build_detail_keyboard(symbol, user_id=chat_id, from_mode=from_mode)
            else:
                text = f"⚠️ {symbol.replace('USDT','')} trade no longer exists."
                keyboard = build_back_keyboard("signals")
            
            requests.post(f"{API_BASE}/editMessageText", json={
                "chat_id": chat_id, "message_id": msg_id,
                "text": text, "reply_markup": keyboard,
                "parse_mode": "Markdown"
            }, timeout=10)
            return
        
        # ─── Support analysis for losing trade ───
        if data.startswith("analyze_"):
            symbol = data.replace("analyze_", "")
            logger.info(f"📊 Support analysis requested for {symbol}")
            
            # Detect mode
            user_symbols = get_user_list(chat_id)
            from_mode = "list" if symbol in user_symbols else "signals"
            
            # Waiting message
            requests.post(f"{API_BASE}/editMessageText", json={
                "chat_id": chat_id, "message_id": msg_id,
                "text": f"🔍 Analyzing {symbol.replace('USDT','')}... ⏳",
                "parse_mode": "Markdown"
            }, timeout=10)
            
            # تحليل الدعم
            analysis = analyze_support_levels(symbol)
            keyboard = build_back_keyboard(from_mode)
            
            requests.post(f"{API_BASE}/editMessageText", json={
                "chat_id": chat_id, "message_id": msg_id,
                "text": analysis, "reply_markup": keyboard,
                "parse_mode": "Markdown"
            }, timeout=10)
    
    except Exception as e:
        logger.error(f"Callback error: {e}")
        # ⚠️ Show user an error popup
        try:
            requests.post(f"{API_BASE}/answerCallbackQuery", json={
                "callback_query_id": cb.get("id"),
                "text": "⚠️ حدث خطأ. حاول مرة أخرى.",
                "show_alert": True
            }, timeout=10)
        except Exception as e:
            logger.debug(f"Callback error reply failed: {e}")


def handle_update(update: dict):
    # ─── Handle callbacks first ───
    cb = update.get("callback_query")
    if cb:
        try:
            handle_callback(cb)
        except Exception as e:
            logger.error(f"Callback call error: {e}")
            try:
                requests.post(f"{API_BASE}/answerCallbackQuery", json={
                    "callback_query_id": cb.get("id"),
                    "text": "⚠️ حدث خطأ. حاول مرة أخرى.",
                    "show_alert": True
                }, timeout=10)
            except Exception as e:
                logger.debug(f"Update callback error reply failed: {e}")
        return
    
    msg = update.get("message", {})
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    text = msg.get("text", "").strip()
    username = chat.get("username", "")
    first_name = chat.get("first_name", "")

    if not chat_id or not text:
        return

    args = text.split()
    cmd = args[0].lower()
    logger.info(f"Command: {cmd} from {chat_id}")

    # 📊 Record command metric
    if HAS_BOT_METRICS:
        record_bot_command(cmd)

    # ─── صلاحيات حسب الرتبة ───
    user_role = get_role(chat_id)
    is_subscribed = user_role is not None  # أي شخص له رتبة
    is_admin_role = is_admin(chat_id)       # مشرف أو مالك
    
    # ═══════════════════════════════════
    # رفض لغير المشتركين فقط
    # ═══════════════════════════════════
    if not is_subscribed and cmd not in PUBLIC_COMMANDS:
        logger.warning(f"🚫 Blocked {chat_id} ({first_name}) — not subscribed")
        safe_send(chat_id, "🚫 **تم حظرك!**\n\nاستخدم /start أولاً للاشتراك.")
        return
    
    try:
        # ═══════════════════════════════════
        # 🎯 Pending entry price — user is adding a coin
        # ═══════════════════════════════════
        pending_entry = get_pending_entry(chat_id)
        if pending_entry and not text.startswith("/"):
            symbol = pending_entry["symbol"]
            sym_clean = pending_entry["sym_clean"]
            trade = pending_entry["trade"]
            low = pending_entry["low"]
            high = pending_entry["high"]
            original_entry = pending_entry["original_entry"]
            msg_id = pending_entry["msg_id"]
            
            # ── If already in "target" phase, this text shouldn't happen ──
            if pending_entry.get("phase") == "target":
                return
            
            try:
                user_entry = float(text.replace(",", "").replace("$", ""))
            except ValueError:
                safe_send(chat_id, f"⚠️ **{sym_clean}** لم تُضف — الرجاء إرسال رقم صحيح.\n\nأرسل السعر مرة أخرى (مثلاً: {original_entry}):")
                return
            
            # Validation: must be within [low, high] range
            if user_entry < low or user_entry > high:
                safe_send(chat_id, (
                    f"⚠️ **{sym_clean}** لم تُضف — سعر الدخول غير صحيح.\n\n"
                    f"السعر المدخل (${user_entry}) لا يتطابق مع نطاق سعر الإشارة.\n"
                    f"الرجاء التأكد من سعر الشراء الفعلي وحاول مرة أخرى.\n"
                    f"سعر الإشارة الأصلي: ${original_entry}\n\n"
                    f"أرسل السعر الصحيح (مثلاً: {original_entry}):"
                ))
                return
            
            # ✅ Validation passed!
            role = get_role(chat_id)
            
            # ── If premium/admin/owner → ask target count first ──
            if role in ("premium", "admin", "owner"):
                set_pending_entry(chat_id, {
                    **pending_entry,
                    "phase": "target",
                    "entry_price": user_entry,
                })
                # Inline keyboard for target selection
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "🎯 هدف واحد", "callback_data": f"target_1_{symbol}"}],
                        [{"text": "🎯 هدفين", "callback_data": f"target_2_{symbol}"}],
                        [{"text": "🎯 3 أهداف", "callback_data": f"target_3_{symbol}"}],
                    ]
                }
                requests.post(f"{API_BASE}/editMessageText", json={
                    "chat_id": chat_id, "message_id": msg_id,
                    "text": (
                        f"📝 **كم هدف تريد متابعة {sym_clean} عليه؟**\n\n"
                        f"✅ سعر الدخول: **${user_entry}**\n"
                        f"اختر عدد الأهداف التي تريد النظام يتتبعها:"
                    ),
                    "reply_markup": keyboard,
                    "parse_mode": "Markdown",
                }, timeout=10)
                return
            
            # ── Regular member → add directly ──
            clear_pending_entry(chat_id)
            added = add_to_user_list(chat_id, symbol)
            subscribe_to_trade(symbol, chat_id)
            
            if added:
                set_user_entry_price(chat_id, symbol, user_entry)
                safe_send(chat_id, (
                    f"✅ **{sym_clean}** أضيفت إلى قائمتك!\n\n"
                    f"📥 سعر دخولك: **${user_entry}**\n"
                    f"ستصلك تنبيهات: تنفيذ الأمر • الأهداف • وقف الخسارة\n\n"
                    f"📋 /list | 📊 /portfolio"
                ))
            else:
                safe_send(chat_id, f"ℹ️ **{sym_clean}** موجودة فعلاً في قائمتك.\n\n📋 /list | 📊 /portfolio")
            return
        
        if pending_entry and text.startswith("/"):
            # User sent a command instead — cancel pending
            clear_pending_entry(chat_id)
        
        # ═══════════════════════════════════
        # 💰 Pending sale — user clicked "تم البيع"
        # ═══════════════════════════════════
        pending_sale = get_pending_sale(chat_id)
        if pending_sale and not text.startswith("/"):
            symbol = pending_sale["symbol"]
            sym_clean = pending_sale["sym_clean"]
            entry_price = pending_sale["entry_price"]
            target_idx = pending_sale["target_idx"]
            msg_id = pending_sale["msg_id"]
            
            try:
                sale_price = float(text.replace(",", "").replace("$", ""))
            except ValueError:
                safe_send(chat_id, f"⚠️ **{sym_clean}** — الرجاء إرسال رقم صحيح.\n\nأرسل سعر البيع (مثلاً: {entry_price}):")
                return
            
            if sale_price <= 0:
                safe_send(chat_id, "⚠️ سعر البيع يجب أن يكون أكبر من 0. أرسل السعر الصحيح:")
                return
            
            clear_pending_sale(chat_id)
            
            # Record the sale
            from trade.trade_userlists import record_sale, mark_user_target_hit, get_user_target_count, get_user_targets_hit, mark_user_tracking_complete, remove_from_user_list, unsubscribe_from_trade
            pnl_pct = record_sale(chat_id, symbol, entry_price, sale_price, target_idx)
            
            # 🎯 تسجيل الهدف في تتبع المستخدم
            mark_user_target_hit(chat_id, symbol, target_idx)
            
            # 🎯 هل هذا هو آخر هدف للمستخدم؟
            target_count = get_user_target_count(chat_id, symbol)
            targets_hit = get_user_targets_hit(chat_id, symbol)
            
            pnl_emoji = "🟢" if pnl_pct > 0 else "🔴"
            if len(targets_hit) >= target_count:
                # ✅ اكتمل التتبع — نحذف من القائمة ونلغي الاشتراك
                mark_user_tracking_complete(chat_id, symbol)
                remove_from_user_list(chat_id, symbol)
                unsubscribe_from_trade(symbol, chat_id)
                safe_send(chat_id, (
                    f"{pnl_emoji} **{sym_clean} — تم تسجيل البيع!** ✅\n\n"
                    f"📥 سعر الشراء: **${entry_price}**\n"
                    f"💰 سعر البيع: **${sale_price}**\n"
                    f"📊 الربح/الخسارة: **{pnl_pct:+.2f}%**\n\n"
                    f"🎯 اكتمل تتبع {sym_clean} بعدد الأهداف المطلوب ({target_count}).\n"
                    f"📊 /portfolio — لمشاهدة محفظتك"
                ))
            else:
                # ⏳ التتبع مستمر — انتظار الأهداف القادمة
                remaining = target_count - len(targets_hit)
                safe_send(chat_id, (
                    f"{pnl_emoji} **{sym_clean} — تم تسجيل البيع!**\n\n"
                    f"📥 سعر الشراء: **${entry_price}**\n"
                    f"💰 سعر البيع: **${sale_price}**\n"
                    f"📊 الربح/الخسارة: **{pnl_pct:+.2f}%**\n\n"
                    f"📌 تبقي {remaining} هدف/أهداف للمتابعة.\n"
                    f"ستصلك تنبيهات الأهداف القادمة."
                ))
            return
        
        if pending_sale and text.startswith("/"):
            clear_pending_sale(chat_id)
        
        # ═══════════════════════════════════
        # PUBLIC COMMANDS (anyone)
        # ═══════════════════════════════════

        if cmd == "/start":
            # اشتراك + صلاحيات كاملة تلقائي
            add_subscriber(chat_id, username, first_name)
            try_assign_slot(chat_id)  # 🪑 تعيين مقعد تلقائي
            reset_spam(chat_id)
            
            # تعيين الرتبة
            current_role = get_role(chat_id)
            if not current_role or current_role == "member":
                set_role(chat_id, "member")
            
            # تعيين الأوامر حسب الرتبة
            role = get_role(chat_id)
            set_user_commands(chat_id, role)
            
            # رسالة ترحيب حسب الرتبة
            if role == "owner":
                safe_send(chat_id, f"🎉 **Welcome Master YJ!**\n\n{WELCOME_MSG}")
            elif role == "admin":
                safe_send(chat_id, f"🎉 **مرحباً بك أيها المشرف**\n\n{WELCOME_MSG}")
            elif role == "premium":
                safe_send(chat_id, f"🎉 **مرحباً بك أيها المميز**\n\n📊 لديك صلاحية الوصول للتحليلات المتقدمة.\n\n{MEMBER_WELCOME}")
            else:
                safe_send(chat_id, MEMBER_WELCOME)
            return

        elif cmd == "/signals":
            # عرض قائمة اختيار: نشطة vs معلقة
            if not is_admin_role:
                allowed, spam_msg = check_list_spam(chat_id)
                if not allowed:
                    safe_send(chat_id, spam_msg)
                    return

            trades = update_current_prices(get_active_trades())
            save_trades(trades)
            if not trades:
                safe_send(chat_id, "📡 **لا توجد توصيات نشطة حالياً**")
                return

            active_count = len([t for t in trades if t.get("status") == "active"])
            pending_count = len([t for t in trades if t.get("status") == "pending"])
            text = f"📡 **اختر نوع التوصيات**\n\n✅ {active_count} نشطة | ⏳ {pending_count} معلقة\n\nاختر النوع لعرض القائمة:"
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": f"🟢 نشطه ({active_count})", "callback_data": "signals_active"},
                        {"text": f"⏳ معلقه ({pending_count})", "callback_data": "signals_pending"},
                    ]
                ]
            }
            requests.post(f"{API_BASE}/sendMessage", json={
                "chat_id": chat_id,
                "text": text,
                "reply_markup": keyboard,
                "parse_mode": "Markdown"
            }, timeout=15)
            return

        elif cmd == "/list":
            # قائمة المستخدم الشخصية — مع pagination
            user_symbols = get_user_list(chat_id)
            if not user_symbols:
                safe_send(chat_id, "📋 **قائمتك الشخصية**\n\nلا توجد عملات مضافة.\n\nاستخدم /signals لعرض التوصيات ثم اضغط ➕ أضف إلى قائمتي.")
                return
            
            trades = update_current_prices(get_active_trades())
            save_trades(trades)
            my_trades = [t for t in trades if t["symbol"] in user_symbols]
            
            if not my_trades:
                safe_send(chat_id, "📋 **قائمتك الشخصية**\n\nالعملات اللي ضفتها لم تعد نشطة (حققت هدف/ألغيت/ضربت وقف).\nاستخدم /signals للبحث عن فرص جديدة.")
                return
            
            keyboard = build_list_keyboard(my_trades, page=1, mode="list")
            total_pages = max(1, (len(my_trades) + 9) // 10)
            text = f"📋 **قائمتك الشخصية** ({len(my_trades)} عملة) — ص 1/{total_pages}\nاختر عملة للتفاصيل:"
            requests.post(f"{API_BASE}/sendMessage", json={
                "chat_id": chat_id,
                "text": text,
                "reply_markup": keyboard,
                "parse_mode": "Markdown"
            }, timeout=15)
            return

        elif cmd == "/portfolio":
            # محفظة المستخدم — ربح/خسارة العملات اللي ضافها
            user_symbols = get_user_list(chat_id)
            if not user_symbols:
                # No active trades — show closed trade history
                try:
                    with open(DATA_DIR / "trades_history.json") as f:
                        history = json.load(f)
                except Exception:
                    history = []
                
                user_history = [h for h in history if h.get("symbol", "").replace("USDT","") in 
                               [s.replace("USDT","") for s in user_symbols]] if user_symbols else []
                
                if not user_history and not user_symbols:
                    safe_send(chat_id, "📊 **محفظتك**\n\nلا توجد عملات مضافة.\n\nاستخدم /signals ثم ➕ أضف إلى قائمتي.")
                    return
                
                if not user_history and user_symbols:
                    safe_send(chat_id, "📊 **محفظتك**\n\nلا توجد صفقات نشطة حالياً في قائمتك.\nكل الصفقات السابقة مغلقة.")
                    return
                
                # Show closed trade history
                wins = [h for h in user_history if h.get("pnl_pct",0) > 0]
                losses = [h for h in user_history if h.get("pnl_pct",0) < 0]
                total_pnl = sum(h.get("pnl_pct",0) for h in user_history)
                win_rate = len(wins) / max(len(wins) + len(losses), 1) * 100
                
                lines = ["📊 **محفظتك — سجل الصفقات**", ""]
                for h in user_history[-10:]:  # Last 10
                    sym = h["symbol"].replace("USDT", "")
                    pnl = h.get("pnl_pct", 0)
                    emoji = "🟢" if pnl > 0 else "🔴"
                    lines.append(f"{emoji} **{sym}** {pnl:+.2f}%")
                
                lines.append("")
                lines.append("━━━━━━━━━━━━━━━")
                total_emoji = "🟢" if total_pnl > 0 else "🔴"
                lines.append(f"{total_emoji} **إجمالي الأرباح:** {total_pnl:+.2f}%")
                lines.append(f"✅ ناجحة: {len(wins)} | ❌ خاسرة: {len(losses)} | 🎯 {win_rate:.0f}%")
                lines.append(f"📋 إجمالي الصفقات: {len(user_history)}")
                
                safe_send(chat_id, "\n".join(lines))
                return
            
            trades = update_current_prices(get_active_trades())
            save_trades(trades)
            my_trades = [t for t in trades if t["symbol"] in user_symbols]
            
            if not my_trades:
                safe_send(chat_id, "📊 **محفظتك**\n\nلا توجد صفقات نشطة حالياً في قائمتك.\nكل الصفقات السابقة مغلقة — استخدم /report للاطلاع على التقرير اليومي.")
                return
            
            entry_prices = get_all_user_entry_prices(chat_id)
            total_pnl = 0
            lines = ["📊 **محفظتك الشخصية**", ""]
            
            for t in my_trades:
                sym = t["symbol"].replace("USDT", "")
                entry = entry_prices.get(t["symbol"], t["entry_price"])  # Use custom entry if available
                cp = t.get("current_price", entry)
                status = t.get("status", "active")
                pnl_pct = (cp - entry) / entry * 100
                total_pnl += pnl_pct
                
                emoji = "🟢" if pnl_pct > 0 else "🔴" if pnl_pct < 0 else "⚪"
                status_icon = "⏳" if status == "pending" else ""
                
                # Format price with proper decimals
                dec = 8 if entry < 0.01 else 6 if entry < 1 else 4
                entry_label = f"سعرك ${entry:.{dec}f}" if t["symbol"] in entry_prices else f"دخول ${entry:.{dec}f}"
                lines.append(f"{emoji} **{sym}** {status_icon} {pnl_pct:+.2f}% | {entry_label}")
            
            lines.append("")
            lines.append("━━━━━━━━━━━━━━━")
            avg_pnl = total_pnl / len(my_trades) if my_trades else 0
            total_emoji = "🟢" if total_pnl > 0 else "🔴"
            lines.append(f"{total_emoji} **إجمالي:** {total_pnl:+.2f}% | متوسط: {avg_pnl:+.2f}%")
            lines.append(f"📋 عدد العملات: {len(my_trades)}")
            
            safe_send(chat_id, "\n".join(lines))
            return

        elif cmd == "/report":
            # تقرير اليوم الحالي — الصفقات الرابحة والخاسرة وصافي الربح
            try:
                from trade.trade_tracker import generate_daily_report
                report = generate_daily_report()
                if report:
                    safe_send(chat_id, report)
                else:
                    safe_send(chat_id, "📊 **لا توجد صفقات مغلقة اليوم**")
            except Exception as e:
                logger.error(f"Report generation error: {e}")
                safe_send(chat_id, "⚠️ حدث خطأ أثناء إنشاء التقرير.")
            return

        # ═══════════════════════════════════
        # SLOT USER COMMANDS (needs slot, non-owner)
        # ═══════════════════════════════════

        elif cmd == "/stop":
            # Remove from subscribers
            with SUBS_LOCK:
                subs = _read_subs()
                if chat_id in subs:
                    subs.remove(chat_id)
                    try:
                        SUBS_FILE.write_text(json.dumps(subs))
                    except Exception as e:
                        logger.error(f"Failed to save subscribers: {e}")
            # Free slot + broadcast availability (built into remove_slot)
            freed = remove_slot(chat_id)
            if freed:
                logger.info(f"🪑 Slot freed by /stop: {chat_id}")
            safe_send(chat_id, "🔴 **تم إلغاء الاشتراك وتحرير مقعدك**\n\nللرجوع: /start")
            return

        elif cmd == "/help":
            role = get_role(chat_id)
            if role == "owner":
                safe_send(chat_id, HELP_MSG)
            elif role == "admin":
                safe_send(chat_id, ADMIN_HELP)
            elif role == "premium":
                safe_send(chat_id, PREMIUM_HELP)
            else:
                safe_send(chat_id, MEMBER_HELP)
            return
        
        elif cmd in ("/analysis", "/max"):
            # 🛡️ تحقق من الرتبة — فقط المميزين فما فوق
            if not is_premium(chat_id):
                safe_send(chat_id, "⭐ **هذه الميزة للمستخدمين المميزين فقط.**\n\nللاستفسار عن الترقية، تواصل مع المشرف.")
                return
            
            if len(args) < 2:
                usage = "/analysis BTC" if cmd == "/analysis" else "/max BTC"
                safe_send(chat_id, f"⚠️ **استخدم:** `{usage}`\nمثال: `{usage}`")
                return
            
            if not validate_symbol(args[1]):
                safe_send(chat_id, f"⚠️ **عملة غير صالحة:** `{args[1]}`\nمثال: `/analysis BTC`")
                return
            
            symbol = sanitize_symbol(args[1])
            is_arabic = (cmd == "/analysis")
            
            # Rate limit for non-admin
            if not is_admin_role:
                rl = check_rate_limit(chat_id)
                if not rl["allowed"]:
                    safe_send(chat_id, f"❌ استنفذت طلباتك. حاول بعد {rl['reset_in']}.")
                    return
                consume_rate_limit(chat_id)
            
            # Send waiting message
            safe_send(chat_id, f"🔍 **جاري تحليل {symbol.upper()}...** ⏳")
            
            # Run in background thread
            from bot.bot_trading import run_analyze
            threading.Thread(
                target=run_analyze,
                args=(chat_id, symbol),
                kwargs=({"full": (not is_arabic), "arabic": is_arabic}),
                daemon=True
            ).start()
            
            # Warning for rate limit
            if not is_admin_role:
                rl = check_rate_limit(chat_id)
                if rl["warning"]:
                    safe_send(chat_id, rl["warning"])
            return

        # ═══════════════════════════════════
        # ADMIN-ONLY COMMANDS (المالك والمشرفين فقط)
        # ═══════════════════════════════════

        if not is_admin_role:
            return

        if cmd == "/allow":
            if len(args) < 2:
                safe_send(chat_id, "⚠️ **استخدم:** `/allow NUMBER`\nمثال: `/allow 5`")
                return
            if not validate_limit(args[1]):
                safe_send(chat_id, "⚠️ **استخدم:** `/allow NUMBER` (1-1000)")
                return
            try:
                num = int(args[1])
                result = set_max_slots(num)
                safe_send(chat_id, result)
            except ValueError:
                safe_send(chat_id, "⚠️ **استخدم:** `/allow NUMBER`")
            return

        if cmd == "/broadcast":
            # إرسال رسالة جماعية لكل المشتركين — مع إيموجي Premium متحرك
            if len(args) < 2:
                safe_send(chat_id, "⚠️ **استخدم:** `/broadcast نص الرسالة`\n\nتقدر ترسل رسالة متعددة الأسطر مع ايموجيز متحركة 🎉")
                return
            msg_text = text.split(maxsplit=1)[1] if len(text.split(maxsplit=1)) > 1 else ""
            msg_text = msg_text[:1000]
            if not msg_text.strip():
                safe_send(chat_id, "⚠️ نص الرسالة فارغ.")
                return
            subs = load_subscribers()
            success = 0
            for uid in subs:
                if send_msg_premium(uid, msg_text):
                    success += 1
            safe_send(chat_id, f"✅ **تم الإرسال:** {success}/{len(subs)} مشترك")
            return

        elif cmd in ("/test", "/test_broadcast"):
            # إرسال اختباري — نفس نظام البث لكن للمالك فقط + إيموجي Premium
            if len(args) < 2:
                safe_send(chat_id, "⚠️ **استخدم:** `/test نص الرسالة`\n\nنفس نظام البث لكن لك فقط للاختبار.")
                return
            msg_text = text.split(maxsplit=1)[1] if len(text.split(maxsplit=1)) > 1 else ""
            if not msg_text.strip():
                safe_send(chat_id, "⚠️ نص الرسالة فارغ.")
                return
            mid = send_msg_premium(chat_id, msg_text)
            if mid:
                safe_send(chat_id, f"✅ **تم الإرسال لك فقط** (msg_id={mid})")
            else:
                safe_send(chat_id, "❌ **فشل الإرسال**")
            return

        elif cmd == "/adduser":
            if len(args) < 2:
                safe_send(chat_id, "⚠️ **استخدم:** `/adduser UID`\nمثال: `/adduser 123456789`")
                return
            if not validate_uid(args[1]):
                safe_send(chat_id, "⚠️ **UID غير صالح.** أدخل رقم صحيح موجب.")
                return
            try:
                uid = int(args[1])
                # تعيين رتبة مميز + مقعد
                add_uid_to_slots(uid)
                add_subscriber(uid, "", "")
                result = set_role(uid, "premium")
                # 🆕 حدث أوامر المستخدم الجديد
                set_user_commands(uid, "premium")
                safe_send(chat_id, result)
                # إشعار المستخدم
                try:
                    safe_send(uid, "🎉 **تم ترقيتك إلى مستخدم مميز!** ⭐\n\n📊 الآن يمكنك استخدام:\n/analysis BTC — تحليل عربي\n/max BTC — تقرير متقدم\n\nاستخدم /help لعرض جميع الأوامر.")
                except Exception as e:
                    logger.debug(f"Premium upgrade notification skipped for {uid}: {e}")
            except ValueError:
                safe_send(chat_id, "⚠️ **استخدم:** `/adduser UID`")
            return

        elif cmd == "/admin":
            if len(args) < 2:
                safe_send(chat_id, "⚠️ **استخدم:** `/admin UID`\nمثال: `/admin 123456789`")
                return
            if not validate_uid(args[1]):
                safe_send(chat_id, "⚠️ **UID غير صالح.** أدخل رقم صحيح موجب.")
                return
            try:
                uid = int(args[1])
                result = add_admin(uid)
                set_role(uid, "admin")
                # 🆕 حدث أوامر المشرف الجديد
                set_user_commands(uid, "admin")
                safe_send(chat_id, result)
            except ValueError:
                safe_send(chat_id, "⚠️ **استخدم:** `/admin UID`")
            return

        elif cmd == "/request":
            if len(args) < 3:
                safe_send(chat_id, "⚠️ **استخدم:** `/request 4h 5`\nمثال: `/request 4h 5` (5 طلبات كل 4 ساعات)")
                return
            if not validate_limit(args[2]):
                safe_send(chat_id, "⚠️ **العدد غير صالح.** أدخل رقماً من 1 إلى 1000.")
                return
            window_str = args[1]
            try:
                count = int(args[2])
                result = set_rate_limit(window_str, count)
                safe_send(chat_id, result)
            except ValueError:
                safe_send(chat_id, "⚠️ **استخدم:** `/request 4h 5`")
            return

        elif cmd == "/status":
            slots = get_slots_status()
            rate = read_rate_config()
            win_min = rate.get('window_seconds', 3600) // 60
            from data.data_fetcher import get_fetcher_status
            exchange_status = get_fetcher_status()
            info = (
                f"{slots}\n"
                f"📊 **الحد:** {rate.get('max_per_window', '?')} طلب / {win_min} دقيقة\n"
                f"🪪 **المعرف:** `{OWNER_ID}`\n\n"
                f"{exchange_status}"
            )
            safe_send(chat_id, info)
            return

        elif cmd == "/exchanges":
            from data.data_fetcher import get_fetcher_status
            safe_send(chat_id, get_fetcher_status())
            return

        elif cmd == "/scan":
            safe_send(chat_id, "🔍 **Scanning market...** ⏳")
            from bot.bot_trading import run_scan
            threading.Thread(target=run_scan, args=(chat_id,), daemon=True).start()
            return

        elif cmd == "/sectors":
            safe_send(chat_id, "📊 **Analyzing sectors...** ⏳")
            from bot.bot_trading import run_sectors
            threading.Thread(target=run_sectors, args=(chat_id,), daemon=True).start()
            return

        elif cmd in ("/matrix", "/top", "/rank"):
            safe_send(chat_id, "🔬 **Scanning strength matrix (30 coins × 3 TFs)...** (30-60s) ⏳")
            from bot.bot_trading import run_matrix
            threading.Thread(target=run_matrix, args=(chat_id,), daemon=True).start()
            return

        elif cmd == "/analyze":
            if len(args) < 2:
                safe_send(chat_id, "⚠️ **استخدم:** `/analyze BTC`")
                return
            if not validate_symbol(args[1]):
                safe_send(chat_id, f"⚠️ **عملة غير صالحة:** `{args[1]}`\nمثال: `/analyze BTC`")
                return
            symbol = sanitize_symbol(args[1])
            safe_send(chat_id, f"🔍 **Analyzing {symbol.upper()} across 3 TFs...** ⏳")
            from bot.bot_trading import run_analyze
            threading.Thread(target=run_analyze, args=(chat_id, symbol), kwargs={"full": True}, daemon=True).start()
            return

        # ─── Unknown command ───
        # Only owner sees unknown command errors
        safe_send(chat_id, f"⚠️ **أمر غير معروف:** `{cmd}`\nاستخدم /help لعرض الأوامر المتاحة.")

    except Exception as e:
        logger.error(f"Command handler error: {e}", exc_info=True)


# ─── Re-exports from bot_polling ───
from bot.bot_polling import (
    _load_polling_offset, _save_polling_offset,
    stop_polling, start_polling,
)
