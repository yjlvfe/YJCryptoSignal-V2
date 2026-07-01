# trade/ — Trade Lifecycle Management

6 files, 2.3K LOC. Trade tracking, position sizing, safety checks, portfolio heat. Cross-process safe via fcntl file locks. Consumed by both entry points.

## STRUCTURE

```
trade/
├── trade_tracker.py     # Trade CRUD: add/check/close/track, PnL, daily report (764 LOC)
├── trade_sizing.py      # Kelly Criterion + volatility-adjusted position sizing (755 LOC)
├── trade_safety.py      # Trade safety validation checks
├── trade_heat.py        # Portfolio heat exposure tracking
├── trade_userlists.py   # Per-user trade subscriptions + watchlists (437 LOC)
└── __init__.py          # Empty
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Add a trade | `trade_tracker.py` → `add_trade()` | JSON persistence + fcntl lock + PnL calc |
| Check active trades | `trade_tracker.py` → `check_trades()`, `get_active_trades()` | Cross-process safe |
| Daily report | `trade_tracker.py` → `generate_daily_report()` | Called by bot scheduler |
| Price updates | `trade_tracker.py` → `update_current_prices()` | Updates all active trade prices |
| Position sizing | `trade_sizing.py` | Kelly Criterion with volatility adjustment |
| Safety checks | `trade_safety.py` | Pre-trade validation |
| Portfolio heat | `trade_heat.py` | Total exposure tracking |
| User tracking lists | `trade_userlists.py` | Per-user subscribed symbols |

## CONVENTIONS

- **Persistence**: All state in JSON files under `DATA_DIR`. `_read_json()` / `_save_json()` with `fcntl.flock()`.
- **Imports**: Clean absolute imports. No wildcards.
- **Logging**: Standard `getLogger("yjcrypto-*")` — NOT structured JSON (different from core/). Renamed from `crypto-signal-*` in Wave 2.
- **Error handling**: Broad `except Exception as e` with `logger.error(f"Failed to ...: {e}")`. Default return values on failure.

## ANTI-PATTERNS

1. **`trade/trade_tracker.py` imports `bot.bot_config.POSITION_SIZE_PCT`** — creates trade→bot dependency (should be reversed or moved to shared config)
2. **`trade/trade_userlists.py` has a dead copy** at `bot/bot_userlists.py` (exact duplicate) and `bot/_archive/user_lists.py` (archived version)
3. **Hardcoded `DATA_DIR` fallback** in tracker — uses env var but falls back to `/root/.yjcryptosignal-bot`
