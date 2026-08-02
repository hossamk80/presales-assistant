"""
اختبارات المرحلة 10 — الملاحق والتعديلات · الجدول الزمني · المخطط · التحقّق ·
اتساق الأرقام · لوحة المواعيد.
"""
import pandas as pd
import pytest


# ══════════════════════════════════════════════════════════════════════════════
#  الجدول الزمني: قراءة المدة والتحقّق
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def tl():
    from utils import timeline
    return timeline


def _plan(rows) -> pd.DataFrame:
    from utils.state import TIMELINE_COLUMNS

    if not rows:
        return pd.DataFrame(columns=TIMELINE_COLUMNS)
    return pd.DataFrame(rows)[TIMELINE_COLUMNS]


def _phase(number, name, start, duration, depends="", deliverables="",
           payment=False, weight=0.0) -> dict:
    return {
        "رقم المرحلة": number, "المرحلة": name, "البداية (أسبوع)": start,
        "المدة (أسبوع)": duration, "يعتمد على": depends,
        "التسليمات": deliverables, "معلم دفع": payment, "وزن الإنجاز %": weight,
    }


@pytest.mark.parametrize("text, weeks", [
    ("12 شهراً", 48),
    ("٦ أشهر", 24),
    ("24 أسبوعاً", 24),
    ("سنة واحدة", 52),
    ("365 يوماً", 52),
    ("اثنا عشر شهراً", 48),
    ("18 months", 72),
])
def test_duration_is_read_in_weeks(tl, text, weeks):
    assert tl.parse_duration_weeks(text) == weeks


@pytest.mark.parametrize("text", ["", None, "غير محدد في المرفقات", "قريباً"])
def test_unreadable_duration_stays_unjudged(tl, text):
    """
    المدة غير المقروءة لا تُقدَّر: الخطة تُقاس عليها، ورقم مُختلَق يمرّر خطة
    تتجاوز العقد.
    """
    assert tl.parse_duration_weeks(text) is None


def test_plan_within_contract_passes(tl):
    plan = _plan([
        _phase(1, "التحليل", 1, 4, weight=25),
        _phase(2, "التنفيذ", 5, 8, depends="1", weight=50),
        _phase(3, "التشغيل", 13, 4, depends="2", weight=25),
    ])
    report = tl.validate(plan, {"contract_duration": "4 أشهر"})
    assert report["span_weeks"] == 16
    assert report["contract_weeks"] == 16
    assert not report["errors"]


def test_plan_exceeding_contract_is_an_error(tl):
    """خطة تتجاوز مدة العقد غير قابلة للتنفيذ مهما حسُنت صياغتها."""
    plan = _plan([_phase(1, "التنفيذ", 1, 30)])
    report = tl.validate(plan, {"contract_duration": "3 أشهر"})
    assert report["errors"]
    assert "تجاوز" in report["errors"][0]


def test_phase_starting_before_its_dependency_ends(tl):
    plan = _plan([
        _phase(1, "التصميم", 1, 6),
        _phase(2, "التنفيذ", 3, 6, depends="1"),
    ])
    report = tl.validate(plan)
    assert any("قبل انتهاء" in e for e in report["errors"])


def test_dependency_on_a_missing_phase_warns(tl):
    plan = _plan([_phase(1, "التنفيذ", 1, 4, depends="7")])
    report = tl.validate(plan)
    assert any("غير موجودة" in w for w in report["warnings"])


def test_deliverable_without_a_phase_is_an_error(tl):
    """كل تسليم رئيسي في الكراسة يجب أن يقع في مرحلة."""
    plan = _plan([_phase(1, "تركيب الخوادم", 1, 4, deliverables="تسليم الخوادم")])
    report = tl.validate(plan, {
        "key_deliverables": ["تركيب الخوادم", "برنامج تدريب المستخدمين"],
    })
    assert "برنامج تدريب المستخدمين" in report["uncovered_deliverables"]
    assert "تركيب الخوادم" not in report["uncovered_deliverables"]
    assert report["errors"]


def test_weights_not_summing_to_hundred_warn(tl):
    plan = _plan([
        _phase(1, "أ", 1, 2, weight=30),
        _phase(2, "ب", 3, 2, depends="1", weight=30),
    ])
    report = tl.validate(plan)
    assert any("أوزان" in w for w in report["warnings"])


