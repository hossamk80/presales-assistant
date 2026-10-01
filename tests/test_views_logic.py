"""
اختبارات المنطق المدفون في الشاشات — `views/`.

`views/` كانت أدنى الطبقات تغطيةً (٥١٪). وليست كلّها قابلةً للفحص بثمن
معقول: شاشةُ Streamlit عرضٌ لا قرار. لكن فيها دوالّ **تحمل قراراً**،
وغيابها عن الفحص هو الفراغ الحقيقي — لا عدد الأسطر.

ما يلي يفحص تلك الدوالّ وحدها: حجز الأمر قبل إرساله إلى دفاتر العميل ·
تنظيف المرفقات قبل إنفاق التوكنات · قراءة جدول الكميات محلياً بلا نموذج ·
حفظ ما تغيّر وحده من الصلاحيات · وتسجيل قرار الاعتماد.
"""

import pandas as pd
import pytest


# ─── دفع أمر البيع: الحجز قبل الإرسال ────────────────────────────────────────
#
# أخطر مسار في النظام: يكتب في النظام المحاسبي للعميل. والنمط المحروس هنا
# **الحجز قبل الإرسال**: السجلّ يُوضع أولاً فلا تمرّ ضغطتان بأمرين، ويُمحى
# إن فشل الإرسال — أثرٌ زائد أهون من أمرٍ مكرَّر في دفاتر العميل.


class _Connector:
    """موصّل يدفع ويسجّل ما وصله."""

    def __init__(self, result=None, raises=None):
        self.result = result
        self.raises = raises
        self.calls = []

    def push_order(self, order):
        self.calls.append(order)
        if self.raises is not None:
            raise self.raises
        return self.result


@pytest.fixture()
def projects_view(temp_db, fake_streamlit):
    from views import projects
    return projects


@pytest.fixture()
def order():
    # الشكل كما تبنيه `orders.build`: `fingerprint` تقرأ `quantity` و `unit`
    return {"reference": "BID-1-مثال", "customer": "جهة",
            "lines": [{"name": "خادم", "quantity": 2, "unit": "عدد"}],
            "priced": False}


def _result(ok=True, remote_id="SO-77", message="تم"):
    from utils.connectors.base import PushResult
    return PushResult(ok, remote_id, message)


def test_a_successful_push_records_the_remote_id(projects_view, temp_db, order):
    """
    بلا معرّف بعيد لا يستطيع أحد أن يفتح ما أُنشئ ولا أن يتحقّق منه، فيصير
    الدفع فعلاً بلا أثر يُراجَع.
    """
    pid = temp_db.create_project("منافسة", {})
    connector = _Connector(_result())

    projects_view._push_order({"id": pid}, connector, "odoo", order)

    stored = temp_db.connector_order(pid, "odoo")
    assert stored is not None
    assert stored["remote_id"] == "SO-77"
    assert len(connector.calls) == 1


def test_a_second_push_for_the_same_tender_never_reaches_the_connector(
        projects_view, temp_db, order):
    """
    **المنع في التخزين لا في الواجهة**: ضغطتان متتاليتان، أو جلستان، لا
    تُنتجان أمرين. والموصّل لا يُستدعى أصلاً في الثانية.
    """
    pid = temp_db.create_project("منافسة", {})
    first = _Connector(_result())
    projects_view._push_order({"id": pid}, first, "odoo", order)

    second = _Connector(_result(remote_id="SO-99"))
    projects_view._push_order({"id": pid}, second, "odoo", order)

    assert second.calls == [], "الأمر الثاني وصل الموصّل"
    assert temp_db.connector_order(pid, "odoo")["remote_id"] == "SO-77"


def test_a_failed_push_erases_the_reservation_so_a_retry_is_possible(
        projects_view, temp_db, order, fake_streamlit):
    """
    لو بقي الحجز بعد فشل الإرسال لامتنع الدفع المشروع إلى الأبد — والعميل
    بلا أمر، والنظام يقول إنه دُفع.
    """
    pid = temp_db.create_project("منافسة", {})
    failing = _Connector(_result(ok=False, remote_id="", message="رفض الخادم"))

    projects_view._push_order({"id": pid}, failing, "odoo", order)

    assert temp_db.connector_order(pid, "odoo") is None
    assert any(kind == "error" for kind, _ in fake_streamlit.messages)

    # وإعادة المحاولة بعد إصلاح العطل تمرّ
    ok = _Connector(_result())
    projects_view._push_order({"id": pid}, ok, "odoo", order)
    assert temp_db.connector_order(pid, "odoo")["remote_id"] == "SO-77"


