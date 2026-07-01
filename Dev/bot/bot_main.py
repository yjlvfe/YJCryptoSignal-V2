#!/usr/bin/env python3
"""
🤖 CryptoSignal Bot — Entry Point with Observability
"""
import sys
import os
import time
import threading
from pathlib import Path

# 🔧 Load .env FIRST — before project imports so config.py sees BOT_TOKEN
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

# ⛔ File lock — single-instance guard
_lock_file = None

def _acquire_lock():
    global _lock_file
    _lock_file = open('/tmp/yjcryptosignal-bot.lock', 'w')
    try:
        import fcntl
        fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_file.write(str(os.getpid()))
        _lock_file.flush()
        return True
    except (IOError, OSError):
        print("Bot already running — exiting")
        return False

# ─── Ensure project root is on path ───
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ─── Observability: Metrics Server ───
try:
    from core.core_metrics_server import MetricsServer
    _bot_metrics_port = int(os.getenv("BOT_METRICS_PORT", "9091"))
    _bot_metrics_server = MetricsServer(host="0.0.0.0", port=_bot_metrics_port)
    _bot_metrics_server.start(blocking=False)
    print(f"📊 Bot metrics server started on :{_bot_metrics_port}", flush=True)
except Exception as e:
    print(f"⚠️ Bot metrics server failed: {e}", flush=True)
    _bot_metrics_server = None

# ─── Observability: Structured Logging ───
try:
    from core.core_logging import setup_json_logging, get_context_logger
    _bot_log_default = str(Path(__file__).resolve().parent.parent / "logs" / "bot.json")
    _bot_log_file = os.getenv("BOT_LOG_FILE", _bot_log_default)
    setup_json_logging("cryptosignal-bot", "INFO", log_file=_bot_log_file)
    BOT_LOGGER = get_context_logger("cryptosignal.bot", {"component": "bot"})
    HAS_STRUCTURED_LOGGING = True
except Exception as e:
    print(f"⚠️ Structured logging unavailable: {e}", flush=True)
    HAS_STRUCTURED_LOGGING = False
    BOT_LOGGER = None

# ─── Observability: Alerting ───
try:
    from utils.alerting import get_alert_manager, alert_info, alert_critical, alert_warning
    _alert_mgr = get_alert_manager()
    HAS_ALERTING = True
except Exception as e:
    print(f"⚠️ Alerting unavailable: {e}", flush=True)
    HAS_ALERTING = False

# ─── Observability: Bot Metrics ───
try:
    from core.core_metrics import record_bot_command, record_bot_message, set_active_subscribers
    HAS_BOT_METRICS = True
except Exception as e:
    print(f"⚠️ Bot metrics unavailable: {e}", flush=True)
    HAS_BOT_METRICS = False

# ─── Imports (after observability setup) ───
from bot.bot_config import *
from bot.bot_handlers import *
from bot.bot_trading import *

import logging
logger = logging.getLogger("yjcrypto-bot")

# ─── Entry Point ───
def main():
    """Start the bot: init commands, then enter scheduler loop."""
    logger.info("🤖 CryptoSignal Bot starting...")
    
    # Alert on startup
    if HAS_ALERTING:
        alert_info("Bot started", source="bot", tags={"version": "3.0.0"})
    
    # Initialize Telegram commands
    try:
        init_all_commands()
    except Exception as e:
        logger.error(f"Command initialization failed: {e}")
        if HAS_ALERTING:
            alert_critical(f"Command init failed: {e}", source="bot")
    
    # Start Telegram message polling
    start_polling()
    
    # Start the trading scheduler (runs forever)
    scheduler_loop()

if __name__ == "__main__":
    if not _acquire_lock():
        sys.exit(0)
    
    if "--once" in sys.argv:
        import requests
        bot_info = requests.get(f"{API_BASE}/getMe").json()
        logger.info(f"Bot: {bot_info}")
        subs = load_subscribers()
        logger.info(f"Subscribers: {subs}")
    else:
        main()