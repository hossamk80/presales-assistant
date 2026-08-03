"""
tests/test_phase13.py — المرحلة 13: الاستخدام الجماعي.

13-1: جدول الشركة كان مقيَّداً بصف واحد `CHECK (id = 1)`. الاختبارات هنا
تحرس أمرين: أن القاعدة صارت تحتمل أكثر من شركة، وأن قاعدة أُنشئت بالمخطط
القديم تُرقّى بلا فقد بيانات — لا الحمولة ولا القالب ولا الشعار.

13-2: المستخدمون والمصادقة. ما يُحرَس هنا: أن الكلمة لا تُخزَّن كما هي، وأن
سبب الرفض لا يفرّق بين اسم مجهول وكلمة خاطئة، وأن حساباً عُطِّل يسقط من جلسته
القائمة، وأن آخر حساب فعّال لا يُعطَّل فيُقفل النظام على الجميع. حراسة «لا
شاشة قبل الدخول» نفسها في `tests/test_app_smoke.py`.
"""
import json
import sqlite3

import pytest


LEGACY_SCHEMA = """
CREATE TABLE company (
    id       INTEGER PRIMARY KEY CHECK (id = 1),
    payload  TEXT NOT NULL,
    template BLOB,
    logo     BLOB
);
"""


def _write_legacy_db(path, payload, template=None, logo=None):
    """يبني ملف قاعدة بالمخطط القديم قبل أن يفتحه `db` لأول مرة."""
    conn = sqlite3.connect(path)
    conn.executescript(LEGACY_SCHEMA)
    conn.execute(
        "INSERT INTO company (id, payload, template, logo) VALUES (1, ?, ?, ?)",
        (json.dumps(payload, ensure_ascii=False), template, logo),
    )
    conn.commit()
    conn.close()


# ─── 13-1: إلغاء قيد الشركة الأحادية ─────────────────────────────────────────


def test_more_than_one_company_can_be_stored(temp_db):
    db = temp_db
    first = db.create_company("الشركة الأمّ", {"c_name": "الأمّ"})
    second = db.create_company("الذراع التنفيذية", {"c_name": "الذراع"})

    assert first != second
    assert [c["name"] for c in db.list_companies()] == [
        "الشركة الأمّ", "الذراع التنفيذية"]
    assert db.load_company(second)[0]["c_name"] == "الذراع"


def test_company_table_has_no_single_row_constraint(temp_db):
    db = temp_db
    db.save_company({"c_name": "شركة"})
    sql = db.get_conn().execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'company'"
    ).fetchone()["sql"]
    assert "CHECK" not in sql.upper()


def test_legacy_database_upgrades_without_data_loss(temp_db):
    """قاعدة بالمخطط القديم: الصف يبقى، والقيد يزول، وتُقبل شركة ثانية."""
    db = temp_db
    _write_legacy_db(db.DB_PATH, {"c_name": "شركة قديمة", "c_phone": "123"},
                     template=b"DOCX-BYTES", logo=b"PNG-BYTES")

    payload, template, logo = db.load_company()
    assert payload == {"c_name": "شركة قديمة", "c_phone": "123"}
    assert template == b"DOCX-BYTES"
    assert logo == b"PNG-BYTES"

    assert [c["id"] for c in db.list_companies()] == [1]
    new_id = db.create_company("شركة ثانية")
    assert new_id != 1
    assert len(db.list_companies()) == 2


def test_legacy_migration_runs_once_and_keeps_added_rows(temp_db):
    """إعادة فتح القاعدة بعد الترحيل لا تُعيد بناء الجدول ولا تمحو ما أُضيف."""
    db = temp_db
    _write_legacy_db(db.DB_PATH, {"c_name": "شركة قديمة"})
    db.create_company("شركة ثانية")

    db._local.__dict__.pop("conn", None)          # اتصال جديد ⇐ ترحيل جديد
    assert [c["id"] for c in db.list_companies()] == [1, 2]
    assert db.load_company(1)[0] == {"c_name": "شركة قديمة"}


# ─── الشركة الفاعلة ──────────────────────────────────────────────────────────


def test_active_company_defaults_to_oldest(temp_db):
    db = temp_db
    first = db.create_company("أ", {"c_name": "أ"})
    db.create_company("ب", {"c_name": "ب"})
    assert db.active_company_id() == first
    assert db.load_company()[0]["c_name"] == "أ"


def test_active_company_switches_reads_and_writes(temp_db):
    db = temp_db
    first = db.create_company("أ", {"c_name": "أ"})
    second = db.create_company("ب", {"c_name": "ب"})

    db.set_active_company(second)
    assert db.load_company()[0]["c_name"] == "ب"

    db.save_company({"c_name": "ب محدَّثة"}, template=b"T")
    assert db.load_company()[0]["c_name"] == "ب محدَّثة"
    assert db.load_company(first)[0]["c_name"] == "أ"   # الأولى لم تُمَسّ
    assert db.load_company(first)[1] is None


