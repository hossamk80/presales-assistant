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

# مفاتيح ثابتة لا نصوص — التسمية تتغيّر مع لغة الواجهة، المفتاح لا
NAV_PAGES = ["dashboard", "tenders", "workspace", "company", "settings", "data"]


@pytest.fixture(autouse=True)
def real_streamlit(monkeypatch, tmp_path):
    """
    يُبطل بديل streamlit المزيّف من conftest لهذا الملف، ويعزل قاعدة البيانات.
    """
    for name in [m for m in list(sys.modules)
                 if m == "streamlit" or m.startswith(("streamlit.", "utils", "views", "components"))]:
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setenv("ANALYST_DB_PATH", str(tmp_path / "smoke.db"))
    monkeypatch.syspath_prepend(str(APP_DIR))
    yield


def _nav_buttons(at):
    """
    أزرار التنقّل في الشريط العلوي وحدها — شاشة الدخول تعرض عناصر أخرى،
    فوجود زر ليس دليلاً على الوصول إلى الشاشات.
    """
    return [b for b in at.button if (b.key or "").startswith("nav_")]


def _signed_in_user(role: str = "admin", username: str = "tester") -> int:
    """
    حساب فعّال في قاعدة الاختبار — بعد 13-2 لا شاشة تُرسم بلا دخول، فبقية
    اختبارات الإقلاع تحتاج جلسة قائمة كي تصل إلى الصفحات أصلاً.
    """
    from utils import auth, db

    return db.create_user(username, auth.hash_password("test-password"),
                          username.title(), role=role)


def _run(page: str | None = None, user_id: int | None = -1):
    """`user_id=None` يشغّل التطبيق بلا دخول — لاختبار الحارس نفسه."""
    from streamlit.testing.v1 import AppTest

    if user_id == -1:
        user_id = _signed_in_user()

    at = AppTest.from_file(str(APP_FILE), default_timeout=90)
    if user_id is not None:
        at.session_state["auth_user_id"] = user_id
    at.run()
    if page is not None:
        # `nav_selection` وحده مصدر التوجيه بعد استبدال الشريط الجانبي بشريط
        # علوي: الأزرار تكتب فيه، والتوجيه يقرأ منه.
        at.session_state["nav_selection"] = page
        at.run()
    return at


def test_app_starts_without_exception():
    at = _run()
    assert not at.exception, f"التطبيق رفع استثناءً عند الإقلاع: {at.exception}"


def test_top_nav_has_exactly_the_intended_pages():
    """
    مجلد views/ سُمّي كذلك تحديداً كي لا يلتقطه نظام الصفحات التلقائي في
    Streamlit ويضيف عناصر تنقّل شبحية. لو أُعيد لاسم pages/ لكسر هذا الاختبار.
    """
    from utils.i18n import t

    at = _run()
    buttons = _nav_buttons(at)
    assert buttons, "لا يوجد عنصر تنقّل في الشريط العلوي"
    assert [b.key for b in buttons] == [f"nav_{k}" for k in NAV_PAGES]
    for key, button in zip(NAV_PAGES, buttons):
        assert t(f"nav.{key}") in button.label, \
            f"عنصر التنقل {key} لا يطابق {button.label}"


def test_clicking_a_nav_button_switches_page():
    """الشريط العلوي يوجّه فعلاً لا يرسم أزراراً معطّلة عن التوجيه."""
    at = _run()
    next((b for b in at.button if b.key == "nav_company")).click().run()
    assert not at.exception
    assert at.session_state["nav_selection"] == "company"


@pytest.mark.parametrize("page", NAV_PAGES)
def test_every_page_renders(page):
    at = _run(page)
    assert not at.exception, f"الصفحة «{page}» رفعت استثناءً: {at.exception}"


def test_no_api_key_does_not_crash_workspace():
    """مساحة العمل يجب أن تُرسم وترشد المستخدم بدل الانهيار بلا مفتاح."""
    at = _run("workspace")
    assert not at.exception


