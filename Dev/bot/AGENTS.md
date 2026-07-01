# bot/ — Telegram Bot Interface

11 files, 4.3K LOC. User-facing Telegram bot with manual command routing, role-based access, rate limiting, and trading scheduler.

## STRUCTURE

```
bot/
├── bot_main.py        # Entry point: main() → start_polling() + scheduler_loop()
├── bot_handlers.py    # handle_update() + handle_callback() — 1261 LOC (largest)
├── bot_trading.py     # scheduler_loop() + run_scan() + trade alerts (809 LOC)
├── bot_config.py      # Config hub: constants, roles, spam, paths, messages (487 LOC)
├── bot_messaging.py   # send_msg(), send_msg_premium(), send_msg_html(), init_all_commands()
├── bot_polling.py     # start_polling(): Telegram long-polling daemon thread
├── bot_admin.py       # load_admins(), add_admin(), subscriber/slot management
├── bot_ratelimit.py   # broadcast(), check_rate_limit(), rate limiting + spam
├── bot_keyboard.py    # Inline keyboard builders (360 LOC)
└── _archive/          # 8 files, 4.8K LOC — 100% DEAD CODE, 0 imports
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Command dispatch | `bot_handlers.py` → `handle_update()` | Manual if/elif chain, no decorators |
| Callback handling | `bot_handlers.py` → `handle_callback()` | Inline button press routing |
| Trading scheduler | `bot_trading.py` → `scheduler_loop()` | Forever loop: daily report, trade alerts, price updates |
| Run a manual scan | `bot_trading.py` → `run_scan()` | Triggered by `/scan` command |
| Send a message | `bot_messaging.py` → `send_msg()` | Also send_msg_premium/html |
| Init bot commands | `bot_messaging.py` → `init_all_commands()` | Registers with Telegram BotFather |
| Polling loop | `bot_polling.py` → `start_polling()` | Daemon thread, lazy imports for circular avoidance |
| Broadcast to all | `bot_ratelimit.py` → `broadcast()` | Rate-limited subscriber broadcast |
| Role/access control | `bot_admin.py` | Member/premium/admin/owner roles |
| Config constants | `bot_config.py` | BOT_TOKEN, DATA_DIR, messages, file paths, locks |
| Keyboard builders | `bot_keyboard.py` | Inline keyboard generators |

## CONVENTIONS

- **Wildcard imports**: `bot_main.py` uses `from bot.bot_config import *`, `from bot.bot_handlers import *`, `from bot.bot_trading import *`. Legacy pattern — symbols come from 3+ merged namespaces.
- **Re-export chains**: `bot_handlers.py` re-exports from `bot_admin.py`, `bot_ratelimit.py`, `bot_messaging.py`. A symbol like `broadcast` appears to come from `bot_handlers` but is defined elsewhere.
- **No decorator-based handlers**: All routing is manual string matching. No `@bot.message_handler` or `@app.route`.
- **Circular import avoidance**: `bot_polling.py` uses lazy `import` inside the polling loop.
- **Logging**: Standard `getLogger("yjcrypto-{component}")` (e.g., `"yjcrypto-bot"`). NOT structured JSON (different from core/). Renamed from `crypto-signal-*` in Wave 2.

## ANTI-PATTERNS

1. **`bot/_archive/` is 100% dead code** (4.8K LOC, 0 active imports). Do not edit. Do not reference.
2. **`bot_config.py` is a god module** (487 LOC) — mixes config, roles, spam, rate limiting, file persistence, and message templates.
3. **Wildcard imports make symbol tracing difficult** — when resolving a symbol in bot_main, check bot_config + bot_handlers + bot_trading.
4. **`except Exception` in trading** — `bot_trading.py` (lines 734, 776, 791) has silent error swallowing. Always log.
