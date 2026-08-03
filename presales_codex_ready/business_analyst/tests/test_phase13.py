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


# ─── 13-3: الأدوار الخمسة ─────────────────────────────────────────────────────


def _as(auth, role):
    """يدخل بحساب بهذا الدور ويعيد معرّفه."""
    from utils import db

    username = f"user_{role}"
    assert auth.add_user(username, "strong-pass-1", role=role) is None
    user_id = db.get_user(username)["id"]
    auth.start_session(user_id)
    return user_id


def test_writer_neither_sees_keys_nor_deletes_a_tender(auth):
    """شرط قبول 13-3 في طبقة الصلاحيات نفسها."""
    _as(auth, auth.WRITER)

    assert auth.can("sections.write")
    assert auth.can("tables.edit")
    assert auth.can("projects.create")
    assert not auth.can("settings.manage")     # المفاتيح
    assert not auth.can("users.manage")
    assert not auth.can("projects.delete")     # حذف منافسة
    assert not auth.can("company.edit")


def test_each_role_gets_exactly_its_matrix_row(auth):
    expected = {
        auth.ADMIN: set(auth.PERMISSIONS),
        auth.BID_MANAGER: {
            "data.manage", "projects.create", "projects.edit", "projects.delete",
            "tables.edit", "sections.write", "sections.assign", "review.run",
            "assistant.ask", "company.edit", "export", "audit.view",
        },
        auth.WRITER: {
            "projects.create", "projects.edit", "tables.edit", "sections.write",
            "assistant.ask", "export",
        },
        auth.REVIEWER: {"review.run", "assistant.ask", "export"},
        auth.VIEWER: set(),
    }
    for role, permissions in expected.items():
        assert auth.permissions_of(role) == permissions, role


def test_viewer_may_do_nothing_but_read(auth):
    _as(auth, auth.VIEWER)
    assert auth.permissions_of(auth.VIEWER) == set()
    for permission in auth.PERMISSIONS:
        assert auth.blocked(permission), permission


def test_reviewer_runs_the_committee_but_writes_no_text(auth):
    """المراجع يفحص ولا يكتب — وإلا اختلط الفحص بالتحرير."""
    _as(auth, auth.REVIEWER)
    assert auth.can("review.run")
    assert not auth.can("sections.write")
    assert not auth.can("tables.edit")


def test_unknown_permission_is_denied_to_everyone_but_the_admin(auth):
    """خطأ مطبعي في اسم صلاحية يجب أن يُغلق الباب لا أن يفتحه."""
    _as(auth, auth.WRITER)
    assert not auth.can("does.not.exist")

    _as(auth, auth.ADMIN)
    assert auth.can("does.not.exist")


def test_unknown_role_is_treated_as_the_least_privileged(auth, temp_db):
    """دور غريب في القاعدة (ترقية أو تلف) لا يُمنح صلاحيات."""
    user_id = _as(auth, auth.ADMIN)
    temp_db.set_user_role(user_id, "superuser")

    assert auth.role_of() == auth.VIEWER
    assert not auth.can("settings.manage")


def test_new_users_get_the_least_privileged_role(auth, temp_db):
    """حساب جديد لا يرث صلاحيات من أنشأه."""
    assert auth.add_user("sara", "strong-pass-1") is None
    assert temp_db.get_user("sara")["role"] == auth.WRITER
    assert auth.NEW_USER_ROLE != auth.ADMIN


def test_first_account_is_an_admin(auth, temp_db):
    """وإلا لم يوجد من يدير المفاتيح ولا الحسابات في نظام جديد."""
    assert auth.create_first_admin("boss", "strong-pass-1") is None
    assert temp_db.get_user("boss")["role"] == auth.ADMIN


def test_unknown_role_is_refused_on_write(auth, temp_db):
    assert auth.add_user("sara", "strong-pass-1", role="superuser") \
        == "au.err_unknown_role"
    assert temp_db.get_user("sara") is None

    admin = _as(auth, auth.ADMIN)
    other = auth.add_user("omar", "strong-pass-2", role=auth.WRITER)
    assert other is None
    assert auth.set_role(temp_db.get_user("omar")["id"], "superuser") \
        == "au.err_unknown_role"
    assert admin