def test_idle_weeks_warn(tl):
    plan = _plan([
        _phase(1, "أ", 1, 2),
        _phase(2, "ب", 9, 2, depends="1"),
    ])
    report = tl.validate(plan)
    assert any("بلا أي نشاط" in w for w in report["warnings"])


def test_empty_plan_is_not_an_error(tl):
    report = tl.validate(None)
    assert report["phases"] == 0 and not report["errors"]


def test_extracted_contract_weeks_win_over_text(tl):
    assert tl.contract_weeks({"contract_duration": "3 أشهر"}, 40) == 40
    assert tl.contract_weeks({"contract_duration": "3 أشهر"}, 0) == 12


# ══════════════════════════════════════════════════════════════════════════════
#  الفصل المالي عن الفني
# ══════════════════════════════════════════════════════════════════════════════


def test_payment_milestone_never_reaches_the_technical_document(tl):
    """
    قاعدة منتج ثابتة: الفني والمالي مظروفان منفصلان. عمود معلم الدفع يفيد
    الفريق التجاري داخل النظام ولا يدخل المظروف الفني.
    """
    plan = _plan([_phase(1, "التنفيذ", 1, 4, payment=True)])
    exported = tl.export_df(plan)
    assert "معلم دفع" not in exported.columns
    assert "المرحلة" in exported.columns


def test_export_of_an_empty_plan_is_none(tl):
    assert tl.export_df(None) is None
    assert tl.export_df(pd.DataFrame()) is None


# ══════════════════════════════════════════════════════════════════════════════
#  المخطط الزمني
# ══════════════════════════════════════════════════════════════════════════════


def test_gantt_marks_only_the_active_weeks(tl):
    plan = _plan([
        _phase(1, "التحليل", 1, 2),
        _phase(2, "التنفيذ", 3, 2, depends="1"),
    ])
    grid = tl.gantt_grid(plan)
    assert grid["unit"] == "week" and grid["columns"] == 4
    assert grid["rows"][0]["cells"] == [True, True, False, False]
    assert grid["rows"][1]["cells"] == [False, False, True, True]


def test_long_plans_are_grouped_into_months(tl):
    """خطة سنتين بأعمدة أسبوعية لا تتّسع في صفحة — تُجمَّع حتى تُقرأ."""
    plan = _plan([_phase(1, "التنفيذ", 1, 104)])
    grid = tl.gantt_grid(plan)
    assert grid["unit"] == "month"
    assert grid["columns"] <= tl.MAX_GANTT_COLUMNS
    assert all(grid["rows"][0]["cells"])


def test_gantt_of_an_empty_plan_is_none(tl):
    assert tl.gantt_grid(None) is None
    assert tl.gantt_grid(_plan([])) is None


def test_gantt_row_label_cell_is_never_shaded(tl):
    """التظليل يدلّ على الزمن لا على الاسم."""
    plan = _plan([_phase(1, "التنفيذ", 2, 1)])
    grid = tl.gantt_grid(plan)
    assert grid["rows"][0]["cells"][0] is False


# ══════════════════════════════════════════════════════════════════════════════
#  تحويل الاستخراج إلى جدول
# ══════════════════════════════════════════════════════════════════════════════


def test_extracted_phases_become_a_table():
    from utils.state import TIMELINE_COLUMNS, timeline_to_df

    df = timeline_to_df({"phases": [
        {"phase_number": 1, "phase_name": "التحليل", "start_week": 1,
         "duration_weeks": 3, "depends_on": "", "deliverables": "وثيقة المتطلبات",
         "payment_milestone": True, "weight_percent": 20},
    ]})
    assert list(df.columns) == TIMELINE_COLUMNS
    assert df.iloc[0]["المرحلة"] == "التحليل"
    assert df.iloc[0]["معلم دفع"] is True or bool(df.iloc[0]["معلم دفع"])


def test_phase_without_a_name_is_dropped():
    from utils.state import timeline_to_df

    df = timeline_to_df({"phases": [{"phase_name": "  ", "start_week": 1}]})
    assert df.iloc[0]["المرحلة"] == ""      # الجدول الافتراضي


def test_broken_numbers_fall_back_instead_of_crashing():
    from utils.state import timeline_to_df

    df = timeline_to_df({"phases": [
        {"phase_name": "أ", "start_week": "غير معروف", "duration_weeks": None},
    ]})
    assert int(df.iloc[0]["البداية (أسبوع)"]) == 1
    assert int(df.iloc[0]["المدة (أسبوع)"]) == 1


