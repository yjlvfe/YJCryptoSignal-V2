"""
🧠 YJCryptoSignal — Core AI Analyst
Multi-Provider AI Router with Auto-Failover & Key Rotation
Reads ALL provider config from .env — never hardcodes keys.

Sub-modules:
  core/providers.py  — Provider loading, config, runtime state
  core/ai_client.py  — HTTP session, retry, _call_ai
  core/ai_parser.py  — Response parsing (Arabic + JSON)
  core/ai_prompts.py — System prompt constants
"""
import json
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger("yjcrypto-core-ai")

# ═══════════════════════════════════════════════════════════════
# Internal imports (used by functions in this module)
# ═══════════════════════════════════════════════════════════════
from core.ai_client import _call_ai
from core.ai_parser import _extract_arabic_decision, _parse_ai_response, _fallback_analysis
from core.providers import AI_MAX_TOKENS

# ═══════════════════════════════════════════════════════════════
# Prompt constants (imported from dedicated module)
# ═══════════════════════════════════════════════════════════════
from core.ai_prompts import AI_ANALYST_PURE_SYSTEM, AI_ANALYST_SYSTEM  # noqa: F401

# ═══════════════════════════════════════════════════════════════
# Public API re-exports (backward-compatible)
# ═══════════════════════════════════════════════════════════════
from core.ai_client import call_ai  # noqa: F401
from core.providers import (  # noqa: F401
    get_provider_status,
    force_provider_recovery,
    health_check,
)


# ═══════════════ Public Analysis Functions ═══════════════
def analyze_coin(
    symbol: str,
    price: float,
    signals: list,
    regime_data: dict,
    df_recent: dict = None,
    sector_data: dict = None,
    liquidity_intel: dict = None,
    breakout_data: dict = None,
    btc_correlation: dict = None,
) -> dict:
    """AI performs comprehensive multi-school analysis and returns trading decision."""
    # Build strategy summary
    buy_signals = []
    sell_signals = []
    neutral_signals = []

    for s in signals:
        entry = f"{s.name}: {s.signal}"
        if s.reason:
            entry += f" ({s.reason[:60]})"
        if s.signal == "BUY":
            buy_signals.append(entry)
        elif s.signal == "SELL":
            sell_signals.append(entry)
        else:
            neutral_signals.append(entry)

    regime = regime_data.get("regime", "?")
    entry_filter = regime_data.get("entry_filter", "?")

    # Price context
    price_context = ""
    if df_recent and len(df_recent) >= 20:
        closes = list(df_recent["close"].values)
        highs = list(df_recent["high"].values)
        lows = list(df_recent["low"].values)
        chg_24h = ((closes[-1] - closes[0]) / closes[0] * 100) if closes[0] > 0 else 0
        hi_24h = max(highs)
        lo_24h = min(lows)
        price_context = f"24h: ${lo_24h:.2f} → ${hi_24h:.2f} | تغير: {chg_24h:+.1f}%"

    sector_context = ""
    if sector_data:
        sector_context = f"القطاع: {sector_data.get('sector','?')} | التدفق: {sector_data.get('flow','?')}"

    # Liquidity context
    liq_context = ""
    if liquidity_intel and liquidity_intel.get("status") != "insufficient_data":
        liq_score = liquidity_intel.get("liquidity_score", 50)
        liq_bias = liquidity_intel.get("bias", "NEUTRAL")
        liq_alerts = liquidity_intel.get("alerts", [])
        liq_context = f"💧 السيولة: {liq_score}/100 ({liq_bias})"
        if liq_alerts:
            liq_context += f" | تنبيهات: {'; '.join(liq_alerts[:3])}"

    # Breakout context
    brk_context = ""
    if breakout_data and breakout_data.get("status") != "insufficient_data":
        brk_score = breakout_data.get("breakout_score", 30)
        brk_alerts = breakout_data.get("alerts", [])
        brk_context = f"🎯 الاختراق: {brk_score}/100"
        if brk_alerts:
            brk_context += f" | {'; '.join(brk_alerts[:2])}"

    # BTC correlation context
    corr_context = ""
    if btc_correlation:
        corr_val = btc_correlation.get("correlation_30d", 0)
        corr_cls = btc_correlation.get("classification", "?")
        corr_context = f"🔗 ارتباط BTC: {corr_val:.0%} ({corr_cls})"

    # Compose user prompt
    if price_context:
        user_prompt = f"""تحليل {symbol} @ ${price:.2f}

📊 **إشارات الاستراتيجيات (11 مدرسة):**
✅ شراء ({len(buy_signals)}): {'; '.join(buy_signals) if buy_signals else 'لا يوجد'}
❌ بيع ({len(sell_signals)}): {'; '.join(sell_signals) if sell_signals else 'لا يوجد'}
⚪ محايد ({len(neutral_signals)}): {len(neutral_signals)} استراتيجية

🌊 **حالة السوق:**
النظام: {regime} | فلتر الدخول: {entry_filter}

📈 **السعر:** {price_context}
🏛️ {sector_context}
{liq_context}
{brk_context}
{corr_context}

حلل عبر المدارس الستة. القرار؟"""
    else:
        user_prompt = f"""تحليل {symbol} @ ${price:.2f}

📊 **إشارات الاستراتيجيات:**
✅ شراء ({len(buy_signals)}): {'; '.join(buy_signals) if buy_signals else 'لا يوجد'}
❌ بيع ({len(sell_signals)}): {'; '.join(sell_signals) if sell_signals else 'لا يوجد'}
⚪ محايد: {len(neutral_signals)} استراتيجية

🌊 **السوق:** {regime}
{liq_context}
{brk_context}
{corr_context}

حلل عبر المدارس الستة وأعطي القرار."""

    response = _call_ai(AI_ANALYST_SYSTEM, user_prompt, max_tokens=AI_MAX_TOKENS)

    if not response:
        return _fallback_analysis(symbol, price, signals, regime_data)

    return _parse_ai_response(response, symbol, price, signals)


