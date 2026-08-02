#!/usr/bin/env bash
# تهيئة بيئة Codespaces / إعداد الحاوية.
#
# ثلاثة أشياء لا يعمل النظام بدونها ولا يخبرك أحد بها وقت التشغيل:
#   · خط يدعم العربية — بدونه يرفض تصدير PDF بدل إخراج ملف بمربّعات فارغة.
#   · أدوات OCR — كثير من كراسات اعتماد ملفات ممسوحة ضوئياً بلا طبقة نص.
#   · مسار قاعدة بيانات خارج شجرة الكود — حتى لا تُمحى بيانات العطاءات
#     مع أي عملية تنظيف للمستودع.
set -euo pipefail

APP_DIR="presales_codex_ready/business_analyst"

echo "▶ حزم النظام / system packages…"
sudo apt-get update -qq
sudo apt-get install -y -qq \
  fonts-dejavu-core \
  fonts-hosny-amiri \
  tesseract-ocr \
  tesseract-ocr-ara \
  poppler-utils

echo "▶ مكتبات Python / Python packages…"
python -m pip install --upgrade pip --quiet
python -m pip install --quiet -r "${APP_DIR}/requirements.txt"

# اختيارية في requirements لكنها مطلوبة لتشغيل مسار OCR فعلياً
python -m pip install --quiet pytesseract pdf2image

# أدوات الاختبار — CI يشغّلها، ومن المفيد تشغيلها هنا قبل الدفع
python -m pip install --quiet pytest pytest-timeout

# قاعدة البيانات خارج شجرة الكود وتبقى ما بقيت الحاوية
mkdir -p /workspaces/data

cat <<'EOF'

────────────────────────────────────────────────────────────
✅ البيئة جاهزة / Environment ready

التشغيل / Run:
    streamlit run presales_codex_ready/business_analyst/app.py

الاختبارات / Tests:
    cd presales_codex_ready/business_analyst && python -m pytest tests/ -q

⚠️  مفتاح Gemini / Gemini API key
    أضِفه كسرّ في Codespaces باسم GEMINI_API_KEY فيقرأه التطبيق تلقائياً،
    أو أدخله يدوياً من صفحة «إعدادات النظام» داخل التطبيق.
    Add it as a Codespaces secret named GEMINI_API_KEY, or paste it into
    the System settings page inside the app.
────────────────────────────────────────────────────────────
EOF