def test_timeline_migration_adds_missing_columns():
    from utils.state import TIMELINE_COLUMNS, migrate_timeline_df

    old = pd.DataFrame({"المرحلة": ["أ"], "المدة (أسبوع)": [3]})
    assert list(migrate_timeline_df(old).columns) == TIMELINE_COLUMNS
    assert list(migrate_timeline_df(None).columns) == TIMELINE_COLUMNS


# ══════════════════════════════════════════════════════════════════════════════
#  اتساق الأرقام بين الأقسام
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def cs():
    from utils import consistency
    return consistency


def test_sections_stating_different_durations_conflict(cs):
    findings = cs.check([
        {"title": "الملخص التنفيذي", "content": "مدة التنفيذ 12 شهراً من تاريخ الترسية."},
        {"title": "المنهجية", "content": "مدة التنفيذ 18 شهراً وفق الخطة."},
    ])
    assert any(f["kind"] == "sections_disagree" for f in findings)


def test_agreeing_sections_produce_no_finding(cs):
    findings = cs.check([
        {"title": "الملخص", "content": "مدة التنفيذ 12 شهراً."},
        {"title": "المنهجية", "content": "مدة التنفيذ 12 شهراً."},
    ])
    assert not [f for f in findings if f["kind"] == "sections_disagree"]


def test_section_contradicting_the_timeline(cs):
    plan = _plan([_phase(1, "التنفيذ", 1, 20)])
    findings = cs.check(
        [{"title": "الملخص", "content": "مدة التنفيذ 12 شهراً."}], plan
    )
    assert any(f["kind"] == "section_vs_timeline" for f in findings)


def test_section_promising_more_than_the_contract(cs):
    findings = cs.check(
        [{"title": "الملخص", "content": "مدة التنفيذ 18 شهراً."}],
        None,
        {"contract_duration": "12 شهراً"},
    )
    assert any(f["kind"] == "section_vs_contract" for f in findings)


def test_warranty_duration_is_not_mistaken_for_execution(cs):
    """
    مدة الضمان رقم مشروع يختلف عن مدة التنفيذ. الخلط بينهما يُنتج تحذيراً
    كاذباً يُفقد الفحص مصداقيته فيُتجاهَل.
    """
    findings = cs.check([
        {"title": "الملخص", "content": "مدة التنفيذ 12 شهراً."},
        {"title": "الضمان", "content": "فترة الضمان 24 شهراً بعد التسليم النهائي."},
    ])
    assert not findings


def test_unit_differences_are_tolerated(cs):
    """«ثلاثة أشهر» و«12 أسبوعاً» نفس المدة بوحدتين — ليست تناقضاً."""
    findings = cs.check([
        {"title": "أ", "content": "مدة التنفيذ 3 أشهر."},
        {"title": "ب", "content": "مدة التنفيذ 12 أسبوعاً."},
    ])
    assert not findings


def test_no_sections_no_findings(cs):
    assert cs.check([]) == []
    assert cs.check(None) == []


# ══════════════════════════════════════════════════════════════════════════════
#  الملاحق والتعديلات
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def ad():
    from utils import addenda
    return addenda


def test_identical_uploads_have_no_changes(ad):
    texts = {"كراسة.pdf": "بند 1: توريد خوادم\nبند 2: تركيب"}
    diff = ad.diff_versions(texts, dict(texts))
    assert not ad.has_changes(diff)


def test_added_and_removed_files_are_detected(ad):
    diff = ad.diff_versions(
        {"كراسة.pdf": "نص"}, {"كراسة.pdf": "نص", "ملحق-1.pdf": "تعديل"}
    )
    assert diff["added"] == ["ملحق-1.pdf"]
    assert ad.has_changes(diff)
    assert "تعديل" in diff["new_text"]


def test_changed_lines_are_captured(ad):
    diff = ad.diff_versions(
        {"كراسة.pdf": "بند 4-7: شهادة الأيزو مطلوبة\nبند 5: التسليم"},
        {"كراسة.pdf": "بند 4-7: شهادة الأيزو 27001 مطلوبة\nبند 5: التسليم"},
    )
    stats = ad.summarize(diff)
    assert stats["changed_files"] == 1
    assert stats["added_lines"] == 1 and stats["removed_lines"] == 1