def test_only_a_user_manager_changes_roles(auth, temp_db):
    """الكاتب لا يرقّي نفسه ولا غيره."""
    auth.add_user("omar", "strong-pass-2", role=auth.REVIEWER)
    target = temp_db.get_user("omar")["id"]

    _as(auth, auth.WRITER)
    assert auth.set_role(target, auth.ADMIN) == "au.err_forbidden"
    assert temp_db.get_user_by_id(target)["role"] == auth.REVIEWER


def test_nobody_changes_their_own_role(auth, temp_db):
    """خفض ذاتي بالخطأ يقفل الإدارة على الجميع."""
    admin = _as(auth, auth.ADMIN)
    auth.add_user("second", "strong-pass-2", role=auth.ADMIN)

    assert auth.can_change_role(admin) is False
    assert auth.set_role(admin, auth.VIEWER) == "au.err_last_admin"
    assert temp_db.get_user_by_id(admin)["role"] == auth.ADMIN


def test_the_last_admin_keeps_role_and_account(auth, temp_db):
    """نظام يعمل بلا مدير نظام لا تُدار مفاتيحه ولا حساباته."""
    boss = _as(auth, auth.ADMIN)
    auth.add_user("omar", "strong-pass-2", role=auth.WRITER)
    writer_id = temp_db.get_user("omar")["id"]

    # مدير آخر يحاول تنزيل المدير الوحيد
    auth.start_session(writer_id)
    temp_db.set_user_role(writer_id, auth.ADMIN)
    assert auth.can_change_role(boss) is True     # لم يعد الوحيد

    temp_db.set_user_role(writer_id, auth.WRITER)
    assert auth.can_change_role(boss) is False    # عاد وحيداً
    assert auth.can_disable(boss) is False


def test_role_of_falls_back_for_a_signed_out_visitor(auth):
    assert auth.role_of() == auth.VIEWER
    assert auth.blocked("projects.edit")


# ─── 13-4: إسناد الأقسام ─────────────────────────────────────────────────────


@pytest.fixture()
def sections(auth, fake_streamlit):
    """هيكل عرض في جلسة معزولة مع طبقة الصلاحيات فوقه."""
    from utils import state

    state.init_state()
    return state


def _own(state, key, owner):
    assert state.set_section_owner(key, owner) is True
    return next(s for s in state.get_sections() if s["key"] == key)


def test_section_starts_unassigned_and_not_started(sections):
    section = next(s for s in sections.get_sections() if s["kind"] == "ai")
    assert sections.section_owner(section) is None
    assert sections.section_status(section) == "todo"


def test_owner_and_status_survive_a_round_trip(sections):
    section = _own(sections, "exec", 7)
    assert sections.section_owner(section) == 7

    assert sections.set_section_status("exec", "ready") is True
    section = next(s for s in sections.get_sections() if s["key"] == "exec")
    assert sections.section_status(section) == "ready"


def test_unknown_status_is_refused_and_unknown_section_is_ignored(sections):
    assert sections.set_section_status("exec", "done_ish") is False
    assert sections.set_section_owner("no_such_section", 3) is False


def test_a_pre_assignment_section_reads_its_defaults(sections):
    """قسم من منافسة حُفظت قبل 13-4 لا يحمل الحقلين — ولا ينهار."""
    legacy = {"key": "old", "title": "قسم قديم", "kind": "ai", "include": True}
    assert sections.section_owner(legacy) is None
    assert sections.section_status(legacy) == "todo"


