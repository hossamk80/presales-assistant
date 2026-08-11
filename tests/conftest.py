"""
tests/conftest.py — تهيئة مشتركة للاختبارات.

وحدات المشروع تستورد streamlit على مستوى الوحدة وتقرأ session_state. خارج
دورة تشغيل حقيقية لا تتوفّر تلك الحالة، فنركّب بديلاً خفيفاً يكفي لاختبار
المنطق الخالص (التقسيم، التحليل، البناء، قاعدة البيانات).

اختبار إقلاع التطبيق ككل يستخدم streamlit الحقيقي عبر AppTest — انظر
test_app_smoke.py.
"""
import os
import sys
import types
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))


class _Spinner:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Progress:
    def progress(self, *a, **k):
        pass

    def empty(self):
        pass


class _Column:
    """عمود تخطيط: يبتلع كل استدعاء عرض ويصلح كمدير سياق."""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __getattr__(self, name):
        def noop(*a, **k):
            return None
        return noop


class FakeStreamlit(types.ModuleType):
    """بديل مبسّط لواجهة streamlit يلتقط الرسائل بدل عرضها."""

    def __init__(self):
        super().__init__("streamlit")
        self.session_state = {}
        self.messages = []

    # الرسائل
    def error(self, msg, *a, **k):
        self.messages.append(("error", str(msg)))

    def warning(self, msg, *a, **k):
        self.messages.append(("warning", str(msg)))

    def info(self, msg, *a, **k):
        self.messages.append(("info", str(msg)))

    def success(self, msg, *a, **k):
        self.messages.append(("success", str(msg)))

    def caption(self, msg, *a, **k):
        self.messages.append(("caption", str(msg)))

    # عناصر لا تُستخدم في منطق الاختبار
    def spinner(self, *a, **k):
        return _Spinner()

    def expander(self, *a, **k):
        return _Spinner()

    def progress(self, *a, **k):
        return _Progress()

    def columns(self, spec, *a, **k):
        n = spec if isinstance(spec, int) else len(spec)
        return [_Column() for _ in range(n)]

    def code(self, *a, **k):
        pass

    def cache_resource(self, *a, **k):
        if a and callable(a[0]):
            return a[0]

        def deco(fn):
            return fn
        return deco

    cache_data = cache_resource

    def __getattr__(self, name):
        def noop(*a, **k):
            return None
        return noop


@pytest.fixture(autouse=True)
def fake_streamlit(monkeypatch):
    """يُركّب البديل قبل أي استيراد لوحدات المشروع، ويُنظّف بعده."""
    fake = FakeStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", fake)
    for name in [m for m in list(sys.modules) if m.startswith(("utils", "views", "components"))]:
        monkeypatch.delitem(sys.modules, name, raising=False)
    return fake


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """قاعدة بيانات معزولة لكل اختبار."""
    path = tmp_path / "test.db"
    monkeypatch.setenv("ANALYST_DB_PATH", str(path))
    for name in [m for m in list(sys.modules) if m.startswith("utils")]:
        monkeypatch.delitem(sys.modules, name, raising=False)
    from utils import db
    monkeypatch.setattr(db, "DB_PATH", str(path))
    db._local.__dict__.pop("conn", None)
    yield db
    db._local.__dict__.pop("conn", None)


@pytest.fixture()
def app_dir():
    return APP_DIR