def test_requirement_is_matched_by_its_clause_reference(ad):
    df = pd.DataFrame([{
        "المعرّف": "REQ-007", "التصنيف": "Technical", "مرجع البند": "4-7",
        "المتطلب": "تقديم شهادة أيزو", "الأهمية": "High",
        "استراتيجية الاستجابة": "", "الالتزام": "نعم",
        "الشهادة المطلوبة": "", "التغطية": "مغطّى", "القسم المغطّي": "المنهجية",
    }])
    diff = {"new_text": "تعديل على البند 4-7: تُقبل الشهادة من جهة معتمدة فقط."}
    affected = ad.affected_requirements(df, diff)
    assert len(affected) == 1 and affected[0]["req_id"] == "REQ-007"


def test_requirement_is_matched_by_shared_wording(ad):
    df = pd.DataFrame([{
        "المعرّف": "REQ-002", "التصنيف": "Technical", "مرجع البند": "",
        "المتطلب": "توريد وتركيب أجهزة الخوادم الافتراضية", "الأهمية": "High",
        "استراتيجية الاستجابة": "", "الالتزام": "نعم",
        "الشهادة المطلوبة": "", "التغطية": "مغطّى", "القسم المغطّي": "",
    }])
    diff = {"new_text": "تعديل: تركيب أجهزة الخوادم الافتراضية يشمل الترخيص."}
    assert ad.affected_requirements(df, diff)


def test_unrelated_requirement_is_not_flagged(ad):
    """مطابقة فضفاضة تُغرق المستخدم بمتطلبات لم يمسّها التعديل فيتجاهل الكل."""
    df = pd.DataFrame([{
        "المعرّف": "REQ-003", "التصنيف": "Legal", "مرجع البند": "9-1",
        "المتطلب": "إقرار عدم تعارض المصالح", "الأهمية": "Low",
        "استراتيجية الاستجابة": "", "الالتزام": "نعم",
        "الشهادة المطلوبة": "", "التغطية": "مغطّى", "القسم المغطّي": "",
    }])
    diff = {"new_text": "تعديل على مواصفات كابلات الشبكة والتمديدات."}
    assert ad.affected_requirements(df, diff) == []


def test_empty_change_affects_nothing(ad):
    df = pd.DataFrame([{"المعرّف": "REQ-1", "المتطلب": "شيء", "مرجع البند": ""}])
    assert ad.affected_requirements(df, {"new_text": ""}) == []


def test_affected_rows_return_to_unchecked(ad):
    """
    تعديل على الكراسة يُبطل تغطية سابقة: ما ثبت أنه مغطّى كان مغطّى للنص
    القديم. وإعادته «غير مفحوص» تُعيد تفعيل بوابة التصدير تلقائياً.
    """
    from utils.state import COVERAGE_UNCHECKED

    df = pd.DataFrame([
        {"المعرّف": "REQ-1", "المتطلب": "أ", "مرجع البند": "1",
         "التغطية": "مغطّى", "القسم المغطّي": "المنهجية"},
        {"المعرّف": "REQ-2", "المتطلب": "ب", "مرجع البند": "2",
         "التغطية": "مغطّى", "القسم المغطّي": "الجودة"},
    ])
    updated = ad.mark_unchecked(df, [{"position": 0}])
    assert updated.iloc[0]["التغطية"] == COVERAGE_UNCHECKED
    assert updated.iloc[0]["القسم المغطّي"] == ""
    assert updated.iloc[1]["التغطية"] == "مغطّى"


def test_marking_blocks_export_again():
    """
    الغاية من إعادة الوسم: متطلب حرج على شرط تغيّر يوقف التصدير حتى يُعاد
    فحصه — لا يمرّ بتغطية ثبتت لنصّ ملغى.
    """
    from utils import addenda, traceability

    df = pd.DataFrame([{
        "المعرّف": "REQ-1", "التصنيف": "Technical", "مرجع البند": "4-7",
        "المتطلب": "شهادة أيزو", "الأهمية": "High",
        "استراتيجية الاستجابة": "", "الالتزام": "نعم", "الشهادة المطلوبة": "",
        "التغطية": "مغطّى", "القسم المغطّي": "المنهجية",
    }])
    assert not traceability.coverage_summary(df)["blocking"]

    updated = addenda.mark_unchecked(df, [{"position": 0}])
    assert traceability.coverage_summary(updated)["blocking"]


# ══════════════════════════════════════════════════════════════════════════════
#  نسخ المرفقات في قاعدة البيانات
# ══════════════════════════════════════════════════════════════════════════════


