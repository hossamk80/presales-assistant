#!/usr/bin/env bash
# تشغيل الاختبارات — من أي مجلد / Run the test suite from any directory.
#
# الاختبارات تستورد `utils` و `views` كحزم عليا، فلا بدّ أن يكون جذر المستودع
# هو مجلد العمل — وهو مجلد التطبيق نفسه بعد نقله إلى الجذر.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="${REPO_ROOT}/.venv/bin/python"

PY="${VENV_PY}"
[ -x "${PY}" ] || PY="$(command -v python3 || command -v python)"

if ! "${PY}" -c "import pytest" 2>/dev/null; then
  echo "❌ pytest غير مثبّت في ${PY}" >&2
  echo "   شغّل التهيئة أولاً: bash .devcontainer/setup.sh" >&2
  exit 1
fi

# `--cov` كأول وسيط يقيس التغطية ويفحص أرضيات كل طبقة — نفس ما يفعله CI.
# بلا العلم يبقى التشغيل سريعاً للحلقة القصيرة.
WITH_COV=0
if [ "${1:-}" = "--cov" ]; then
  WITH_COV=1
  shift
  # رسالة صريحة بدل `unrecognized arguments: --cov` من pytest
  if ! "${PY}" -c "import pytest_cov" 2>/dev/null; then
    echo "❌ pytest-cov غير مثبّت في ${PY}" >&2
    echo "   pip install -r requirements-dev.txt -c constraints.txt" >&2
    exit 1
  fi
fi

cd "${REPO_ROOT}"

# pyflakes قبل الاختبارات — نفس ترتيب CI. مفتاح مكرَّر في قاموس تمرّ عليه
# الاختبارات بصمت، فلا فائدة من كشفه بعدها. غيابه محلياً لا يوقف التشغيل.
if "${PY}" -c "import pyflakes" 2>/dev/null; then
  "${PY}" -m pyflakes app.py utils views components tests scripts
else
  echo "⚠️  pyflakes غير مثبّت — تُخطّى هنا ويفحصها CI" >&2
fi

if [ "${WITH_COV}" = "1" ]; then
  "${PY}" -m pytest tests/ --cov --cov-report=term \
    --cov-report=json:coverage.json "${@:--q}"
  exec "${PY}" scripts/check_coverage.py coverage.json
fi

exec "${PY}" -m pytest tests/ "${@:--q}"