def test_no_screen_renders_before_sign_in():
    """
    شرط قبول 13-2: لا وصول لأي شاشة قبل الدخول. بلا جلسة يجب ألا يظهر تنقّل
    ولا محتوى صفحة — شاشة الدخول وحدها.
    """
    _signed_in_user()                       # النظام مهيّأ، لكن لا جلسة
    at = _run(user_id=None)
    assert not at.exception
    assert not _nav_buttons(at), "عنصر التنقّل ظهر لمستخدم غير مسجَّل دخوله"
    assert at.text_input, "شاشة الدخول لم تُرسم"


def test_first_run_offers_account_setup():
    """قاعدة بلا مستخدم لا تُقفل على نفسها: تعرض تهيئة أول حساب."""
    at = _run(user_id=None)
    assert not at.exception
    assert not _nav_buttons(at)
    assert at.text_input, "شاشة التهيئة بلا حقول"


def test_disabled_account_loses_its_open_session():
    """تعطيل حساب يُخرج صاحبه من جلسته القائمة لا عند دخوله التالي."""
    from utils import db

    user_id = _signed_in_user()
    at = _run(page=None, user_id=user_id)
    assert _nav_buttons(at), "المستخدم الفعّال لم يصل إلى الشاشات"

    db.set_user_active(user_id, False)
    at.run()
    assert not at.exception
    assert not _nav_buttons(at), "حساب معطَّل ظلّ يرى الشاشات"


def test_default_outline_is_available():
    from utils.state import DEFAULT_SECTIONS

    at = _run("workspace")
    assert not at.exception
    assert len(DEFAULT_SECTIONS) >= 6


# ─── 13-3: الأدوار على الشاشات ────────────────────────────────────────────────


def _button(at, key: str):
    return next((b for b in at.button if b.key == key), None)


def test_writer_sees_no_api_keys():
    """شرط قبول 13-3، الشقّ الأول: الكاتب لا يرى المفاتيح."""
    admin = _signed_in_user("admin", "boss")
    writer = _signed_in_user("writer", "kateb")

    as_writer = _run("settings", user_id=writer)
    assert not as_writer.exception
    assert not [i for i in as_writer.text_input if "API Key" in i.label], \
        "الكاتب رأى حقل مفتاح الموفّر"

    # وللتأكد أن الشاشة نفسها تعرضه لمن يملكه — وإلا فالاختبار يمر بلا معنى
    as_admin = _run("settings", user_id=admin)
    assert [i for i in as_admin.text_input if "API Key" in i.label], \
        "مدير النظام لم يعد يرى حقل المفتاح"


def test_writer_cannot_delete_a_tender():
    """شرط قبول 13-3، الشقّ الثاني: الكاتب لا يحذف منافسة."""
    from utils import db

    admin = _signed_in_user("admin", "boss")
    writer = _signed_in_user("writer", "kateb")
    pid = db.create_project("منافسة", {}, "REF", "جهة")

    as_writer = _run("tenders", user_id=writer)
    assert not as_writer.exception
    delete_btn = _button(as_writer, f"del_{pid}")
    assert delete_btn is not None, "زر الحذف لم يُرسم أصلاً"
    assert delete_btn.disabled, "الكاتب يستطيع حذف منافسة"

    # والكتابة نفسها متاحة له: الإنشاء غير محجوب
    assert _button(as_writer, f"dup_{pid}").disabled is False

    as_admin = _run("tenders", user_id=admin)
    assert _button(as_admin, f"del_{pid}").disabled is False, \
        "مدير النظام لم يعد يستطيع الحذف"


def test_viewer_gets_a_read_only_workspace():
    """المطّلع يقرأ ولا يكتب — لا حفظ ملف جهات ولا إنشاء منافسة."""
    viewer = _signed_in_user("viewer", "mottale")
    at = _run("tenders", user_id=viewer)
    assert not at.exception
    assert _button(at, "rec_save_entities").disabled
    create = next((b for b in at.button if "new_project" in (b.key or "")), None)
    assert create is not None and create.disabled, "المطّلع أنشأ منافسة"
