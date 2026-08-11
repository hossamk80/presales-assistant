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

cd "${REPO_ROOT}"
exec "${PY}" -m pytest tests/ "${@:--q}"
