# Smart Pre-Sales Assistant

تطبيق Streamlit عربي لإدارة مرحلة ما قبل البيع وتحليل كراسات الشروط، يشمل رفع ملفات RFP، تشغيل تحليلات ذكية، مراجعة جداول الامتثال وBOQ، وبناء عرض فني قابل للتصدير.

## هيكل المشروع المختصر

```text
presales_codex_ready/
├── README.md
└── imdad/
    ├── app.py                 # ملف التشغيل الرئيسي لتطبيق Streamlit
    ├── requirements.txt       # مكتبات Python المطلوبة
    ├── components/            # مكونات واجهة قابلة لإعادة الاستخدام
    ├── pages/                 # صفحات التطبيق الداخلية
    └── utils/                 # إدارة الحالة، قراءة الملفات، ومحرك الذكاء الاصطناعي
```

## مجلد التطبيق الرئيسي

مجلد التطبيق الرئيسي هو:

```bash
presales_codex_ready/imdad
```

وملف التشغيل الرئيسي هو:

```bash
presales_codex_ready/imdad/app.py
```

## أوامر التشغيل من جذر المستودع

```bash
cd /workspace/presales-assistant/presales_codex_ready/imdad
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true
```

بعد التشغيل افتح المتصفح على:

```text
http://localhost:8501
```

## إعدادات مهمة

- أدخل مفتاح Google Gemini API من صفحة **إعدادات النظام** داخل التطبيق.
- موفر الذكاء الاصطناعي المفعّل حالياً هو Google Gemini.
- حقول OpenAI وClaude موجودة كخيارات/حقول إعدادات فقط وليست موفرات مفعّلة حالياً.