def test_a_connector_exception_also_erases_the_reservation(
        projects_view, temp_db, order, fake_streamlit):
    """انقطاعُ شبكةٍ وسط الإرسال ليس أمراً مدفوعاً."""
    from utils.connectors import ConnectorError

    pid = temp_db.create_project("منافسة", {})
    boom = _Connector(raises=ConnectorError("انقطع الاتصال"))

    projects_view._push_order({"id": pid}, boom, "odoo", order)

    assert temp_db.connector_order(pid, "odoo") is None
    assert any(kind == "error" for kind, _ in fake_streamlit.messages)


def test_two_connectors_are_two_independent_orders(projects_view, temp_db, order):
    """
    المنع لكل (منافسة · نظام) لا لكل منافسة: من يملك نظامين محاسبيين يدفع
    إلى كلٍّ منهما مرّة.
    """
    pid = temp_db.create_project("منافسة", {})
    projects_view._push_order({"id": pid}, _Connector(_result()), "odoo", order)
    projects_view._push_order({"id": pid},
                              _Connector(_result(remote_id="X-1")), "sap", order)

    assert temp_db.connector_order(pid, "odoo")["remote_id"] == "SO-77"
    assert temp_db.connector_order(pid, "sap")["remote_id"] == "X-1"


# ─── تنظيف المرفقات قبل إنفاق التوكنات ───────────────────────────────────────


@pytest.fixture()
def analysis_view(temp_db, fake_streamlit):
    from views import analysis
    return analysis


def test_identical_attachments_are_not_sent_twice(analysis_view):
    """
    الملفّ نفسه مرفوعاً باسمين يُدفع ثمنه مرّتين في كل استدعاء — بلا متطلب
    واحد إضافي.
    """
    text = "البند الأول: خادم.\nالبند الثاني: ترخيص.\n" * 40
    per_file = {"كراسة.pdf": text, "نسخة.pdf": text}

    notices = analysis_view._clean_attachments(per_file)

    assert len(per_file) == 1, per_file.keys()
    assert any("نسخة" in n or "كراسة" in n for n in notices)


def test_distinct_attachments_are_all_kept(analysis_view):
    """إسقاط مرفقٍ مختلف يفقد متطلبات — أسوأ بكثير من توكنات مكرّرة."""
    per_file = {"أ.pdf": "متطلبات أمن المعلومات " * 60,
                "ب.pdf": "جدول الكميات والمواصفات " * 60}

    analysis_view._clean_attachments(per_file)

    assert set(per_file) == {"أ.pdf", "ب.pdf"}


def test_cleaning_never_returns_more_than_it_was_given(analysis_view):
    """التنظيف يُنقص أو يُبقي — ولا يزيد."""
    per_file = {"ك.pdf": "صفحة ١\nمتطلب حقيقي\nصفحة ٢\nمتطلب آخر\n" * 30}
    before = len(per_file["ك.pdf"])

    analysis_view._clean_attachments(per_file)

    assert len(per_file["ك.pdf"]) <= before


# ─── قراءة جدول الكميات محلياً ───────────────────────────────────────────────


class _Upload:
    def __init__(self, name):
        self.name = name


def test_a_local_parse_never_overwrites_an_edited_table(analysis_view,
                                                        fake_streamlit,
                                                        monkeypatch):
    """
    **قراءة آلية تمحو تعديلات المستخدم أسوأ من استدعاء يُنفق توكناً.**
    جدولٌ لمسه المستخدم لا يُقرأ فوقه، ولو كان الملف قابلاً للقراءة.
    """
    edited = pd.DataFrame({"البند": ["خادم كتبه المستخدم"], "الكمية": [3]})
    fake_streamlit.session_state["df_boq"] = edited

    called = []
    monkeypatch.setattr(analysis_view.boq_parser, "parse_file",
                        lambda f: called.append(f) or (edited, {"rows": 1}))

    notice = analysis_view._try_local_boq([_Upload("كميات.xlsx")])

    assert notice == ""
    assert called == [], "حاول القراءة فوق جدول محرَّر"
    assert fake_streamlit.session_state["df_boq"] is edited


