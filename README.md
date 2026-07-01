# YJCryptoSignal-V2 🚀

**نظام إشارات تداول العملات الرقمية — الجيل الثاني** — بنية موحدة مع محرك AI متقدم، مقاييس Prometheus، ونظام تنبيهات ذكي.

---

## ✨ المميزات

- 🏗️ **بنية موحدة** — core/bot/engine/trade/data في وحدات منفصلة نظيفة
- 🧠 **محرك AI متقدم** — multi-provider مع فال بايك وفحص صحة تلقائي
- 🔍 **ماسح متعدد المنصات** — MEXC, OKX, Gate.io, KuCoin, Bitget
- 📊 **16 استراتيجية فنية** — RSI, MACD, CVD, VWAP, Divergence, SMC, Market Structure
- 🛡️ **نظام حماية متقدم** — trade_safety + safety_walls مع SL < 3%, R:R ≥ 1:1
- 📈 **تقارير تيليجرام** — قوالب رسائل عربية احترافية
- 📉 **اختبار رجعي** — engine_backtest لتحسين الأداء
- 🔥 **تعلم تكيفي** — learn_adaptive يتعلم من الصفقات السابقة
- 📊 **Prometheus Metrics** — مقاييس الأداء على المنفذ 9090/9091
- 🔔 **نظام تنبيهات** — alerting مع إشعارات ذكية
- 🧪 **اختبارات شاملة** — pytest مع coverage عالية

---

## 📋 المتطلبات

- **Python:** 3.10+
- **Redis:** (اختياري) للطبقة المخبأة
- **OS:** Linux (Ubuntu 22.04+)

---

## 🚀 التشغيل

```bash
git clone https://github.com/yjlvfe/YJCryptoSignal-V2.git
cd YJCryptoSignal-V2/Dev
pip install -r requirements.txt
```

انسخ `.env.example` إلى `.env` وعبّئ المتغيرات المطلوبة:

```bash
cp .env.example .env
```

تشغيل السكانر:

```bash
python run_scanner.py
```

تشغيل البوت:

```bash
python bot/bot_main.py
```

تشغيل الاختبارات:

```bash
pytest Dev/tests/ -v
```

---

## 🏗️ هيكل المشروع

```
YJCryptoSignal-V2/
├── Dev/
│   ├── bot/                    # بوت تيليجرام
│   │   ├── bot_admin.py        # أوامر المشرفين
│   │   ├── bot_handlers.py     # معالجات الأوامر
│   │   ├── bot_messaging.py    # نظام الرسائل
│   │   ├── bot_security.py    # أمان البوت
│   │   ├── bot_ratelimit.py   # حدود الطلبات
│   │   └── ...                 # ملفات إضافية
│   ├── core/                   # النواة
│   │   ├── core_ai.py          # محرك AI متعدد المزودين
│   │   ├── core_scanner.py     # الماسح الرئيسي
│   │   ├── core_analyzer.py    # المحلل
│   │   ├── core_regime.py      # تحديد حالة السوق
│   │   ├── core_metrics.py     # مقاييس Prometheus
│   │   ├── config.py           # إعدادات النظام
│   │   └── ...                 # ملفات إضافية
│   ├── engine/                 # محرك التحليل
│   │   ├── engine_scanner.py   # ماسح المحرك
│   │   ├── engine_breakout.py  # صياد الاختراقات
│   │   ├── engine_liquidity.py # تحليل السيولة
│   │   ├── engine_multi_tf.py  # تحليل متعدد الأطر
│   │   └── ...                 # محركات إضافية
│   ├── trade/                  # إدارة التداول
│   │   ├── trade_tracker.py    # تتبع الصفقات
│   │   ├── trade_safety.py     # حماية الصفقات
│   │   ├── trade_sizing.py     # حجم الصفقة
│   │   └── trade_heat.py       # خريطة الحرارة
│   ├── strategies/             # الاستراتيجيات الفنية
│   ├── data/                   # جلب البيانات
│   ├── learn/                  # التعلم التكيفي
│   ├── report/                 # التقارير
│   ├── sectors/                # تصنيف القطاعات
│   ├── scripts/                # سكربتات واختبارات ضغط
│   ├── tests/                  # اختبارات pytest
│   ├── utils/                  # أدوات مساعدة
│   ├── run_scanner.py          # تشغيل السكانر
│   ├── health_check.py         # فحص صحة النظام
│   └── yjcryptosignal-ctl      # أداة تحكم CLI
└── .github/workflows/          # CI/CD
```

---

## ⚙️ الإعدادات

يتم التحكم بالإعدادات عبر ملف `.env`:

| المتغير | الوصف |
|---------|-------|
| `BOT_TOKEN` | توكن بوت تيليجرام |
| `DATA_DIR` | مجلد البيانات |
| `AI_API_KEY` | مفتاح API للذكاء الاصطناعي |
| `AI_BASE_URL` | رابط API |
| `AI_MODEL` | نموذج AI |
| `METRICS_PORT` | منفذ Prometheus (افتراضي 9090) |

---

## 📄 الرخصة

MIT License — انظر ملف [LICENSE](LICENSE)

---

## 🤝 المؤلف

**YJLVFE** — [github.com/yjlvfe](https://github.com/yjlvfe)