def test_a_writer_edits_only_what_is_theirs_or_unassigned(auth, sections):
    """شرط قبول 13-4: تعديل قسم لا يملكه المستخدم محجوب."""
    from utils import db

    auth.add_user("sara", "strong-pass-1", role=auth.WRITER)
    auth.add_user("omar", "strong-pass-2", role=auth.WRITER)
    sara = db.get_user("sara")["id"]
    omar = db.get_user("omar")["id"]

    auth.start_session(sara)
    unassigned = next(s for s in sections.get_sections() if s["key"] == "scope")
    assert auth.can_edit_section(unassigned) is True      # غير مُسند: متاح

    mine = _own(sections, "exec", sara)
    assert auth.can_edit_section(mine) is True

    theirs = _own(sections, "plan", omar)
    assert auth.can_edit_section(theirs) is False         # ← شرط القبول


def test_a_bid_manager_edits_a_section_owned_by_someone_else(auth, sections):
    """مسؤول عن العرض كله لا عن قسم فيه — وإلا تعطّل التسليم بغياب كاتب."""
    from utils import db

    auth.add_user("sara", "strong-pass-1", role=auth.WRITER)
    auth.add_user("manager", "strong-pass-2", role=auth.BID_MANAGER)
    sara = db.get_user("sara")["id"]

    auth.start_session(db.get_user("manager")["id"])
    theirs = _own(sections, "plan", sara)
    assert auth.can_edit_section(theirs) is True
    assert auth.can("sections.assign")


def test_a_reviewer_edits_nothing_even_when_assigned_to_them(auth, sections):
    """الإسناد لا يمنح صلاحية كتابة لمن لا يملكها أصلاً."""
    from utils import db

    auth.add_user("nour", "strong-pass-1", role=auth.REVIEWER)
    nour = db.get_user("nour")["id"]
    auth.start_session(nour)

    assigned_to_them = _own(sections, "exec", nour)
    assert auth.can_edit_section(assigned_to_them) is False
    assert auth.blocked("sections.assign")


def test_a_writer_cannot_reassign_sections(auth, sections):
    auth.add_user("sara", "strong-pass-1", role=auth.WRITER)
    from utils import db

    auth.start_session(db.get_user("sara")["id"])
    assert auth.blocked("sections.assign")


def test_signed_out_visitor_edits_nothing(auth, sections):
    section = _own(sections, "exec", 0)          # 0 يعني غير مُسند
    assert sections.section_owner(section) is None
    assert auth.can_edit_section(section) is False


# ─── 13-5: سجل التدقيق ───────────────────────────────────────────────────────


@pytest.fixture()
def trail(auth):
    """سجل التدقيق فوق قاعدة معزولة، بمستخدم داخل."""
    from utils import audit as audit_module

    _add(auth, "sara", "strong-pass-1", display_name="سارة")
    auth.login("sara", "strong-pass-1")
    return audit_module


def test_every_event_carries_a_person_and_a_time(trail, temp_db):
    """شرط قبول 13-5: كل تغيير قابل للتتبّع لشخص ووقت."""
    assert trail.record(trail.PROJECT_CREATE, project_id=3, project_name="منافسة") is True

    entry = temp_db.list_audit_entries()[0]
    assert entry["username"] == "سارة"
    assert entry["user_id"] == temp_db.get_user("sara")["id"]
    assert entry["created_at"]
    assert entry["action"] == trail.PROJECT_CREATE
    assert entry["project_id"] == 3


def test_login_is_recorded_by_itself(auth, temp_db):
    """الدخول نفسه حدث — وإلا لم يُعرف من كان على الجهاز وقت التغيير."""
    _add(auth, "sara", "strong-pass-1")
    assert temp_db.count_audit_entries() == 0

    auth.login("sara", "strong-pass-1")
    assert [e["action"] for e in temp_db.list_audit_entries()] == ["auth.login"]


def test_the_trail_has_no_update_or_delete(temp_db):
    """سجل يُنقّح ليس سجلاً — الطبقة نفسها لا تملك الأداة."""
    names = dir(temp_db)
    assert "add_audit_entry" in names
    assert not [n for n in names
                if "audit" in n and ("delete" in n or "update" in n or "clear" in n)]


