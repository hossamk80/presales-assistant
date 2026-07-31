# Smart Pre-Sales Assistant

تطبيق Streamlit عربي لإدارة مرحلة ما قبل البيع وتحليل كراسات الشروط، يشمل رفع ملفات RFP، تشغيل تحليلات ذكية، مراجعة جداول الامتثال وBOQ، وبناء عرض فني قابل للتصدير.

## مجلد التطبيق الرئيسي

```text
presales_codex_ready/imdad
```

## ملف التشغيل الرئيسي

```text
presales_codex_ready/imdad/app.py
```

## أوامر التشغيل

من جذر المستودع:

```bash
cd presales_codex_ready/imdad
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true
```

ثم افتح:

```text
http://localhost:8501
```

## ملاحظات

- أدخل مفتاح Google Gemini API من صفحة إعدادات النظام داخل التطبيق.
- موفر الذكاء الاصطناعي المفعّل حالياً هو Google Gemini عبر حزمة `google-genai` الموحّدة.
- النماذج المتاحة: Gemini 3.6 Flash (الافتراضي) · Gemini 3.1 Pro · Gemini 3.5 Flash-Lite.
- لتفعيل OCR للملفات الممسوحة ضوئياً: `sudo apt install tesseract-ocr tesseract-ocr-ara poppler-utils` ثم `pip install pytesseract pdf2image`.
- حقول OpenAI وClaude موجودة كخيارات/حقول إعدادات فقط وليست موفرات مفعّلة حالياً.