def test_active_company_falls_back_when_selection_deleted(temp_db):
    db = temp_db
    first = db.create_company("أ")
    second = db.create_company("ب")
    db.set_active_company(second)

    assert db.delete_company(second) is True
    assert db.active_company_id() == first


def test_last_company_cannot_be_deleted(temp_db):
    """حذف الشركة الأخيرة يمحو ملف الشركة كاملاً — يُرفض."""
    db = temp_db
    only = db.create_company("أ")
    assert db.delete_company(only) is False
    assert db.delete_company(9999) is False
    assert len(db.list_companies()) == 1


def test_rename_company(temp_db):
    db = temp_db
    cid = db.create_company("اسم قديم")
    db.rename_company(cid, "اسم جديد")
    assert db.list_companies()[0]["name"] == "اسم جديد"


def test_save_company_creates_first_company_implicitly(temp_db):
    """السلوك القديم محفوظ: أول حفظ بلا شركة قائمة يُنشئ واحدة."""
    db = temp_db
    assert db.list_companies() == []
    cid = db.save_company({"c_name": "شركة"})
    assert db.active_company_id() == cid
    assert db.load_company()[0] == {"c_name": "شركة"}


# ─── 13-2: المستخدمون والمصادقة ──────────────────────────────────────────────


@pytest.fixture()
def auth(temp_db):
    """طبقة المصادقة فوق قاعدة معزولة."""
    from utils import auth as auth_module
    return auth_module


def _add(auth, username="sara", password="strong-pass-1", **kw):
    assert auth.add_user(username, password, **kw) is None
    from utils import db
    return db.get_user(username)["id"]


def test_password_is_never_stored_as_written(auth, temp_db):
    user_id = _add(auth, password="strong-pass-1")
    stored = temp_db.get_user_by_id(user_id)["password_hash"]

    assert "strong-pass-1" not in stored
    assert stored.startswith("scrypt$")
    assert auth.verify_password("strong-pass-1", stored)
    assert not auth.verify_password("strong-pass-2", stored)


def test_same_password_hashes_differently_each_time(auth):
    """ملح لكل كلمة: تجزئتان متطابقتان تكشفان أن الحسابين بالكلمة نفسها."""
    first = auth.hash_password("strong-pass-1")
    second = auth.hash_password("strong-pass-1")
    assert first != second
    assert auth.verify_password("strong-pass-1", first)
    assert auth.verify_password("strong-pass-1", second)


def test_verify_rejects_damaged_or_unknown_hashes(auth):
    for stored in ("", "not-a-hash", "md5$abc$def", "scrypt$bad$8$1$zz$zz"):
        assert auth.verify_password("strong-pass-1", stored) is False


def test_legacy_pbkdf2_hash_still_verifies(auth):
    """قاعدة أُنشئت بصيغة أقدم لا تُقفل على أصحابها."""
    import hashlib

    salt, iterations = b"0123456789abcdef", 1000
    digest = hashlib.pbkdf2_hmac("sha256", b"strong-pass-1", salt, iterations, dklen=32)
    stored = f"pbkdf2${iterations}${salt.hex()}${digest.hex()}"

    assert auth.verify_password("strong-pass-1", stored)
    assert not auth.verify_password("wrong", stored)


def test_unknown_user_and_wrong_password_give_the_same_reason(auth):
    """تفريق السببين يكشف أي الأسماء مسجَّل في النظام."""
    _add(auth, "sara", "strong-pass-1")
    assert auth.login("ghost", "whatever") == "au.err_bad_credentials"
    assert auth.login("sara", "wrong-pass-9") == "au.err_bad_credentials"


def test_successful_login_opens_session_and_records_time(auth, temp_db):
    user_id = _add(auth, "sara", "strong-pass-1", display_name="سارة")
    assert temp_db.get_user_by_id(user_id)["last_login"] == ""

    assert auth.login("sara", "strong-pass-1") is None
    assert auth.is_authenticated()
    assert auth.current_user()["display_name"] == "سارة"
    assert temp_db.get_user_by_id(user_id)["last_login"] != ""


def test_current_user_never_exposes_the_hash(auth):
    _add(auth, "sara", "strong-pass-1")
    auth.login("sara", "strong-pass-1")
    assert "password_hash" not in auth.current_user()


def test_username_is_case_insensitive(auth):
    _add(auth, "Sara", "strong-pass-1")
    assert auth.add_user("sara", "strong-pass-2") == "au.err_username_taken"
    assert auth.login("SARA", "strong-pass-1") is None