def analyze_coin_pure(
    symbol: str,
    price: float,
    df_4h,
    regime_data: dict = None,
    liquidity_intel: dict = None,
    breakout_data: dict = None,
    btc_correlation: dict = None,
) -> dict:
    """PURE AI market analysis — NO mechanical pre-filtering."""
    if df_4h is None or len(df_4h) < 20:
        return {
            "decision": "SKIP", "direction": "NEUTRAL", "confidence": 0,
            "entry": price, "stop_loss": price * 0.95, "targets": [],
            "risk_level": "HIGH",
            "reason": "بيانات غير كافية للتحليل", "schools_agreeing": 0, "key_signal": "",
        }

    closes = list(df_4h["close"].values)
    highs = list(df_4h["high"].values)
    lows = list(df_4h["low"].values)
    volumes = list(df_4h["volume"].values) if "volume" in df_4h.columns else []

    n = len(closes)
    sma20 = sum(closes[-20:]) / 20 if n >= 20 else price
    sma50 = sum(closes[-50:]) / 50 if n >= 50 else price

    # ATR approximation (14-period)
    tr_values = []
    for i in range(1, min(15, n)):
        hl = highs[-i] - lows[-i]
        hc = abs(highs[-i] - closes[-i-1]) if i < n else 0
        lc = abs(lows[-i] - closes[-i-1]) if i < n else 0
        tr_values.append(max(hl, hc, lc))
    atr = sum(tr_values) / len(tr_values) if tr_values else price * 0.02

    vol_recent = sum(volumes[-5:]) / 5 if len(volumes) >= 5 else sum(volumes) / max(len(volumes), 1)
    vol_hist = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else vol_recent
    vol_ratio = vol_recent / vol_hist if vol_hist > 0 else 1.0

    chg_4c = ((closes[-1] - closes[-4]) / closes[-4] * 100) if n >= 4 else 0
    chg_20c = ((closes[-1] - closes[-20]) / closes[-20] * 100) if n >= 20 else 0
    recent_high = max(highs[-20:]) if n >= 20 else max(highs)
    recent_low = min(lows[-20:]) if n >= 20 else min(lows)

    regime = regime_data.get("regime", "?") if regime_data else "?"
    entry_filter = regime_data.get("entry_filter", "?") if regime_data else "?"

    liq_context = ""
    if liquidity_intel and liquidity_intel.get("status") != "insufficient_data":
        liq_bias = liquidity_intel.get("bias", "NEUTRAL")
        liq_score = liquidity_intel.get("liquidity_score", 50)
        liq_context = f"💧 سيولة: {liq_score}/100 ({liq_bias})"

    brk_context = ""
    if breakout_data and breakout_data.get("status") != "insufficient_data":
        brk_score = breakout_data.get("breakout_score", 30)
        brk_context = f"🎯 اختراق: {brk_score}/100"

    vol_desc = "مرتفع" if vol_ratio > 1.5 else "عادي" if vol_ratio > 0.7 else "منخفض"
    regime_str = f"{regime} ({entry_filter})" if regime_data else "?"

    user_prompt = f"""🔍 تحليل {symbol}
━━━━━━━━━━━━━━━━━━━━━
السعر: ${price:.4f}
SMA20: ${sma20:.4f}
SMA50: ${sma50:.4f}
ATR: ${atr:.2f} ({atr/price*100:.2f}% من السعر)
القمة 24h: ${recent_high:.4f}
القاع 24h: ${recent_low:.4f}
التغير 4 شمعات: {chg_4c:+.2f}%
التغير 20 شمعة: {chg_20c:+.2f}%
الحجم: {vol_desc} (x{vol_ratio:.1f})
السوق: {regime_str}
{liq_context} {brk_context}

حلل بالمدارس الستة وحدد:
1. هل ندخل ENTER أو SKIP؟
2. هل الاتجاه BUY أم SELL؟
3. الثقة من 0-100؟
4. سعر وقف الخسارة بالدولار (رقم محدد)
5. 3 أهداف سعرية بالدولار (أرقام محددة)
6. المدة المتوقعة لتحقيق أول هدف: كم ساعة؟ (رقم فقط، لا تكتب "ساعة")
7. سبب التحليل بجملة عربية مختصرة

🛑 تذكر: المدة رقم فقط. وقف الخسارة سعر محدد بالدولار. الأهداف أسعار محددة بالدولار."""

    response = _call_ai(AI_ANALYST_PURE_SYSTEM, user_prompt, max_tokens=2500)

    if not response:
        return {
            "decision": "SKIP", "direction": "NEUTRAL", "confidence": 0,
            "entry": price, "stop_loss": price * 0.95, "targets": [],
            "risk_level": "HIGH",
            "reason": "AI غير متاح — تحليل يدوي", "schools_agreeing": 0, "key_signal": "",
        }

    return _extract_arabic_decision(response, symbol, price)


