"""
📋 YJCryptoSignal — AI Response Parser
Extracts trading decisions from AI responses (Arabic + JSON formats).
"""
import json
import re
import logging

logger = logging.getLogger("yjcrypto-core-ai")


def _extract_arabic_decision(text: str, symbol: str, price: float) -> dict:
    """استخراج القرار من تحليل AI بالعربية."""
    lines = text.split('\n')

    decision = "SKIP"
    direction = "NEUTRAL"
    confidence = 0
    stop_loss = price * 0.95
    targets = []
    reason = text[:500]
    duration_hours = None

    # Phase 1: Extract from formatted decision section
    for line in lines:
        line = line.strip()
        if not line or 'أو' in line or ('سعر' in line and 'وقف' not in line):
            continue

        clean = line.replace('**', '')

        m = re.search(r'القرار\s*[:\\=-]\s*(ENTER|SKIP|دخول|تجاهل)', clean, re.IGNORECASE)
        if m:
            raw = m.group(1).upper()
            if raw in ('ENTER', 'دخول'):
                decision = 'ENTER'
            else:
                decision = 'SKIP'

        m = re.search(r'الاتجاه\s*[:\\=-]\s*(BUY|SELL|شراء|بيع|صاعد|هابط|هبوطي)', clean, re.IGNORECASE)
        if m:
            raw = m.group(1).upper()
            if raw in ('BUY', 'شراء', 'صاعد'):
                direction = 'BUY'
            elif raw in ('SELL', 'بيع', 'هابط', 'هبوطي'):
                direction = 'SELL'

        m = re.search(r'الثقة\s*[:\\=-]\s*(\d+)', clean)
        if m:
            confidence = min(int(m.group(1)), 100)

        m = re.search(r'وقف\s*(الخسارة)?\s*[:\\=-]\s*([\d.]+)', clean)
        if m:
            try:
                stop_loss = float(m.group(2))
            except (ValueError, TypeError):
                logger.debug(f"Stop-loss regex parse failed for {symbol}")

        m = re.search(r'الأهداف\s*[:\\=-]\s*([\d.\s,،]+)', clean)
        if m:
            nums = re.findall(r'[\d.]+', m.group(1))
            targets = [float(n) for n in nums[:3] if n]

        m = re.search(r'السبب\s*[:\\-]\s*(.+)', clean)
        if m:
            candidate = m.group(1).strip()
            if 'كلمة' not in candidate and len(candidate) > 10:
                reason = candidate

    # Extract duration
    for line in lines:
        clean = line.replace('**', '').strip()
        m = re.search(r'المدة\s*[:\\-]?\s*(\d+)', clean)
        if m:
            duration_hours = min(int(m.group(1)), 168)
            break

    # Phase 2: Fallback text analysis
    if direction == "NEUTRAL" or confidence == 0:
        text_lower = text.lower()

        bullish_words = ['صاعد', 'bull', 'شراء', 'buy', 'قوي', 'إيجابي', 'اختراق', 'مقاومة', 'ارتفاع', 'صعود', 'أعلى']
        bearish_words = ['هابط', 'هبوطي', 'bear', 'بيع', 'sell', 'ضعيف', 'سلبي', 'دعم', 'انخفاض', 'هبوط', 'تصحيح', 'أدنى']

        bull_score = sum(1 for w in bullish_words if w in text_lower)
        bear_score = sum(1 for w in bearish_words if w in text_lower)

        if bull_score > bear_score + 1:
            direction = 'BUY'
            confidence = min(50 + bull_score * 8, 95)
        elif bear_score > bull_score + 1:
            direction = 'SELL'
            confidence = min(50 + bear_score * 8, 95)

        sl_text = re.findall(r'وقف[^0-9]*([\d.]+)', text)
        if sl_text:
            try:
                v = float(sl_text[-1])
                if price * 0.5 < v < price * 1.5:
                    stop_loss = v
            except (ValueError, TypeError):
                logger.debug(f"Stop-loss fallback parse failed for {symbol}")

        tp_text = re.findall(r'هدف[^0-9]*([\d.]+)', text)
        if tp_text and len(targets) == 0:
            targets = [float(t) for t in tp_text[:3] if price * 0.5 < float(t) < price * 1.5]

        if 'كلمة' in reason or len(reason) < 10:
            paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 50]
            if paragraphs:
                reason = paragraphs[-1][:500]
            else:
                reason = text[-500:]

    # Final validation
    if direction == "NEUTRAL" or confidence < 20:
        return {
            "decision": "SKIP", "direction": "NEUTRAL", "confidence": 0,
            "entry": price, "stop_loss": price * 0.95,
            "targets": [], "risk_level": "HIGH",
            "reason": reason[:500], "schools_agreeing": 0, "key_signal": "",
            "duration_hours": duration_hours or 24,
        }

    if direction == "SELL" and stop_loss < price:
        stop_loss = price * 1.02
    elif direction == "BUY" and stop_loss > price:
        stop_loss = price * 0.98

    risk = "LOW" if confidence > 70 else "MEDIUM" if confidence > 45 else "HIGH"

    return {
        "decision": decision,
        "direction": direction,
        "confidence": confidence,
        "entry": price,
        "stop_loss": round(stop_loss, 8),
        "targets": [round(t, 8) for t in targets[:3]],
        "risk_level": risk,
        "reason": reason[:500],
        "schools_agreeing": 1,
        "key_signal": "",
        "duration_hours": duration_hours or 24,
    }


