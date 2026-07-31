# محلل متطلبات الأعمال الذكي / Smart Business Requirements Analyst

تطبيق Streamlit ثنائي اللغة لتحليل كراسات الشروط الحكومية السعودية (اعتماد /
فرصة) وبناء العرض الفني.

المسار: رفع المرفقات ودمجها في سياق موحّد ← استخراج مصفوفة الامتثال وجدول
الكميات ← اقتراح هيكل العرض وفق معايير اعتماد ← الكتابة قسماً بقسم مع مساعد
تنقيح ← مراجعة من لجنة ثلاثة وكلاء بدرجات جاهزية ← التصدير إلى Word أو PDF
بغلاف وهوية الشركة.

الوثائق الكاملة في [`../README.md`](../README.md).

## مجلد التطبيق الرئيسي

```text
presales_codex_ready/business_analyst
```

## ملف التشغيل الرئيسي

```text
presales_codex_ready/business_analyst/app.py
```

## أوامر التشغيل

من جذر المستودع:

```bash
cd presales_codex_ready/business_analyst
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

- أدخل مفتاح Google Gemini API من صفحة إعدادات النظام داخل التطبيق، أو اضبط
  متغيّر البيئة `GEMINI_API_KEY` قبل التشغيل.
- موفر الذكاء الاصطناعي المفعّل حالياً هو Google Gemini عبر حزمة `google-genai` الموحّدة.
- النماذج المتاحة: Gemini 3.6 Flash (الافتراضي) · Gemini 3.1 Pro · Gemini 3.5 Flash-Lite.
- البيانات كلها في `data/analyst.db` (SQLite)؛ يمكن تغيير مساره بمتغيّر البيئة
  `ANALYST_DB_PATH`. الملف مُستثنى من git.
- لتفعيل OCR للملفات الممسوحة ضوئياً: `sudo apt install tesseract-ocr tesseract-ocr-ara poppler-utils` ثم `pip install pytesseract pdf2image`.
- لتصدير PDF بالعربية يلزم خط يدعم الحروف العربية على النظام
  (`sudo apt install fonts-dejavu fonts-hosny-amiri`)، وإلا رفض التصدير برسالة صريحة.
- حقول OpenAI وClaude موجودة كخيارات/حقول إعدادات فقط وليست موفرات مفعّلة حالياً.