def compare_opportunities(
    candidates: list,
    regime_data: dict = None,
    max_recommendations: int = 2,
) -> dict:
    """AI compares multiple coin opportunities and ranks them."""
    if not candidates:
        return {"recommendations": [], "summary": "لا توجد فرص للمقارنة", "best_pick": ""}

    if len(candidates) == 1:
        c = candidates[0]
        return {
            "recommendations": [{"symbol": c["symbol"], "action": "ENTER_NOW", "priority": 1}],
            "summary": f"فرصة وحيدة: {c['symbol']}",
            "best_pick": c["symbol"],
        }

    prompt_lines = ["🔍 مقارنة فرص تداول:", "━━━━━━━━━━━━━━━━━━━━━"]
    for i, c in enumerate(candidates[:8], 1):
        liq = f" | سيولة: {c.get('liquidity_score', '?')}" if 'liquidity_score' in c else ""
        brk = f" | اختراق: {c.get('breakout_score', '?')}" if 'breakout_score' in c else ""
        prompt_lines.append(
            f"{i}. {c['symbol']} @ ${c['price']:.4f} | {c['direction']} | ثقة: {c.get('confidence', '?')}%{liq}{brk}"
        )

    prompt = "\n".join(prompt_lines) + f"\n\nاختر أفضل {max_recommendations} فرص فقط. رتبهم بالأولوية."
    response = _call_ai(AI_ANALYST_SYSTEM, prompt, max_tokens=800)

    if not response:
        return {
            "recommendations": [
                {"symbol": c["symbol"], "action": "ENTER_NOW" if c.get("direction") == "BUY" else "AVOID", "priority": i+1}
                for i, c in enumerate(candidates[:max_recommendations])
            ],
            "summary": f"AI غير متاح — افتراضي: {len(candidates)} فرص",
            "best_pick": candidates[0]["symbol"] if candidates else "",
        }

    # Parse response for recommendations
    import re
    recommendations = []
    for line in response.split('\n'):
        line = line.strip()
        m = re.search(r'(\d+)[\.\s]+(\w+USDT?)[\s|:]+(ENTER|AVOID|WAIT|شراء|بيع)', line, re.IGNORECASE)
        if m:
            priority = int(m.group(1))
            symbol = m.group(2).upper()
            action_raw = m.group(3).upper()
            action_map = {"ENTER": "ENTER_NOW", "شراء": "ENTER_NOW", "BUY": "ENTER_NOW", "AVOID": "AVOID", "WAIT": "WAIT", "بيع": "AVOID", "SELL": "AVOID"}
            action = action_map.get(action_raw, "WAIT")
            recommendations.append({"symbol": symbol, "action": action, "priority": priority})

    if not recommendations:
        recommendations = [
            {"symbol": c["symbol"], "action": "ENTER_NOW" if c.get("direction") == "BUY" else "AVOID", "priority": i+1}
            for i, c in enumerate(candidates[:max_recommendations])
        ]

    recommendations.sort(key=lambda x: x["priority"])
    return {
        "recommendations": recommendations[:max_recommendations],
        "summary": response[:200],
        "best_pick": recommendations[0]["symbol"] if recommendations else (candidates[0]["symbol"] if candidates else ""),
    }


def enrich_with_modules(symbol: str, df: "pd.DataFrame", cvd=None) -> dict:
    """
    Run all enrichment modules on a coin and return combined data.

    Args:
        symbol: e.g., 'BTCUSDT'
        df: OHLCV DataFrame

    Returns:
        dict with liquidity_intel, breakout_data
    """
    result = {}

    try:
        from engine.engine_liquidity import gather_liquidity_intel
        result["liquidity_intel"] = gather_liquidity_intel(df, cvd=cvd, symbol=symbol)
    except Exception as e:
        logger.debug(f"Liquidity intel failed for {symbol}: {e}")
        result["liquidity_intel"] = None

    try:
        from engine.engine_breakout import hunt_breakouts
        result["breakout_data"] = hunt_breakouts(df, symbol=symbol)
    except Exception as e:
        logger.debug(f"Breakout hunt failed for {symbol}: {e}")
        result["breakout_data"] = None

    return result
