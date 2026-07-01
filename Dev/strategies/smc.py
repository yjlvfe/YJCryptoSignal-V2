"""
💰 Smart Money Concepts (SMC) — Order Blocks, FVG, Liquidity
"""
import numpy as np
from .base import BaseStrategy, Signal


class SMCStrategy(BaseStrategy):
    """
    Smart Money Concepts المتقدمة:
    - Order Blocks (OB): آخر شمعة قبل حركة قوية
    - Fair Value Gaps (FVG): فجوة بين الشموع
    - Liquidity Zones: مناطق السيولة فوق القمم وتحت القيعان
    - Breaker Blocks: OB فاشلة تنعكس
    - Mitigation: السعر يرجع ليلمس الـ OB أو FVG
    """
    name = "SMC (Smart Money)"

    def analyze(self, df) -> Signal:
        # Auto-tune disabled — using defaults
        smc_lb = 30
        price = float(df["close"].iloc[-1])
        open_p = df["open"].values
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values
        volume = df["volume"].values if "volume" in df.columns else None

        # ─── Order Blocks ─── 🆕 Pass volume
        bullish_obs = self._find_bullish_obs(open_p, high, low, close, volume, lookback=smc_lb)
        bearish_obs = self._find_bearish_obs(open_p, high, low, close, volume, lookback=smc_lb)

        # ─── Fair Value Gaps ─── 🆕 Track mitigation
        fvgs = self._find_fvgs(high, low, lookback=smc_lb)
        fvgs = self._track_fvg_mitigation(fvgs, high, low, close)

        # ─── Liquidity Zones ───
        liquid_high, liquid_low = self._find_liquidity_zones(high, low, lookback=smc_lb)

        # ─── Liquidity Sweep Detection ─── 🆕 Enhanced with volume
        swept, sweep_dir, sweep_price, sweep_vol = self._detect_liquidity_sweep(high, low, close, volume, liquid_high, liquid_low)

        # ─── Breaker Blocks ─── 🆕 Failed OBs that become reverse signals
        breaker_blocks = self._find_breaker_blocks(bullish_obs, bearish_obs, close)

        # ─── Nearest OB to price ─── 🆕 Check mitigation
        nearest_bullish_ob = None
        nearest_bearish_ob = None
        for ob in bullish_obs[:5]:
            if ob["price"] < price and not ob.get("mitigated", False):
                if nearest_bullish_ob is None or ob["price"] > nearest_bullish_ob["price"]:
                    nearest_bullish_ob = ob
        for ob in bearish_obs[:5]:
            if ob["price"] > price and not ob.get("mitigated", False):
                if nearest_bearish_ob is None or ob["price"] < nearest_bearish_ob["price"]:
                    nearest_bearish_ob = ob

        # ─── Nearest FVG ───
        nearest_fvg = None
        for fvg in fvgs:
            if fvg["low"] <= price <= fvg["high"]:
                nearest_fvg = fvg
                break
            elif nearest_fvg is None:
                nearest_fvg = fvg

        # ─── Signal Logic ───
        bullish_signals = []
        bearish_signals = []
        confidence = 50

        # BUY: السعر عند Order Block صاعد أو لمبة FVG
        if nearest_bullish_ob:
            dist_to_ob = abs(price - nearest_bullish_ob["price"]) / price * 100
            ob_strength = nearest_bullish_ob.get("strength", 0)
            vol_conf = "✓" if nearest_bullish_ob.get("vol_confirmed", False) else "✗"
            if dist_to_ob < 1.5:
                bullish_signals.append(f"Price at bullish OB (${nearest_bullish_ob['price']:.4f}) str:{ob_strength:.1f} vol:{vol_conf}")
                confidence += int(20 * ob_strength)
            elif dist_to_ob < 3.0:
                bullish_signals.append(f"Near bullish OB (${nearest_bullish_ob['price']:.4f}, {dist_to_ob:.1f}% away) str:{ob_strength:.1f}")
                confidence += int(10 * ob_strength)

        if nearest_fvg and nearest_fvg["low"] <= price <= nearest_fvg["high"]:
            bullish_signals.append(f"FVG being filled (${nearest_fvg['low']:.4f}-${nearest_fvg['high']:.4f})")
            confidence += 15

        if liquid_low and price < liquid_low * 1.02:
            bullish_signals.append(f"Below liquidity zone — sweep expected ↑")
            confidence += 15

        # ─── Breaker Block Signals ─── 🆕
        for bb in breaker_blocks:
            if bb["direction"] == "BULLISH" and bb["price"] < price * 1.01:
                bullish_signals.append(f"💎 Bullish Breaker Block at ${bb['price']:.4f}")
                confidence += 20
            elif bb["direction"] == "BEARISH" and bb["price"] > price * 0.99:
                bearish_signals.append(f"💎 Bearish Breaker Block at ${bb['price']:.4f}")
                confidence += 20

        # ─── Liquidity Sweep Signals ─── 🆕 With volume confirmation
        if swept and sweep_dir == "BULLISH":
            vol_tag = " (vol confirmed)" if sweep_vol else ""
            bullish_signals.append(f"🔥 EQL Sweep at ${sweep_price:.6g} — stop hunt completed ↑{vol_tag}")
            confidence += 25
        elif swept and sweep_dir == "BEARISH":
            vol_tag = " (vol confirmed)" if sweep_vol else ""
            bearish_signals.append(f"🔥 EQH Sweep at ${sweep_price:.6g} — stop hunt completed ↓{vol_tag}")
            confidence += 25

        # SELL
        if nearest_bearish_ob:
            dist_to_ob = abs(price - nearest_bearish_ob["price"]) / price * 100
            ob_strength = nearest_bearish_ob.get("strength", 0)
            vol_conf = "✓" if nearest_bearish_ob.get("vol_confirmed", False) else "✗"
            if dist_to_ob < 1.5:
                bearish_signals.append(f"Price at bearish OB (${nearest_bearish_ob['price']:.4f}) str:{ob_strength:.1f} vol:{vol_conf}")
                confidence += int(20 * ob_strength)
            elif dist_to_ob < 3.0:
                bearish_signals.append(f"Near bearish OB (${nearest_bearish_ob['price']:.4f}, {dist_to_ob:.1f}% away) str:{ob_strength:.1f}")
                confidence += int(10 * ob_strength)

        if liquid_high and price > liquid_high * 0.98:
            bearish_signals.append(f"Near liquidity — sweep & reverse expected ↓")
            confidence += 15

        confidence = min(95, confidence)

        # Decision
        if len(bullish_signals) > len(bearish_signals):
            sl = nearest_bullish_ob["price"] * 0.97 if nearest_bullish_ob else price * 0.95
            targets = self._calc_targets(price, "UP", high, bearish_obs)
            return Signal(
                name=self.name, signal="BUY", strength=0.75,
                entry=round(price, 8),
                stop_loss=round(float(sl), 8),
                targets=targets,
                confidence=confidence,
                reason=self._build_smc_reason("BUY", bullish_signals, bearish_signals)
            )

        if len(bearish_signals) > len(bullish_signals):
            sl = nearest_bearish_ob["price"] * 1.03 if nearest_bearish_ob else price * 1.05
            targets = self._calc_targets(price, "DOWN", high, bullish_obs)
            return Signal(
                name=self.name, signal="SELL", strength=0.75,
                entry=round(price, 8),
                stop_loss=round(float(sl), 8),
                targets=targets,
                confidence=confidence,
                reason=self._build_smc_reason("SELL", bearish_signals, bullish_signals)
            )

        return Signal(
            name=self.name, signal="NEUTRAL", strength=0.3,
            entry=round(price, 8), confidence=30,
            reason="⚪ No clear SMC setup. Price in no-man's land."
        )

    def _find_bullish_obs(self, open_p, high, low, close, volume=None, lookback=30):
        """Order Block صاعد: الشمعة الهابطة القوية → حركة صاعدة — 🆕 مع تأكيد الحجم"""
        obs = []
        for i in range(max(1, len(close) - lookback), len(close) - 2):
            if close[i] < open_p[i]:
                body = abs(close[i] - open_p[i])
                range_c = high[i] - low[i]
                if range_c > 0 and body / range_c > 0.6:
                    if close[i + 1] > open_p[i + 1] and close[i + 1] > high[i]:
                        vol_confirmed = True
                        if volume is not None and len(volume) > i + 1:
                            avg_vol = np.mean(volume[max(0, i-10):i])
                            vol_confirmed = volume[i + 1] > avg_vol * 1.2
                        obs.append({
                            "price": float(low[i]),
                            "high": float(high[i]),
                            "low": float(low[i]),
                            "strength": min(1.0, body / (range_c + 1e-10)),
                            "index": i,
                            "mitigated": False,
                            "vol_confirmed": vol_confirmed,
                            "type": "bullish_ob"
                        })
        return sorted(obs, key=lambda x: x["price"], reverse=True)

    def _find_bearish_obs(self, open_p, high, low, close, volume=None, lookback=30):
        """Order Block هابط: الشمعة الصاعدة القوية → حركة هابطة — 🆕 مع تأكيد الحجم"""
        obs = []
        for i in range(max(1, len(close) - lookback), len(close) - 2):
            if close[i] > open_p[i]:
                body = abs(close[i] - open_p[i])
                range_c = high[i] - low[i]
                if range_c > 0 and body / range_c > 0.6:
                    if close[i + 1] < open_p[i + 1] and close[i + 1] < low[i]:
                        vol_confirmed = True
                        if volume is not None and len(volume) > i + 1:
                            avg_vol = np.mean(volume[max(0, i-10):i])
                            vol_confirmed = volume[i + 1] > avg_vol * 1.2
                        obs.append({
                            "price": float(high[i]),
                            "high": float(high[i]),
                            "low": float(low[i]),
                            "strength": min(1.0, body / (range_c + 1e-10)),
                            "index": i,
                            "mitigated": False,
                            "vol_confirmed": vol_confirmed,
                            "type": "bearish_ob"
                        })
        return sorted(obs, key=lambda x: x["price"])  # Asc by price

    def _find_fvgs(self, high, low, lookback=30):
        """Fair Value Gaps: فجوة بين نطاق شمعتين متتاليتين"""
        fvgs = []
        for i in range(max(1, len(high) - lookback), len(high) - 1):
            # شمعة صاعدة: low الحالية > high السابقة
            if low[i] > high[i - 1]:
                fvgs.append({
                    "type": "BULLISH",
                    "high": float(low[i]),
                    "low": float(high[i - 1]),
                    "mid": float((low[i] + high[i - 1]) / 2),
                    "index": i
                })
            # شمعة هابطة: high الحالية < low السابقة
            elif high[i] < low[i - 1]:
                fvgs.append({
                    "type": "BEARISH",
                    "high": float(low[i - 1]),
                    "low": float(high[i]),
                    "mid": float((low[i - 1] + high[i]) / 2),
                    "index": i
                })
        return fvgs

    def _find_liquidity_zones(self, high, low, lookback=20):
        """
        مناطق السيولة المتقدمة:
        - Equal Highs (EQH): قمتان أو أكثر على نفس المستوى (±1%) → سيولة بيع
        - Equal Lows (EQL): قاعان أو أكثر على نفس المستوى (±1%) → سيولة شراء
        - Liquidity Sweep: السعر يمسح EQH/EQL ثم ينعكس
        Returns (liquidity_high, liquidity_low, sweep_detected, sweep_direction)
        """
        recent_high = float(np.max(high[-lookback:]))
        recent_low = float(np.min(low[-lookback:]))
        high_idx = len(high) - lookback + np.argmax(high[-lookback:])
        low_idx = len(low) - lookback + np.argmin(low[-lookback:])

        liquidity_high = None
        liquidity_low = None
        sweep_detected = False
        sweep_direction = None  # "BULLISH" (swept EQL → up) or "BEARISH" (swept EQH → down)

        # ─── ① Equal Highs (EQH) — سيولة بيع فوق السعر ───
        high_clusters = self._find_equal_levels(high, "high", lookback)
        if high_clusters:
            # Closest EQH above current price = liquidity pool
            for eqh_price, eqh_count in high_clusters:
                if eqh_price > recent_high * 0.99:
                    liquidity_high = eqh_price
                    break
            if liquidity_high is None:
                liquidity_high = high_clusters[0][0]

        # ─── ② Equal Lows (EQL) — سيولة شراء تحت السعر ───
        low_clusters = self._find_equal_levels(low, "low", lookback)
        if low_clusters:
            for eql_price, eql_count in low_clusters:
                if eql_price < recent_low * 1.01:
                    liquidity_low = eql_price
                    break
            if liquidity_low is None:
                liquidity_low = low_clusters[0][0]

        # ─── ④ Fallback: use recent high/low ───
        if liquidity_high is None:
            if high_idx > len(high) - 6:
                liquidity_high = recent_high
        if liquidity_low is None:
            if low_idx > len(low) - 6:
                liquidity_low = recent_low

        return liquidity_high, liquidity_low

    def _find_equal_levels(self, values, level_type="high", lookback=20):
        """
        Find clusters of equal highs or equal lows (±1% tolerance).
        Returns list of (price, count) sorted by count desc.
        """
        if len(values) < lookback:
            return []
        segment = values[-lookback:]
        clusters = []
        used = set()

        for i in range(len(segment)):
            if i in used:
                continue
            base = float(segment[i])
            # Find all values within 1% of base
            cluster = [i]
            for j in range(i + 1, len(segment)):
                if j in used:
                    continue
                if abs(float(segment[j]) - base) / max(base, 1e-10) < 0.01:
                    cluster.append(j)
            if len(cluster) >= 2:  # At least 2 touches = liquidity zone
                # Use average price of cluster
                avg_price = sum(float(segment[k]) for k in cluster) / len(cluster)
                clusters.append((avg_price, len(cluster), cluster))
                used.update(cluster)

        # Sort by count desc
        clusters.sort(key=lambda x: (-x[1]))
        return [(c[0], c[1]) for c in clusters]

    def _detect_liquidity_sweep(self, high, low, close_data, volume, liquidity_high, liquidity_low):
        """
        Detect liquidity sweep (stop hunt) in last 3 candles — 🆕 with volume confirmation.
        Returns (sweep_detected, sweep_direction, sweep_price, volume_confirmed)
        """
        if len(close_data) < 4:
            return False, None, None, False

        current_close = float(close_data[-1])

        # ─── Bullish Sweep: wicked below EQL then closed above it ───
        if liquidity_low is not None:
            for i in range(len(close_data) - 3, len(close_data)):
                wick_low = float(low[i])
                candle_close = float(close_data[i])
                if wick_low < liquidity_low * 0.995 and candle_close > liquidity_low:
                    # 🆕 Volume confirmation: sweep candle has above avg volume
                    vol_confirmed = False
                    if volume is not None and len(volume) > i:
                        avg_vol = np.mean(volume[max(0, i-10):i])
                        vol_confirmed = volume[i] > avg_vol * 1.5
                    return True, "BULLISH", float(liquidity_low), vol_confirmed

        # ─── Bearish Sweep: wicked above EQH then closed below it ───
        if liquidity_high is not None:
            for i in range(len(close_data) - 3, len(close_data)):
                wick_high = float(high[i])
                candle_close = float(close_data[i])
                if wick_high > liquidity_high * 1.005 and candle_close < liquidity_high:
                    vol_confirmed = False
                    if volume is not None and len(volume) > i:
                        avg_vol = np.mean(volume[max(0, i-10):i])
                        vol_confirmed = volume[i] > avg_vol * 1.5
                    return True, "BEARISH", float(liquidity_high), vol_confirmed

        return False, None, None, False

    def _track_fvg_mitigation(self, fvgs, high, low, close):
        """🆕 Track which FVGs have been mitigated (filled)"""
        current_price = close[-1]
        for fvg in fvgs:
            if fvg.get("mitigated", False):
                continue
            # Bullish FVG: price entered from above and closed inside/above
            if fvg["type"] == "BULLISH":
                if current_price <= fvg["high"] and current_price >= fvg["low"]:
                    fvg["mitigated"] = True
                    fvg["mitigation_price"] = float(current_price)
            # Bearish FVG: price entered from below and closed inside/below
            elif fvg["type"] == "BEARISH":
                if current_price >= fvg["low"] and current_price <= fvg["high"]:
                    fvg["mitigated"] = True
                    fvg["mitigation_price"] = float(current_price)
        return fvgs

    def _find_breaker_blocks(self, bullish_obs, bearish_obs, close):
        """🆕 Breaker Blocks: Failed OBs that reverse and become strong S/R
        
        A breaker block = OB that was mitigated (price went through it) 
        then price reversed and the OB level becomes support/resistance
        """
        breakers = []
        current_price = close[-1]
        
        # Bullish Breaker: Bearish OB that was broken down, then price came back up
        for ob in bearish_obs:
            if ob.get("mitigated", False) and ob["price"] > current_price:
                # Price broke the bearish OB, then recovered above it
                if close[-1] > ob["price"] and close[-2] < ob["price"]:
                    breakers.append({
                        "price": ob["price"],
                        "direction": "BULLISH",
                        "strength": ob.get("strength", 0.5),
                        "type": "bullish_breaker"
                    })
        
        # Bearish Breaker: Bullish OB that was broken up, then price came back down
        for ob in bullish_obs:
            if ob.get("mitigated", False) and ob["price"] < current_price:
                if close[-1] < ob["price"] and close[-2] > ob["price"]:
                    breakers.append({
                        "price": ob["price"],
                        "direction": "BEARISH",
                        "strength": ob.get("strength", 0.5),
                        "type": "bearish_breaker"
                    })
        
        return breakers

    def _calc_targets(self, price, direction, highs, obs):
        if direction == "UP":
            # هدف عند أعلى OB (هذا يعطي أهداف واقعية)
            if obs:
                next_ob = obs[0] if obs[0]["price"] > price else (obs[1] if len(obs) > 1 else None)
                if next_ob:
                    t1 = next_ob["high"]
                else:
                    t1 = price * 1.02
            else:
                t1 = price * 1.02
            return [round(t1, 8), round(t1 * 1.02, 8), round(t1 * 1.05, 8)]
        else:
            if obs:
                next_ob = obs[0] if obs[0]["price"] < price else (obs[1] if len(obs) > 1 else None)
                if next_ob:
                    t1 = next_ob["low"]
                else:
                    t1 = price * 0.98
            else:
                t1 = price * 0.98
            return [round(t1, 8), round(t1 * 0.98, 8), round(t1 * 0.95, 8)]

    def _build_smc_reason(self, decision, main, opp):
        parts = [f"💰 SMC {decision}"]
        for m in main[:2]:
            parts.append(f"✓ {m}")
        for o in opp[:1]:
            parts.append(f"⚠️ {o}")
        return " | ".join(parts)
