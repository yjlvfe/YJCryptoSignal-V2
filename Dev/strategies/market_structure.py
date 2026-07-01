"""
🏗️ Market Structure -- HH/HL, LH/LL, CHoCH, BOS
"""
import numpy as np
import pandas as pd
from .base import BaseStrategy, Signal


class MarketStructureStrategy(BaseStrategy):
    """
    تحليل هيكل السوق الكلاسيكي:
    - HH (Higher High) + HL (Higher Low) = Uptrend
    - LH (Lower High) + LL (Lower Low) = Downtrend
    - CHoCH (Change of Character) = انعكاس الاتجاه
    - BOS (Break of Structure) = استمرار الاتجاه
    - Internal structure breaks for entries
    """

    name = "Market Structure"

    def analyze(self, df) -> Signal:
        # Auto-tune disabled — using defaults
        lookback = 30
        price = float(df["close"].iloc[-1])
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values

        # استخراج القمم والقيعان
        highs_peaks = self._find_peaks(high, window=4)
        lows_valleys = self._find_valleys(low, window=4)

        if len(highs_peaks) < 3 or len(lows_valleys) < 3:
            return self._neutral(price, "Not enough structure points")

        # تحديد الاتجاه من آخر 4 نقاط
        trend = self._determine_trend(highs_peaks, lows_valleys)

        # كشف تغيير الشخصية (CHoCH) — الآن يعيد (direction, strength)
        choch, choch_strength = self._detect_choch(highs_peaks, lows_valleys, close)

        # كشف كسر الهيكل (BOS) — الآن يعيد (direction, strength)
        bos, bos_strength = self._detect_bos(highs_peaks, lows_valleys, price, close)

        # 🆕 Internal BOS for early entries
        internal_bos, internal_bos_strength = self._detect_internal_bos(highs_peaks, lows_valleys, price, close)

        # 🆕 Mitigation check
        mitigated, mitigation_type, mitigation_dist = self._check_mitigation(highs_peaks, lows_valleys, price)

        # قوة الهيكل
        structure_strength = self._score_structure(highs_peaks, lows_valleys, trend)

        # بناء الإشارة
        bullish_signals = []
        bearish_signals = []

        if trend == "UP":
            bullish_signals.append(f"HH/HL structure intact")
            # CHoCH هابط في اتجاه صاعد = ضعف محتمل
            if choch == "DOWN":
                bearish_signals.append(f"CHoCH down detected -- trend weakening (str: {choch_strength:.0%})")
            if bos == "UP":
                bullish_signals.append(f"BOS up -- trend continuation ✓ (str: {bos_strength:.0%})")
            if internal_bos == "UP":
                bullish_signals.append(f"Internal BOS up -- early entry signal (str: {internal_bos_strength:.0%})")
            if mitigated and "bullish" in mitigation_type:
                bullish_signals.append(f"Price mitigating bullish OB @ {mitigation_dist:.1f}%")
        elif trend == "DOWN":
            bearish_signals.append(f"LH/LL structure intact")
            if choch == "UP":
                bullish_signals.append(f"CHoCH up detected -- potential reversal (str: {choch_strength:.0%})")
            if bos == "DOWN":
                bearish_signals.append(f"BOS down -- bearish continuation ✓ (str: {bos_strength:.0%})")
            if internal_bos == "DOWN":
                bearish_signals.append(f"Internal BOS down -- early entry signal (str: {internal_bos_strength:.0%})")
            if mitigated and "bearish" in mitigation_type:
                bearish_signals.append(f"Price mitigating bearish OB @ {mitigation_dist:.1f}%")
        else:
            # Range
            pass

        # إشارة تداول
        if trend == "UP" and len(bullish_signals) >= 1 and "weak" not in str(bearish_signals):
            sl = min(p["price"] for p in lows_valleys[-2:]) * 0.98 if lows_valleys else price * 0.95
            # 🆕 Use structure-based targets
            targets = self._calc_structure_targets(price, "UP", highs_peaks, lows_valleys)
            return Signal(
                name=self.name, signal="BUY", strength=0.8 if choch != "DOWN" else 0.5,
                entry=round(price, 8),
                stop_loss=round(float(sl), 8),
                targets=targets,
                confidence=min(90, int(structure_strength * 100)),
                reason=self._format_reason("UPTREND", bullish_signals, bearish_signals, structure_strength)
            )

        if trend == "DOWN" and len(bearish_signals) >= 1 and "weak" not in str(bullish_signals):
            sl = max(p["price"] for p in highs_peaks[-2:]) * 1.02 if highs_peaks else price * 1.05
            targets = self._calc_structure_targets(price, "DOWN", highs_peaks, lows_valleys)
            return Signal(
                name=self.name, signal="SELL", strength=0.8 if choch != "UP" else 0.5,
                entry=round(price, 8),
                stop_loss=round(float(sl), 8),
                targets=targets,
                confidence=min(90, int(structure_strength * 100)),
                reason=self._format_reason("DOWNTREND", bearish_signals, bullish_signals, structure_strength)
            )

        # CHoCH انعكاسي
        if choch == "UP" and len(highs_peaks) >= 4 and choch_strength > 0.5:
            sl = min(p["price"] for p in lows_valleys[-3:]) * 0.97
            targets = self._calc_structure_targets(price, "UP", highs_peaks, lows_valleys)
            return Signal(
                name=self.name, signal="BUY", strength=0.7,
                entry=round(price, 8),
                stop_loss=round(float(sl), 8),
                targets=targets,
                confidence=70,
                reason=f"🔄 CHoCH up -- trend reversal from downtrend to uptrend potential (str: {choch_strength:.0%})"
            )
        if choch == "DOWN" and len(lows_valleys) >= 4 and choch_strength > 0.5:
            sl = max(p["price"] for p in highs_peaks[-3:]) * 1.03
            targets = self._calc_structure_targets(price, "DOWN", highs_peaks, lows_valleys)
            return Signal(
                name=self.name, signal="SELL", strength=0.7,
                entry=round(price, 8),
                stop_loss=round(float(sl), 8),
                targets=targets,
                confidence=70,
                reason=f"🔄 CHoCH down -- trend reversal from uptrend to downtrend potential (str: {choch_strength:.0%})"
            )

        return self._neutral(price, f"Range structure -- {trend} with no clear entry")

    def _find_peaks(self, highs, window=4):
        peaks = []
        for i in range(window, len(highs) - window):
            if highs[i] == max(highs[i - window:i + window + 1]):
                peaks.append({"price": float(highs[i]), "i": i})
        return peaks[-10:]

    def _find_valleys(self, lows, window=4):
        valleys = []
        for i in range(window, len(lows) - window):
            if lows[i] == min(lows[i - window:i + window + 1]):
                valleys.append({"price": float(lows[i]), "i": i})
        return valleys[-10:]

    def _determine_trend(self, highs, lows):
        """تصنيف الاتجاه من آخر 3 قمم وقيعان"""
        if len(highs) < 3 or len(lows) < 3:
            return "RANGE"

        last_h = [p["price"] for p in highs[-3:]]
        last_l = [p["price"] for p in lows[-3:]]

        hh = all(last_h[i] >= last_h[i - 1] for i in range(1, len(last_h)))
        hl = all(last_l[i] >= last_l[i - 1] for i in range(1, len(last_l)))
        lh = all(last_h[i] <= last_h[i - 1] for i in range(1, len(last_h)))
        ll = all(last_l[i] <= last_l[i - 1] for i in range(1, len(last_l)))

        if hh and hl:
            return "UP"
        elif lh and ll:
            return "DOWN"
        elif hh and not hl:
            # HH with lower lows = volatile up
            return "UP"
        elif lh and not ll:
            return "DOWN"
        return "RANGE"

    def _detect_choch(self, highs, lows, close_prices=None):
        """Change of Character -- انعكاس الاتجاه مع تأكيد"""
        if len(highs) < 4 or len(lows) < 4:
            return None, 0.0
        
        h3, h2, h1 = highs[-3]["price"], highs[-2]["price"], highs[-1]["price"]
        l3, l2, l1 = lows[-3]["price"], lows[-2]["price"], lows[-1]["price"]
        
        # structural indices
        h3_i, h2_i, h1_i = highs[-3]["i"], highs[-2]["i"], highs[-1]["i"]
        l3_i, l2_i, l1_i = lows[-3]["i"], lows[-2]["i"], lows[-1]["i"]
        
        choch_strength = 0.0
        
        # من هابط إلى صاعد: قاع أعلى (HH) + قمة أعلى بعد قمة أقل (BOS-like)
        # Classic CHoCH down→up: LL broken by HL, then HH formed
        if l2 < l1 and h2 < h1 and l1 > l3:
            # Additional validation: time between structure points
            time_span = h1_i - l2_i
            if 2 <= time_span <= 30:  # reasonable timeframe
                choch_strength = min(1.0, 0.6 + (l1 - l2) / l2 * 10)  # distance bonus
                return "UP", choch_strength
                
        # من صاعد إلى هابط: قمة أقل (LH) + قاع أقل بعد قاع أعلى
        if h2 > h1 and l2 > l1 and h1 < h3:
            time_span = l1_i - h2_i
            if 2 <= time_span <= 30:
                choch_strength = min(1.0, 0.6 + (h2 - h1) / h2 * 10)
                return "DOWN", choch_strength
                
        return None, 0.0

    def _detect_bos(self, highs, lows, price, close_prices=None):
        """Break of Structure -- كسر الهيكل مع تأكيد"""
        if len(highs) < 2 or len(lows) < 2:
            return None, 0.0
            
        last_h = highs[-1]["price"]
        prev_h = highs[-2]["price"]
        last_l = lows[-1]["price"]
        prev_l = lows[-2]["price"]
        
        bos_strength = 0.0
        
        # BOS UP: price breaks recent high, making higher high
        if price > prev_h and last_h > prev_h:
            # Validate: check if close also above (stronger signal)
            close_above = close_prices[-1] > prev_h if close_prices is not None and len(close_prices) > 0 else True
            dist_pct = (last_h - prev_h) / prev_h * 100
            bos_strength = 0.6 + min(0.4, dist_pct * 5)  # distance bonus
            if close_above:
                bos_strength = min(1.0, bos_strength + 0.15)
            return "UP", bos_strength
            
        # BOS DOWN: price breaks recent low, making lower low
        if price < prev_l and last_l < prev_l:
            close_below = close_prices[-1] < prev_l if close_prices is not None and len(close_prices) > 0 else True
            dist_pct = (prev_l - last_l) / prev_l * 100
            bos_strength = 0.6 + min(0.4, dist_pct * 5)
            if close_below:
                bos_strength = min(1.0, bos_strength + 0.15)
            return "DOWN", bos_strength
            
        return None, 0.0

    def _detect_internal_bos(self, highs, lows, price, close_prices=None):
        """🆕 Internal BOS -- كسر هيكل داخلي (فركتلات داخلية على 1h/15m)
        
        يبحث عن كسر أقصر مدى داخل الاتجاه العام لل entradas المبكرة
        """
        if len(highs) < 4 or len(lows) < 4:
            return None, 0.0
            
        # Look at last 4 points for internal structure
        recent_highs = highs[-4:]
        recent_lows = lows[-4:]
        
        # Internal bullish: recent low > previous low (internal HL) + price > internal high
        for i in range(len(recent_lows) - 1, 0, -1):
            if recent_lows[i]["price"] > recent_lows[i-1]["price"]:
                # Found internal HL, check if price breaks the swing high between them
                internal_high = max(h["price"] for h in recent_highs if h["i"] > recent_lows[i-1]["i"] and h["i"] < recent_lows[i]["i"])
                if price > internal_high:
                    return "UP", 0.5  # lower confidence than swing BOS
                    
        # Internal bearish
        for i in range(len(recent_highs) - 1, 0, -1):
            if recent_highs[i]["price"] < recent_highs[i-1]["price"]:
                internal_low = min(l["price"] for l in recent_lows if l["i"] > recent_highs[i-1]["i"] and l["i"] < recent_highs[i]["i"])
                if price < internal_low:
                    return "DOWN", 0.5
                    
        return None, 0.0

    def _check_mitigation(self, highs, lows, price):
        """🆕 Mitigation Check -- هل السعر عاد لـ OB/FVG؟
        
        Returns (mitigated: bool, level_type: str, distance_pct: float)
        """
        # Check if price is near prior swing points (potential OB mitigation)
        for h in highs[-3:]:
            dist = abs(h["price"] - price) / price * 100
            if dist < 1.0:  # within 1%
                return True, "bearish_ob_mitigation", dist
                
        for l in lows[-3:]:
            dist = abs(l["price"] - price) / price * 100
            if dist < 1.0:
                return True, "bullish_ob_mitigation", dist
                
        return False, None, 0.0

    def _score_structure(self, highs, lows, trend):
        """تقييم قوة الهيكل 0-1"""
        if len(highs) < 3 or len(lows) < 3:
            return 0.3

        h_prices = [p["price"] for p in highs[-4:]]
        l_prices = [p["price"] for p in lows[-4:]]

        if trend == "UP":
            h_consistency = sum(1 for i in range(1, len(h_prices)) if h_prices[i] > h_prices[i - 1])
            l_consistency = sum(1 for i in range(1, len(l_prices)) if l_prices[i] > l_prices[i - 1])
        elif trend == "DOWN":
            h_consistency = sum(1 for i in range(1, len(h_prices)) if h_prices[i] < h_prices[i - 1])
            l_consistency = sum(1 for i in range(1, len(l_prices)) if l_prices[i] < l_prices[i - 1])
        else:
            return 0.4

        consistency = (h_consistency + l_consistency) / (max(len(h_prices) - 1, 1) + max(len(l_prices) - 1, 1))
        return min(0.95, 0.4 + consistency * 0.5)

    def _format_reason(self, trend_label, main_signals, opposing_signals, strength):
        main = "; ".join(main_signals[:2])
        opp = "; ".join(opposing_signals[:1])
        parts = [f"🏗️ {trend_label}"]
        if main:
            parts.append(f"✓ {main}")
        if opp:
            parts.append(f"⚠️ {opp}")
        parts.append(f"struct: {strength:.0%}")
        return " | ".join(parts)

    def _calc_structure_targets(self, price, direction, highs, lows):
        """🆕 Structure-based targets using swing highs/lows"""
        if direction == "UP":
            # TP1: next swing high
            # TP2: swing high after that
            # TP3: 1.618 extension of last swing
            swing_highs = sorted(highs, key=lambda x: x["i"])
            higher_highs = [h for h in swing_highs if h["price"] > price]
            
            if len(higher_highs) >= 1:
                t1 = higher_highs[0]["price"]
            else:
                t1 = price * 1.02
                
            if len(higher_highs) >= 2:
                t2 = higher_highs[1]["price"]
            else:
                t2 = t1 * 1.015
                
            # TP3: Fibonacci extension
            last_swing_low = max(l["price"] for l in lows[-3:]) if lows else price * 0.98
            swing_range = price - last_swing_low
            t3 = price + swing_range * 1.618
            
            # Ensure ascending
            t1 = max(t1, price * 1.005)
            t2 = max(t2, t1 * 1.005)
            t3 = max(t3, t2 * 1.005)
            
            return [round(t1, 8), round(t2, 8), round(t3, 8)]
        else:
            swing_lows = sorted(lows, key=lambda x: x["i"])
            lower_lows = [l for l in swing_lows if l["price"] < price]
            
            if len(lower_lows) >= 1:
                t1 = lower_lows[0]["price"]
            else:
                t1 = price * 0.98
                
            if len(lower_lows) >= 2:
                t2 = lower_lows[1]["price"]
            else:
                t2 = t1 * 0.985
                
            last_swing_high = min(h["price"] for h in highs[-3:]) if highs else price * 1.02
            swing_range = last_swing_high - price
            t3 = price - swing_range * 1.618
            
            t1 = min(t1, price * 0.995)
            t2 = min(t2, t1 * 0.995)
            t3 = min(t3, t2 * 0.995)
            
            return [round(t1, 8), round(t2, 8), round(t3, 8)]

    def _neutral(self, price, reason):
        return Signal(
            name=self.name, signal="NEUTRAL", strength=0.3,
            entry=round(price, 8), confidence=30,
            reason=f"⚪ {reason}."
        )