def _parse_ai_response(response: str, symbol: str, price: float, signals: list) -> dict:
    """Parse AI response, extracting JSON or falling back to text analysis."""
    # Try extracting from ```json code block first
    json_str = None
    if "```json" in response:
        start = response.find("```json") + 7
        end = response.find("```", start)
        if end > start:
            json_str = response[start:end].strip()

    # Fallback: find any JSON object
    if not json_str:
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            json_str = response[start:end]

    if json_str:
        try:
            data = json.loads(json_str)
            entry_val = data.get("entry", price)
            if entry_val is None:
                entry_val = price
            elif isinstance(entry_val, str):
                try:
                    entry_val = float(entry_val)
                except (ValueError, TypeError):
                    entry_val = price
            sl_val = data.get("stop_loss", price * 0.95)
            if sl_val is None:
                sl_val = price * 0.95
            elif isinstance(sl_val, str):
                try:
                    sl_val = float(sl_val)
                except (ValueError, TypeError):
                    sl_val = price * 0.95
            targets = data.get("targets", [])
            if isinstance(targets, list) and len(targets) > 0:
                targets = [float(t) if not isinstance(t, str) or t.replace('.', '').replace('-', '').isdigit()
                          else price * (1.01 + i*0.01) for i, t in enumerate(targets[:3])]
            else:
                targets = []
            return {
                "decision": str(data.get("decision", "SKIP")).upper(),
                "direction": str(data.get("direction", "NEUTRAL")).upper(),
                "confidence": int(float(data.get("confidence", 50))),
                "entry": float(entry_val),
                "stop_loss": float(sl_val),
                "targets": targets,
                "risk_level": data.get("risk_level", "MEDIUM"),
                "reason": data.get("reason", response[:200]),
                "schools_agreeing": int(data.get("schools_agreeing", 0)),
                "key_signal": data.get("key_signal", ""),
                "ai_raw": response[:500],
            }
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.debug(f"JSON parse failed: {e} — trying text fallback")

    # Fallback: extract decision from text
    return _fallback_analysis(symbol, price, signals, {"regime": "?"}, response)


def _fallback_analysis(symbol: str, price: float, signals: list,
                       regime_data: dict = None, ai_text: str = "") -> dict:
    """Fallback when AI fails — use vote count or extract from text."""
    buys = sum(1 for s in signals if s.signal == "BUY")
    sells = sum(1 for s in signals if s.signal == "SELL")
    total = buys + sells

    if total > 0:
        direction = "BUY" if buys > sells else "SELL"
        agreement = max(buys, sells) / total
        confidence = agreement * 50
        sl = price * 0.95 if direction == "BUY" else price * 1.05
        return {
            "decision": "ENTER" if agreement > 0.6 else "SKIP",
            "direction": direction,
            "confidence": round(confidence, 1),
            "entry": price,
            "stop_loss": round(sl, 8),
            "targets": [],
            "risk_level": "LOW" if agreement > 0.8 else "MEDIUM" if agreement > 0.6 else "HIGH",
            "reason": ai_text[:200] or f"تصويت: {buys} شراء vs {sells} بيع",
            "schools_agreeing": max(buys, sells),
            "key_signal": "",
        }

    # Pure AI mode — no signals, try extracting from AI text
    if ai_text:
        text = ai_text.lower()

        has_enter = any(w in text for w in ["enter", "دخول", "شراء", "buy"])
        has_skip = any(w in text for w in ["skip", "تجاهل", "انتظار", "لا تدخل", "لا يوجد"])
        decision = "ENTER" if has_enter and not has_skip else "SKIP"

        has_buy = any(w in text for w in ["buy", "شراء", "bull", "صاعد", "طويل"])
        has_sell = any(w in text for w in ["sell", "بيع", "bear", "هابط", "قصير"])
        direction = "BUY" if has_buy and not has_sell else "SELL" if has_sell and not has_buy else "NEUTRAL"

        conf = 0
        conf_patterns = [
            r"confidence[:\\s]+(\d+)",
            r"ثقة[:\\s]+(\d+)",
            r"(\d+)\s*%",
        ]
        for pat in conf_patterns:
            m = re.search(pat, text)
            if m:
                conf = min(int(m.group(1)), 100)
                break

        if decision == "SKIP" or direction == "NEUTRAL" or conf < 20:
            return {
                "decision": "SKIP", "direction": "NEUTRAL", "confidence": 0,
                "entry": price, "stop_loss": price * 0.95,
                "targets": [], "risk_level": "HIGH",
                "reason": ai_text[:200], "schools_agreeing": 0, "key_signal": "",
            }

        sl = price * 0.95 if direction == "BUY" else price * 1.05
        return {
            "decision": decision,
            "direction": direction,
            "confidence": conf,
            "entry": price,
            "stop_loss": round(sl, 8),
            "targets": [],
            "risk_level": "LOW" if conf > 70 else "MEDIUM" if conf > 45 else "HIGH",
            "reason": ai_text[:200],
            "schools_agreeing": 1,
            "key_signal": "",
        }

    return {"decision": "SKIP", "direction": "NEUTRAL", "confidence": 0,
            "entry": price, "stop_loss": price * 0.95,
            "targets": [], "risk_level": "HIGH",
            "reason": "AI غير متاح — لا إشارات", "schools_agreeing": 0, "key_signal": ""}
