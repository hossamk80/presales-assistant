#!/usr/bin/env bash
# تشغيل التطبيق — من أي مجلد / Run the app from any directory.
#
# ثلاثة أخطاء تكرّرت وهذا السكربت يمنعها:
#   · مسار نسبي خاطئ إلى `app.py` («File does not exist»).
#   · `streamlit` من بايثون النظام بينما المكتبات في `.venv`.
#   · التشغيل من مجلد لا يحوي `.streamlit/config.toml` فتضيع إعداداته
#     (حد الرفع 400MB وإعدادات الوكيل) بلا رسالة.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="${REPO_ROOT}/app.py"
VENV_PY="${REPO_ROOT}/.venv/bin/python"

# البيئة الافتراضية إن وُجدت، وإلا بايثون المتاح
PY="${VENV_PY}"
[ -x "${PY}" ] || PY="$(command -v python3 || command -v python)"

if ! "${PY}" -c "import streamlit" 2>/dev/null; then
  echo "❌ streamlit غير مثبّت في ${PY}" >&2
  echo "   شغّل التهيئة أولاً: bash .devcontainer/setup.sh" >&2
  exit 1
fi

# config.toml يُقرأ من مجلد العمل، فنشغّل من جذر المستودع دائماً
cd "${REPO_ROOT}"

exec "${PY}" -m streamlit run "${APP}" \
  --server.address 0.0.0.0 \
  --server.port "${PORT:-8501}" \
  --server.headless true
