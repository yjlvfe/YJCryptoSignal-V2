# strategies/ — 11 Technical Analysis Strategies

13 files, 1.9K LOC. Pure pandas/numpy technical analysis. No AI. Each strategy inherits `BaseStrategy`, produces `Signal` dataclass. Consumed by `core/core_analyzer.py` (11-strategy ensemble).

## STRUCTURE

```
strategies/
├── base.py                  # BaseStrategy ABC + Signal dataclass (60 LOC)
├── smc.py                   # Smart Money Concepts (433 LOC) — most complex
├── market_structure.py      # Market structure analysis (375 LOC)
├── macd_strategy.py         # MACD crossover + histogram
├── rsi_strategy.py          # RSI overbought/oversold + divergence
├── atr_analyzer.py          # ATR volatility-based
├── moving_average.py        # MA cross + MA ribbon
├── cvd_strategy.py          # CVD divergence (❌ imports engine.volume_advanced)
├── obv_cmf.py               # OBV/CMF volume flow
├── vwap.py                  # VWAP deviation
├── support_resistance.py    # S/R levels + breakouts
├── divergence.py            # Hidden/regular divergence detection
└── __init__.py              # Empty (no re-exports)
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| Base class + Signal | `base.py` | `BaseStrategy.detect_trend()`, `get_pivot_points()`, `Signal(name, signal, strength, entry, sl, targets, confidence)` |
| Strategy registry | `core/core_analyzer.py` (NOT here) | `ALL_STRATEGIES` list + `CLUSTERS` dict in core/ |
| New strategy template | `base.py` + any existing strategy | Inherit BaseStrategy, return Signal |

## CONVENTIONS

- **Relative import**: `from .base import BaseStrategy, Signal` — ONLY place in project using relative imports
- **Signal dataclass**: Universal signal type used across entire pipeline (scanner → analyzer → trade), defined here in `base.py`
- **Strategy interface**: Each strategy = class inheriting `BaseStrategy`, implements `analyze(data: pd.DataFrame) -> Signal`
- **No external dependencies**: Pure pandas/numpy analysis. No AI calls.
- **Timeframes**: Each strategy can run on 1H/4H/1D data (fed by caller)
- **Tests**: 5 of 11 strategies have tests in `tests/test_strategies.py`:

| Strategy | Tested |
|----------|--------|
| smc.py | ✅ 7 tests |
| market_structure.py | ✅ 6 tests |
| rsi_strategy.py | ⚠️ 1 test |
| macd_strategy.py | ⚠️ 1 test |
| atr_analyzer.py, moving_average.py, cvd_strategy.py, obv_cmf.py, vwap.py, support_resistance.py, divergence.py | ❌ No tests |

## ANTI-PATTERNS

1. **`cvd_strategy.py` imports from `engine.volume_advanced`** — creates a strategies→engine dependency that shouldn't exist (strategies should be pure)
2. **No type hints** on most strategy functions
3. **No BaseStrategy abstract methods enforced** — Python ABC but `analyze()` isn't abstract