def test_a_file_that_is_not_a_table_is_skipped(analysis_view, fake_streamlit,
                                               monkeypatch):
    """كراسة PDF ليست جدول كميات — ولا تُمرَّر إلى قارئ الجداول."""
    called = []
    monkeypatch.setattr(analysis_view.boq_parser, "parse_file",
                        lambda f: called.append(f) or (None, {}))

    assert analysis_view._try_local_boq([_Upload("كراسة.pdf")]) == ""
    assert called == []


def test_an_unreadable_table_falls_back_silently(analysis_view, fake_streamlit,
                                                 monkeypatch):
    """الفشل رجوعٌ إلى مسار النموذج، لا رسالة خطأ ولا جدول فارغ."""
    monkeypatch.setattr(analysis_view.boq_parser, "parse_file",
                        lambda f: (None, {"rows": 0}))

    assert analysis_view._try_local_boq([_Upload("كميات.xlsx")]) == ""
    assert "df_boq" not in fake_streamlit.session_state


def test_a_readable_table_is_adopted_and_the_editor_key_is_cleared(
        analysis_view, fake_streamlit, monkeypatch):
    """
    `st.data_editor` يحتفظ بتعديلات المستخدم تحت مفتاحه: تركُه بعد استخراج
    آلي يعرض البيانات القديمة فوق الجديدة.
    """
    parsed = pd.DataFrame({"البند": ["خادم"], "الكمية": [2]})
    fake_streamlit.session_state["de_boq"] = {"edited_rows": {0: {}}}
    monkeypatch.setattr(analysis_view.boq_parser, "parse_file",
                        lambda f: (parsed, {"rows": 1}))

    notice = analysis_view._try_local_boq([_Upload("كميات.xlsx")])

    assert notice
    assert "de_boq" not in fake_streamlit.session_state
    assert fake_streamlit.session_state["df_boq"] is parsed


# ─── حفظ مصفوفة الصلاحيات ────────────────────────────────────────────────────


@pytest.fixture()
def settings_view(temp_db, fake_streamlit):
    from views import settings
    return settings


def _permission_frame(settings_view, permission, role, value):
    from utils import auth
    from utils.i18n import t

    holders = set(auth.permission_roles(permission))
    current = {permission: {r: (r in holders) for r in auth.ROLES}}
    row = {t("perm.col_permission"): permission}
    for r in auth.ROLES:
        row[t(f"role.{r}")] = current[permission][r]
    row[t(f"role.{role}")] = value
    return pd.DataFrame([row]), current


def test_only_the_changed_pair_is_stored(settings_view, temp_db, fake_streamlit):
    """
    الزوج الذي لم يُلمَس لا يُخزَّن فيبقى تابعاً للافتراض — فترقية الافتراض
    لاحقاً تسري عليه بدل أن يتجمّد على قيمةٍ نُسخت بلا قصد.
    """
    from utils import auth

    edited, current = _permission_frame(settings_view, "boq.approve",
                                        "reviewer", True)
    settings_view._save_permissions(edited, current)

    assert auth.is_customized("boq.approve", "reviewer")
    # والزوج الذي لم يُلمَس يبقى بلا تجاوز
    assert not auth.is_customized("boq.approve", "bid_manager")
    assert any(kind == "success" for kind, _ in fake_streamlit.messages)


def test_an_unchanged_matrix_stores_nothing_and_says_so(settings_view, temp_db,
                                                        fake_streamlit):
    from utils import auth

    unchanged = "reviewer" in set(auth.permission_roles("boq.approve"))
    edited, current = _permission_frame(settings_view, "boq.approve",
                                        "reviewer", unchanged)
    settings_view._save_permissions(edited, current)

    assert not auth.is_customized("boq.approve", "reviewer")
    assert any(kind == "info" for kind, _ in fake_streamlit.messages)