def test_repeated_failures_trigger_a_cooldown(auth):
    _add(auth, "sara", "strong-pass-1")
    for _ in range(auth.MAX_FAILED_ATTEMPTS):
        assert auth.login("sara", "wrong-pass-9") == "au.err_bad_credentials"

    assert auth.cooldown_remaining() > 0
    # الكلمة الصحيحة نفسها تُرفض أثناء التهدئة — وإلا لم توقف تخميناً
    assert auth.login("sara", "strong-pass-1") == "au.err_cooldown"


def test_disabled_account_is_refused_and_drops_its_open_session(auth, temp_db):
    user_id = _add(auth, "sara", "strong-pass-1")
    other = _add(auth, "omar", "strong-pass-2")
    assert other

    auth.login("sara", "strong-pass-1")
    assert auth.is_authenticated()

    temp_db.set_user_active(user_id, False)
    assert auth.current_user() is None            # الجلسة القائمة تسقط
    # «معطَّل» لا يكشف اسماً: لا يبلغه إلا من يعرف الكلمة الصحيحة أصلاً
    assert auth.login("sara", "strong-pass-1") == "au.err_disabled"
    assert auth.login("sara", "wrong-pass-9") == "au.err_bad_credentials"


def test_weak_password_is_refused_before_the_user_exists(auth, temp_db):
    assert auth.add_user("sara", "short") == "au.err_password_short"
    assert temp_db.get_user("sara") is None
    assert auth.add_user("", "strong-pass-1") == "au.err_username_required"


def test_change_password_needs_the_current_one(auth):
    user_id = _add(auth, "sara", "strong-pass-1")

    assert auth.change_password(
        user_id, "strong-pass-2", "strong-pass-2", current_password="wrong"
    ) == "au.err_current_password"
    assert auth.login("sara", "strong-pass-1") is None

    assert auth.change_password(
        user_id, "strong-pass-2", "strong-pass-2", current_password="strong-pass-1"
    ) is None
    assert auth.login("sara", "strong-pass-2") is None


def test_password_change_rejects_mismatch(auth):
    user_id = _add(auth, "sara", "strong-pass-1")
    assert auth.change_password(user_id, "strong-pass-2", "strong-pass-3",
                                current_password="strong-pass-1") \
        == "au.err_password_mismatch"
    assert auth.login("sara", "strong-pass-1") is None


def test_admin_resets_a_password_without_knowing_the_old_one(auth):
    user_id = _add(auth, "sara", "strong-pass-1")
    assert auth.change_password(user_id, "reset-pass-1") is None
    assert auth.login("sara", "reset-pass-1") is None


def test_first_run_creates_an_admin_then_closes_the_door(auth):
    assert auth.needs_setup()
    assert auth.create_first_admin("admin", "strong-pass-1", "المدير") is None
    assert auth.is_authenticated()
    assert not auth.needs_setup()

    # لا تُنشأ حسابات أخرى من شاشة التهيئة — وإلا صارت باباً خلفياً
    assert auth.create_first_admin("second", "strong-pass-2") == "au.err_setup_done"


def test_setup_refuses_a_weak_password(auth, temp_db):
    assert auth.create_first_admin("admin", "short") == "au.err_password_short"
    assert temp_db.count_users() == 0
    assert auth.needs_setup()


def test_last_active_account_cannot_be_disabled(auth):
    """تعطيل آخر حساب يقفل النظام على الجميع بلا سبيل للدخول."""
    user_id = _add(auth, "sara", "strong-pass-1")
    assert auth.can_disable(user_id) is False

    other = _add(auth, "omar", "strong-pass-2")
    assert auth.can_disable(other) is True

    auth.login("omar", "strong-pass-2")
    assert auth.can_disable(other) is False       # ولا يُعطّل المستخدم نفسه
    assert auth.can_disable(user_id) is True


def test_logout_clears_the_whole_session(auth, fake_streamlit):
    """
    مسح المفتاح وحده يترك تحليل السابق في الذاكرة لمن يدخل بعده على الجهاز.
    """
    _add(auth, "sara", "strong-pass-1")
    auth.login("sara", "strong-pass-1")
    fake_streamlit.session_state["rfp_raw_text"] = "كراسة سرية"

    auth.logout()
    assert not auth.is_authenticated()
    assert fake_streamlit.session_state == {}


def test_duplicate_username_is_refused_at_the_database(temp_db, auth):
    temp_db.create_user("sara", auth.hash_password("strong-pass-1"))
    assert temp_db.create_user("sara", auth.hash_password("strong-pass-2")) is None
    assert temp_db.count_users() == 1
