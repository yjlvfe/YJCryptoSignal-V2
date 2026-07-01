# data/ — Exchange Data Fetchers

3 active files, 1.5K LOC. Multi-exchange market data with automatic fallback. I/O boundary between the system and 5 crypto exchanges. Consumed by scanner and bot.

## STRUCTURE

```
data/
├── data_fetcher.py       # get_fetcher(), fetch_klines(), fetch_multi_timeframe() — 5-exchange fallback
├── data_exchanges.py     # exchange_available(), exchange_has_symbol(), exchange_has_usdt()
├── __init__.py           # Re-exports
└── ~~fetcher.py~~, ~~exchanges.py~~ ✅ Deleted (Wave 4)
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Fetch OHLCV data | `data_fetcher.py` → `fetch_klines()` | 200 candles default, multi-exchange |
| Multi-timeframe fetch | `data_fetcher.py` → `fetch_multi_timeframe()` | Returns dict of {tf: df} |
| Get top volume pairs | `data_fetcher.py` → `get_top_volume_pairs()` | Top N by volume |
| Check exchange health | `data_exchanges.py` → `exchange_available()` | Returns bool per exchange |
| Check if symbol exists | `data_exchanges.py` → `exchange_has_symbol()` | Binance-style symbol check |

## CONVENTIONS

- **Exchange fallback order**: MEXC → OKX → Gate → KuCoin → Bitget (defined in `EXCHANGE_ORDER`)
- **Return format**: All functions return `pd.DataFrame` with OHLCV columns, or `{}`/empty on failure
- **No persistence**: Fetched data is ephemeral (not cached to disk). Wave 3 L-03 proposes Redis caching.
- **Exchange auth**: API keys read from `.env` (`EXCHANGE_{NAME}_API_KEY` / `EXCHANGE_{NAME}_API_SECRET`)
- **Logging**: Standard `getLogger("yjcrypto-data")`. NOT structured JSON.
- **Rate limiting**: Exchange-specific rate limit handling inside each provider class

## ANTI-PATTERNS

1. **`except Exception: pass` occurs in some provider methods** — limits debuggability of exchange API issues
2. **No data caching** — each scan cycle re-fetches all klines from exchanges (expensive; Wave 3 L-03 added optional Redis cache)

## TEST COVERAGE

- `test_data_fetcher.py`: 10 tests — covers fetch_klines (cached + uncached), Redis caching, multi-timeframe, top volume pairs, MEXC symbol mapping, OKX kline parsing
- **Missing tests**: Exchange fallback logic, rate limit handling, error recovery, `data_exchanges.py` (0 tests)
