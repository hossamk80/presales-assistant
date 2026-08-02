#!/usr/bin/env bash
# تهيئة بيئة Codespaces / إعداد الحاوية.
#
# ثلاثة أشياء لا يعمل النظام بدونها ولا يخبرك أحد بها وقت التشغيل:
#   · خط يدعم العربية — بدونه يرفض تصدير PDF بدل إخراج ملف بمربّعات فارغة.
#   · أدوات OCR — كثير من كراسات اعتماد ملفات ممسوحة ضوئياً بلا طبقة نص.
#   · مسار قاعدة بيانات خارج شجرة الكود — حتى لا تُمحى بيانات العطاءات
#     مع أي عملية تنظيف للمستودع.
#
# **كل التثبيت داخل `.venv`**: الـ README يوصي بإنشائها، وVS Code يفعّلها
# تلقائياً في كل طرفية جديدة. تثبيتٌ في بايثون النظام بينما الطرفية على
# البيئة الافتراضية يُنتج بالضبط: `No module named pytest` مع أن التثبيت
# «نجح». مصدر واحد للحقيقة يمنع ذلك.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="${REPO_ROOT}/presales_codex_ready/business_analyst"
VENV="${REPO_ROOT}/.venv"

echo "▶ حزم النظام / system packages…"
sudo apt-get update -qq
sudo apt-get install -y -qq \
  fonts-dejavu-core \
  fonts-hosny-amiri \
  tesseract-ocr \
  tesseract-ocr-ara \
  poppler-utils

if [ ! -x "${VENV}/bin/python" ]; then
  echo "▶ إنشاء البيئة الافتراضية / creating .venv…"
  python -m venv "${VENV}"
fi

PY="${VENV}/bin/python"

echo "▶ مكتبات Python / Python packages…"
"${PY}" -m pip install --upgrade pip --quiet
"${PY}" -m pip install --quiet -r "${APP_DIR}/requirements.txt"

# اختيارية في requirements لكنها مطلوبة لتشغيل مسار OCR فعلياً
"${PY}" -m pip install --quiet pytesseract pdf2image

# أدوات الاختبار — CI يشغّلها، ومن المفيد تشغيلها هنا قبل الدفع
"${PY}" -m pip install --quiet pytest pytest-timeout

# قاعدة البيانات خارج شجرة الكود وتبقى ما بقيت الحاوية
mkdir -p /workspaces/data

cat <<'EOF'

────────────────────────────────────────────────────────────
✅ البيئة جاهزة / Environment ready

التشغيل / Run — من أي مجلد / from any directory:
    ./scripts/run.sh

الاختبارات / Tests:
    ./scripts/test.sh

⚠️  مفتاح Gemini / Gemini API key
    أضِفه كسرّ في Codespaces باسم GEMINI_API_KEY فيقرأه التطبيق تلقائياً،
    أو أدخله يدوياً من صفحة «إعدادات النظام» داخل التطبيق.
    Add it as a Codespaces secret named GEMINI_API_KEY, or paste it into
    the System settings page inside the app.
────────────────────────────────────────────────────────────
EOF
