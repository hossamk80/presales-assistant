"""
اختبار إقلاع التطبيق باستخدام streamlit الحقيقي (لا البديل المزيّف).

هذا ما يثبت أن النظام يقلع فعلاً — بقية الاختبارات تغطي المنطق الخالص.
AppTest يشغّل السكربت كاملاً بلا متصفح ولا خادم.
"""
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parent.parent
APP_FILE = APP_DIR / "app.py"

NAV_PAGES = [
    "🏠 لوحة التحكم",
    "📁 المنافسات",
    "🚀 مساحة العمل",
    "🏢 ملف الشركة",
    "⚙️ إعدادات النظام",
    "💾 إدارة البيانات",
]


@pytest.fixture(autouse=True)
def real_streamlit(monkeypatch, tmp_path):
    """
    يُبطل بديل streamlit المزيّف من conftest لهذا الملف، ويعزل قاعدة البيانات.
    """
    for name in [m for m in list(sys.modules)
                 if m == "streamlit" or m.startswith(("streamlit.", "utils", "views", "components"))]:
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setenv("IMDAD_DB_PATH", str(tmp_path / "smoke.db"))
    monkeypatch.syspath_prepend(str(APP_DIR))
    yield


def _run(page: str | None = None):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP_FILE), default_timeout=90)
    at.run()
    if page is not None:
        at.session_state["nav_selection"] = page
        at.run()
    return at


def test_app_starts_without_exception():
    at = _run()
    assert not at.exception, f"التطبيق رفع استثناءً عند الإقلاع: {at.exception}"


def test_sidebar_has_exactly_the_intended_pages():
    """
    مجلد views/ سُمّي كذلك تحديداً كي لا يلتقطه نظام الصفحات التلقائي في
    Streamlit ويضيف عناصر تنقّل شبحية. لو أُعيد لاسم pages/ لكسر هذا الاختبار.
    """
    at = _run()
    assert at.radio, "لا يوجد عنصر تنقّل في الشريط الجانبي"
    assert list(at.radio[0].options) == NAV_PAGES


@pytest.mark.parametrize("page", NAV_PAGES)
def test_every_page_renders(page):
    at = _run(page)
    assert not at.exception, f"الصفحة «{page}» رفعت استثناءً: {at.exception}"


def test_no_api_key_does_not_crash_workspace():
    """مساحة العمل يجب أن تُرسم وترشد المستخدم بدل الانهيار بلا مفتاح."""
    at = _run("🚀 مساحة العمل")
    assert not at.exception


def test_default_outline_is_available():
    from utils.state import DEFAULT_SECTIONS

    at = _run("🚀 مساحة العمل")
    assert not at.exception
    assert len(DEFAULT_SECTIONS) >= 6
