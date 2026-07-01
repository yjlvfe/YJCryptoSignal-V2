"""CryptoSignal Bot — Telegram Polling Loop

Domain: long-polling for Telegram updates, offset persistence, graceful shutdown.
Extracted from bot_handlers.py to reduce module size.
"""
import atexit, json, logging, threading, time
import requests
from bot.bot_config import API_BASE, POLLING_OFFSET_FILE

logger = logging.getLogger("yjcrypto-bot")

_polling_started = False
_polling_stop = threading.Event()


def _load_polling_offset() -> int:
    """Load last processed update_id to avoid re-processing."""
    try:
        if POLLING_OFFSET_FILE.exists():
            return json.loads(POLLING_OFFSET_FILE.read_text()).get("offset", 0)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Polling offset load failed: {e}")
    return 0


def _save_polling_offset(offset: int):
    """Save last processed update_id."""
    try:
        POLLING_OFFSET_FILE.write_text(json.dumps({"offset": offset}))
    except Exception as e:
        logger.debug(f"Failed to save polling offset: {e}")


def stop_polling():
    """Signal polling thread to stop, save offset, and wait."""
    _polling_stop.set()
    _save_polling_offset(getattr(stop_polling, '_last_offset', 0))
    _poll_thread = getattr(stop_polling, '_thread', None)
    if _poll_thread and _poll_thread.is_alive():
        _poll_thread.join(timeout=5)
    logger.info("✅ Telegram polling stopped")


def start_polling():
    """Start Telegram update polling in a daemon thread."""
    global _polling_started
    if _polling_started:
        logger.warning("⚠️ Polling already started — ignoring duplicate call")
        return
    _polling_started = True
    _polling_stop.clear()
    logger.info("📡 Starting Telegram polling...")
    
    def _poll():
        offset = _load_polling_offset()
        failures = 0
        time.sleep(1)  # ⏳ Short delay to let old Telegram sessions expire
        
        while not _polling_stop.is_set():
            try:
                url = f"{API_BASE}/getUpdates?timeout=15&offset={offset + 1}"
                resp = requests.get(url, timeout=20)
                data = resp.json()
                
                if not data.get("ok"):
                    error_code = data.get("error_code", 0)
                    logger.warning(f"getUpdates failed: {data}")
                    failures += 1
                    # 409 = conflict — reset offset + wait for session to die
                    if error_code == 409:
                        offset = _load_polling_offset()  # fresh load
                        _save_polling_offset(max(0, offset - 100))  # big rewind
                        failures = 0
                        logger.info(f"🔄 409 conflict — reset session, sleeping 5s...")
                        if _polling_stop.wait(5):
                            break
                        continue
                    elif error_code == 429:
                        retry_after = (data.get("parameters") or {}).get("retry_after", 10)
                        logger.warning(f"⏳ 429 Rate limited — waiting {retry_after}s...")
                        if _polling_stop.wait(retry_after):
                            break
                        continue
                
                failures = 0
                # Lazy import to avoid circular dependency at module level
                from bot.bot_handlers import handle_update
                for update in data.get("result", []):
                    uid = update.get("update_id", 0)
                    if uid > offset:
                        offset = uid
                        # 💾 Save offset every update (critical for avoiding reprocessing)
                        if offset % 5 == 0:
                            _save_polling_offset(offset)
                        threading.Thread(
                            target=handle_update,
                            args=(update,),
                            daemon=True
                        ).start()
                
                # 💾 Always save the last offset after processing a batch
                if data.get("result"):
                    _save_polling_offset(offset)
                stop_polling._last_offset = offset

            except requests.exceptions.Timeout:
                stop_polling._last_offset = offset
                continue  # Normal long-poll timeout
            except Exception as e:
                logger.error(f"Polling error: {e}", exc_info=True)
                failures += 1
                if _polling_stop.wait(min(failures * 5, 60)):
                    break
    
    t = threading.Thread(target=_poll, daemon=True, name="telegram-polling")
    stop_polling._thread = t
    t.start()
    atexit.register(stop_polling)
    logger.info("✅ Telegram polling thread started")