def test_stripping_a_protected_admin_permission_is_refused_out_loud(
        settings_view, temp_db, fake_streamlit):
    """
    **الرفض يُقال صراحةً**: مديرٌ يظنّ أنه نزع صلاحيةً وهي باقية أسوأ من
    رفضٍ معلَن — يبني على حالةٍ غير التي في النظام.
    """
    from utils import auth

    locked = auth.LOCKED_ADMIN_PERMISSIONS[0]
    edited, current = _permission_frame(settings_view, locked, "admin", False)

    settings_view._save_permissions(edited, current)

    assert auth.ADMIN in auth.permission_roles(locked)
    assert any(kind == "error" for kind, _ in fake_streamlit.messages)


def test_an_unknown_permission_row_is_ignored(settings_view, temp_db,
                                              fake_streamlit):
    """صفٌّ بصلاحية لا نعرفها لا يُخزَّن — ولا يُسقط الحفظ كلّه."""
    from utils.i18n import t

    edited = pd.DataFrame([{t("perm.col_permission"): "لا.توجد",
                            t("role.admin"): True}])
    settings_view._save_permissions(edited, {})

    assert not any(kind == "error" for kind, _ in fake_streamlit.messages)


# ─── قرار الاعتماد ───────────────────────────────────────────────────────────


def test_an_approval_decision_is_recorded_against_the_revision(temp_db,
                                                               fake_streamlit):
    """
    القرار يُختم على **المراجعة** التي رآها المعتمِد: اعتمادٌ بلا رقم مراجعة
    يبقى ساري المفعول على نصٍّ تغيّر بعده.
    """
    from views import review

    pid = temp_db.create_project("منافسة", {})
    review._decide(pid, temp_db.APPROVAL_STAGES[0], temp_db.APPROVED, 7, " ملاحظة ")

    rows = temp_db.list_approvals(pid)
    assert len(rows) == 1
    assert rows[0]["stage"] == temp_db.APPROVAL_STAGES[0]
    assert rows[0]["decision"] == temp_db.APPROVED
    assert rows[0]["revision"] == 7
    assert rows[0]["note"] == "ملاحظة"


# ─── اعتماد الكميات المحسوبة (ب-5) ───────────────────────────────────────────


@pytest.fixture()
def tables_view(temp_db, fake_streamlit):
    from views import tables
    return tables


@pytest.fixture()
def derived_boq(fake_streamlit):
    """جدول فيه كميةٌ مشتقّة تنتظر الاعتماد."""
    from utils import state

    df = pd.DataFrame([
        {"البند": "خادم", "الكمية": 4, "الوحدة": "عدد",
         "أساس الاحتساب": "مستخدم لكل ٥٠ = ٤ خوادم",
         "مصدر الكمية": state.QTY_DERIVED, "معتمَد": False},
    ])
    df = state.migrate_boq_df(df)
    fake_streamlit.session_state["df_boq"] = df
    return df


def test_approving_a_quantity_without_the_permission_changes_nothing(
        tables_view, derived_boq, fake_streamlit, monkeypatch):
    """
    **زرٌّ معطَّل حجبٌ في الواجهة لا حارس.** الفحص عند الفعل هو ما يمنع
    فعلاً — ومن يستدعي الدالّة بأي طريق أخرى يُردّ.
    """
    from utils import quantities

    monkeypatch.setattr(tables_view.auth, "can", lambda p: False)

    tables_view._approve_quantities([0], "خادم")

    after = fake_streamlit.session_state["df_boq"]
    assert quantities.pending(after), "اعتُمدت الكمية بلا صلاحية"


def test_approving_with_the_permission_clears_the_pending_item(
        tables_view, derived_boq, fake_streamlit, monkeypatch):
    from utils import quantities

    monkeypatch.setattr(tables_view.auth, "can", lambda p: True)

    tables_view._approve_quantities([0], "خادم")

    after = fake_streamlit.session_state["df_boq"]
    assert not quantities.pending(after)