def test_versions_are_stored_and_compared(temp_db):
    pid = temp_db.create_project("منافسة", {})
    temp_db.add_attachment_version(pid, {"كراسة.pdf": "النص الأول"}, {"كراسة.pdf": "rfp"})
    temp_db.add_attachment_version(pid, {"كراسة.pdf": "النص الثاني"}, {"كراسة.pdf": "rfp"})

    versions = temp_db.list_attachment_versions(pid)
    assert len(versions) == 2

    latest = temp_db.load_attachment_version(versions[0]["id"])
    assert latest["payload"]["texts"]["كراسة.pdf"] == "النص الثاني"

    previous = temp_db.previous_attachment_version(pid)
    assert previous["payload"]["texts"]["كراسة.pdf"] == "النص الأول"


def test_versions_die_with_their_project(temp_db):
    pid = temp_db.create_project("منافسة", {})
    temp_db.add_attachment_version(pid, {"a.pdf": "x"}, {})
    temp_db.delete_project(pid)
    assert temp_db.list_attachment_versions(pid) == []


def test_single_version_has_no_previous(temp_db):
    pid = temp_db.create_project("منافسة", {})
    temp_db.add_attachment_version(pid, {"a.pdf": "x"}, {})
    assert temp_db.previous_attachment_version(pid) is None


# ══════════════════════════════════════════════════════════════════════════════
#  التصدير: القسم الزمني في Word و PDF
# ══════════════════════════════════════════════════════════════════════════════


def _timeline_sections():
    return [{"key": "timeline_table", "title": "الجدول الزمني",
             "kind": "table_timeline", "content": ""}]


def test_word_export_includes_the_timeline_and_excludes_payment():
    from docx import Document

    from utils.file_handler import build_word_document

    plan = _plan([
        _phase(1, "التحليل", 1, 2, deliverables="وثيقة المتطلبات", payment=True),
        _phase(2, "التنفيذ", 3, 2, depends="1"),
    ])
    bio = build_word_document(
        company_name="شركة", sections=_timeline_sections(), df_timeline=plan,
    )
    text = "\n".join(p.text for p in Document(bio).paragraphs)
    tables = Document(bio).tables
    joined = text + "\n" + "\n".join(
        c.text for tb in tables for row in tb.rows for c in row.cells
    )
    assert "التحليل" in joined and "التنفيذ" in joined
    assert "معلم دفع" not in joined, "عمود مالي تسرّب إلى المظروف الفني"


def test_word_export_survives_an_empty_timeline():
    from utils.file_handler import build_word_document

    bio = build_word_document(
        company_name="شركة", sections=_timeline_sections(), df_timeline=None,
    )
    assert bio.getvalue()


def test_pdf_export_includes_the_timeline():
    pytest.importorskip("reportlab")
    from utils.file_handler import build_pdf_document

    plan = _plan([_phase(1, "التحليل", 1, 2, payment=True)])
    try:
        bio = build_pdf_document(
            company_name="شركة", sections=_timeline_sections(), df_timeline=plan,
        )
    except ImportError as exc:              # لا خط عربي على هذا النظام
        pytest.skip(str(exc))
    assert bio.getvalue().startswith(b"%PDF")


# ══════════════════════════════════════════════════════════════════════════════
#  الهيكل الافتراضي
# ══════════════════════════════════════════════════════════════════════════════


def test_timeline_section_exists_and_is_opt_in():
    """
    يُدرَج بقرار واعٍ: المستخدم قد يفضّل جدولاً زمنياً سردياً داخل قسم
    المنهجية، فلا نفرض عليه جدولاً ثانياً.
    """
    from utils.state import DEFAULT_SECTIONS

    section = next(s for s in DEFAULT_SECTIONS if s["kind"] == "table_timeline")
    assert section["include"] is False


def test_proposed_outline_keeps_the_timeline_section(fake_streamlit):
    """
    اقتراح هيكل جديد يستبدل الأقسام النصية ويُبقي البنيوية. إسقاط الجدول
    الزمني هنا يعني ضياع خطة بُنيت وفُحصت.
    """
    from utils.state import DEFAULT_SECTIONS, get_sections
    from views import doc_builder

    fake_streamlit.session_state["proposal_sections"] = [dict(s) for s in DEFAULT_SECTIONS]
    doc_builder._apply_proposed_outline([
        {"section_id": 1, "section_title": "الملخص التنفيذي",
         "purpose": "", "key_points_to_address": []},
    ])
    kinds = [s["kind"] for s in get_sections()]
    assert "table_timeline" in kinds
