# engine/ — Trading Analysis Engines

14 active files, ~5.8K LOC. Largest module. **Zero direct tests — highest risk area.**

## STRUCTURE

```
engine/
├── ⚡ ACTIVE (engine_* prefix):
│   ├── engine_scanner.py      # CryptoScanner V2 (104 LOC)
│   ├── engine_multi_tf.py     # Multi-timeframe strength matrix
│   ├── engine_backtest.py     # Walk-forward backtest + Monte Carlo (968 LOC)
│   ├── engine_weights.py      # Strategy weight engine (483 LOC)
│   ├── engine_breakout.py     # BB squeeze + volume breakout + S/R retest (532 LOC)
│   ├── engine_liquidity.py    # Whale detection + CVD divergence + order book (597 LOC)
│   ├── engine_optimizer.py    # Genetic algorithm optimizer (602 LOC)
│   ├── engine_smart_entry.py  # Smart entry signals (374 LOC)
│   ├── engine_sentiment.py    # Sentiment analysis
│   ├── engine_kronos.py       # Kronos scoring system
│   ├── engine_layers.py       # Signal layer analysis — DISABLED
│   └── engine_volume_advanced.py  # Advanced volume analysis
│
├── ⚡ ACTIVE (no prefix):
│   ├── ai_calibrator.py       # AI score calibration
│   └── safety_walls.py        # Circuit breaker, daily loss caps, drawdown
│
└── ~~LEGACY~~ (All 11 deleted in Wave 4 — see WAVE 4 CLEANUP)
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Strategy analysis pipeline | `engine_scanner.py` → `core.core_analyzer` | Uses V2 analyzer |
| Multi-timeframe scanning | `engine_multi_tf.py` | Strength matrix for 1H/4H/1D |
| Backtesting 11 strategies | `engine_backtest.py` | Walk-forward + Monte Carlo |
| Breakout detection | `engine_breakout.py` | BB squeeze, volume breakout, S/R retest |
| Liquidity/whale analysis | `engine_liquidity.py` | CVD divergence, order book, volume climax |
| Genetic optimization | `engine_optimizer.py` | Strategy parameter GA |
| Circuit breaker | `safety_walls.py` | Daily loss caps, drawdown tracking, max trades |
| Smart entry signals | `engine_smart_entry.py` | Entry refinement |
| Sentiment analysis | `engine_sentiment.py` | Market sentiment indicators |
| AI calibration | `ai_calibrator.py` | AI score calibration |
| Volume analysis | `engine_volume_advanced.py` | Advanced volume indicators (used by strategies/cvd_strategy.py) |

## CONVENTIONS

- **Logging**: Standard `logging.getLogger("yjcrypto-{component}")` (NOT structured JSON). Renamed from `crypto-signal-*` in Wave 2.
- **Imports**: Absolute from project root. Mix of new (`from core.core_analyzer import Analyzer`) and old imports.
- **Error handling**: Broad `except Exception as e` with `logger.error()`. Several silent `pass` still exist.
- **Data classes**: Defined locally per file (`@dataclass` in backtest, breakout, liquidity, optimizer).

## ANTI-PATTERNS

1. **Zero tests** for any engine module. Changes must be manually verified.
2. **`except Exception: pass` still exists** — particularly in legacy files that remain. Always log.
3. **`engine/engine_layers.py` has `DISABLED` flag** — not operational.

## WAVE 2 & 4 CLEANUP

21 dead duplicates were deleted across Waves 2 and 4 (Jun 2026):
- **Wave 2 (9 files)**: `scanner.py`, `genetic_optimizer.py`, `smart_entry.py`, `sentiment.py`, `kronos.py`, `layers.py`, `smart_targets.py`, `universal_hunter.py`, `ai_analyst.py`
- **Wave 4 (11 files)**: `analyzer.py`, `backtesting.py`, `breakout_hunter.py`, `liquidity_intel.py`, `multi_analyzer.py`, `portfolio_heat.py`, `position_sizing_v2.py`, `self_learning_v2.py`, `volume_advanced.py`, `weights.py`, `regime.py`

All legacy imports have been migrated to canonical modules. Only active `engine_*` prefixed files remain. Always use the `engine_*` prefixed versions.