def test_an_approved_quantity_reaches_the_export_and_an_unapproved_one_does_not(
        tables_view, derived_boq, fake_streamlit, monkeypatch):
    """
    الاعتماد ليس وسماً للعرض: **الكمية غير المعتمدة تُحجب عن المستند**،
    والمعتمدة تخرج. وهذا ما يربط اللوحة بالضمانة التي تَعِد بها.
    """
    from utils import quantities

    withheld = quantities.export_df(fake_streamlit.session_state["df_boq"])
    assert withheld is None or withheld.empty or \
        not any(withheld["الكمية"].astype(str).str.contains("4"))

    monkeypatch.setattr(tables_view.auth, "can", lambda p: True)
    tables_view._approve_quantities([0], "خادم")

    exported = quantities.export_df(fake_streamlit.session_state["df_boq"])
    assert exported is not None and not exported.empty


# ─── تطبيق ملاحظة مراجعة على قسم ─────────────────────────────────────────────


@pytest.fixture()
def review_view(temp_db, fake_streamlit):
    from views import review
    return review


def _finding(section="المنهجية الفنية"):
    return {"id": "f-1", "section": section, "lens_label": "تجاري",
            "severity": "حرجة", "issue": "لا جدول زمني",
            "impact": "خصم درجات", "suggested_text": "", "applied": False}


def test_a_finding_for_a_section_that_is_gone_is_refused_not_guessed(
        review_view, fake_streamlit):
    """
    قسمٌ حُذف بعد المراجعة: الملاحظة لا تُطبَّق على قسمٍ آخر «قريب» — تطبيقٌ
    على غير موضعه يفسد نصّاً سليماً ويترك العيب قائماً.
    """
    ok = review_view._apply_finding(_finding("قسم محذوف"), [], "m")

    assert ok is False
    assert any(kind == "error" for kind, _ in fake_streamlit.messages)


def test_applying_a_finding_keeps_the_previous_text_for_undo(
        review_view, fake_streamlit, monkeypatch):
    """
    **إعادة الكتابة تُتلف نصّاً كتبه إنسان.** بلا حفظ السابق لا رجوع، وقرارُ
    قبول الصياغة الجديدة يصير بلا رجعة.
    """
    from utils.state import section_content_key

    sections = [{"key": "meth", "title": "المنهجية الفنية", "content": "نصّ قديم"}]
    fake_streamlit.session_state[section_content_key("meth")] = "نصّ قديم"
    fake_streamlit.session_state["ta_meth"] = "مسوّدة المحرِّر"
    fake_streamlit.session_state["review_findings"] = [_finding()]
    monkeypatch.setattr(review_view, "ai_generate", lambda *a, **k: "نصّ منقَّح")

    ok = review_view._apply_finding(_finding(), sections, "m")

    ckey = section_content_key("meth")
    assert ok is True
    assert fake_streamlit.session_state[ckey] == "نصّ منقَّح"
    assert fake_streamlit.session_state[f"_undo_{ckey}"] == "نصّ قديم"
    # ومفتاح المحرِّر يُمسح وإلا عُرضت المسوّدة القديمة فوق الجديد
    assert "ta_meth" not in fake_streamlit.session_state
    assert fake_streamlit.session_state["review_findings"][0]["applied"] is True


def test_a_failed_call_leaves_the_section_untouched(review_view, fake_streamlit,
                                                    monkeypatch):
    """
    **قاعدة ثابتة**: فشل استدعاء النموذج لا يمسح نصّ المستخدم. ولا يُسجَّل
    «طُبِّقت» على ملاحظةٍ لم تُطبَّق.
    """
    from utils.state import section_content_key

    sections = [{"key": "meth", "title": "المنهجية الفنية", "content": "نصّ قديم"}]
    ckey = section_content_key("meth")
    fake_streamlit.session_state[ckey] = "نصّ قديم"
    fake_streamlit.session_state["review_findings"] = [_finding()]
    monkeypatch.setattr(review_view, "ai_generate", lambda *a, **k: "")

    ok = review_view._apply_finding(_finding(), sections, "m")

    assert ok is False
    assert fake_streamlit.session_state[ckey] == "نصّ قديم"
    assert f"_undo_{ckey}" not in fake_streamlit.session_state
    assert fake_streamlit.session_state["review_findings"][0]["applied"] is False