def test_a_deleted_user_leaves_their_trail_behind(trail, temp_db, auth):
    """حذف حساب لا يمحو أثر ما فعله، ولا يترك صفاً بلا اسم."""
    user_id = temp_db.get_user("sara")["id"]
    trail.record(trail.PROJECT_DELETE, project_id=1, project_name="منافسة")

    temp_db.delete_user(user_id)
    entry = temp_db.list_audit_entries(action=trail.PROJECT_DELETE)[0]
    assert entry["username"] == "سارة"          # اللقطة باقية
    assert entry["user_id"] == user_id


def test_events_are_filtered_by_project_and_by_person(trail, temp_db, auth):
    trail.record(trail.EXPORT_BUILD, project_id=1)
    trail.record(trail.EXPORT_BUILD, project_id=2)

    _add(auth, "omar", "strong-pass-2")
    other = temp_db.get_user("omar")["id"]
    auth.start_session(other)                    # يسجّل دخولاً كذلك
    trail.record(trail.EXPORT_BUILD, project_id=1)

    assert len(trail.entries(project_id=1, action=trail.EXPORT_BUILD)) == 2
    assert len(trail.entries(user_id=other, action=trail.EXPORT_BUILD)) == 1


def test_newest_event_comes_first(trail, temp_db):
    trail.record(trail.SECTION_GENERATE, target="section:exec", source=trail.AI)
    trail.record(trail.SECTION_EDIT, target="section:exec")

    actions = [e["action"] for e in trail.entries()]
    assert actions[0] == trail.SECTION_EDIT


def test_section_source_follows_the_last_write(trail):
    """نصّ ولّده النموذج ثم حرّره إنسان صار مسؤولية إنسان."""
    assert trail.section_source("exec", project_id=1) == ""

    trail.record(trail.SECTION_GENERATE, target=trail.section_target("exec"),
                 source=trail.AI, project_id=1)
    assert trail.section_source("exec", project_id=1) == "ai"

    trail.record(trail.SECTION_EDIT, target=trail.section_target("exec"),
                 source=trail.HUMAN, project_id=1)
    assert trail.section_source("exec", project_id=1) == "human"


def test_non_content_events_do_not_change_the_source(trail):
    """الإسناد ليس كتابة — لا يجعل نصاً ولّده النموذج نصَّ إنسان."""
    trail.record(trail.SECTION_GENERATE, target=trail.section_target("exec"),
                 source=trail.AI, project_id=1)
    trail.record(trail.SECTION_ASSIGN, target=trail.section_target("exec"),
                 project_id=1)

    assert trail.section_source("exec", project_id=1) == "ai"


def test_an_unknown_source_is_stored_as_human(trail, temp_db):
    trail.record(trail.SECTION_EDIT, target="section:x", source="magic")
    assert temp_db.list_audit_entries()[0]["source"] == "human"


def test_only_changed_sections_are_recorded_on_save(trail, temp_db):
    before = {"sec_exec": "نص", "sec_plan": "خطة"}
    after = {"sec_exec": "نص أطول", "sec_plan": "خطة"}

    assert trail.record_section_edits(before, after, ["exec", "plan"]) == 1
    entries = temp_db.list_audit_entries(action=trail.SECTION_EDIT)
    assert [e["target"] for e in entries] == ["section:exec"]


def test_a_failing_trail_never_breaks_the_work(trail, monkeypatch, temp_db):
    """أن يفشل حفظ منافسة لأن سطر تدقيق تعذّر أسوأ من أثر ناقص."""
    def boom(*a, **k):
        raise RuntimeError("القرص ممتلئ")

    monkeypatch.setattr(temp_db, "add_audit_entry", boom)
    assert trail.record(trail.PROJECT_CREATE) is False


def test_reading_the_trail_is_not_for_everyone(auth):
    """السجل يكشف من فعل ماذا — ليس لكل من يكتب."""
    _add(auth, "kateb", "strong-pass-1", role=auth.WRITER)
    auth.login("kateb", "strong-pass-1")
    assert auth.blocked("audit.view")

    _add(auth, "manager", "strong-pass-2", role=auth.BID_MANAGER)
    auth.login("manager", "strong-pass-2")
    assert auth.can("audit.view")
