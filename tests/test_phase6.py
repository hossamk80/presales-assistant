"""
اختبارات المرحلة 6 — مصفوفة التتبّع: ربط المتطلبات بأقسام العرض.
"""
import pandas as pd
import pytest


@pytest.fixture()
def tr():
    from utils import traceability
    return traceability


@pytest.fixture()
def st_mod():
    from utils import state
    return state


def _df(rows):
    from utils.state import COMPLIANCE_COLUMNS, DEFAULT_COMPLIANCE_DF
    base = {c: "" for c in COMPLIANCE_COLUMNS}
    return pd.DataFrame([{**base, **r} for r in rows]) if rows \
        else DEFAULT_COMPLIANCE_DF.copy()


SECTIONS = [
    {"key": "methodology", "title": "المنهجية", "kind": "ai", "include": True},
    {"key": "team", "title": "الفريق", "kind": "ai", "include": True},
    {"key": "skipped", "title": "قسم غير مُدرَج", "kind": "ai", "include": False},
    {"key": "comp_table", "title": "جدول الامتثال", "kind": "table_compliance",
     "include": True},
]

CONTENT = {
    "methodology": "نتبع منهجية رشيقة ونلتزم بشهادة ISO 27001.",
    "team": "مدير مشروع معتمد PMP.",
    "skipped": "نص لن يُصدَّر.",
}


# ─── المخطط والأعمدة ───────────────────────────────────────────────────────────


def test_coverage_columns_added_to_the_existing_matrix(st_mod):
    """توسعة للمصفوفة القائمة لا جدول موازٍ."""
    assert st_mod.COMPLIANCE_COLUMNS[-2:] == ["التغطية", "القسم المغطّي"]
    assert len(st_mod.COMPLIANCE_COLUMNS) == 10


def test_saved_matrix_is_upgraded_with_unchecked_not_missing(st_mod):
    """
    الفرق بين "لم نفحص" و"فحصنا فلم نجد" جوهري: الثاني حكم، والأول غيابه.
    ترقية جدول قديم لا يجوز أن تدّعي أنه فُحص.
    """
    old = pd.DataFrame({
        "المتطلب التقني": ["شهادة ISO"],
        "الالتزام": ["نعم"],
        "التبرير / الملاحظة": ["مرفقة"],
        "الشهادة المطلوبة": ["ISO 27001"],
    })
    out = st_mod.migrate_compliance_df(old)
    assert list(out.columns) == st_mod.COMPLIANCE_COLUMNS
    assert out["التغطية"].iloc[0] == st_mod.COVERAGE_UNCHECKED
    assert out["المتطلب"].iloc[0] == "شهادة ISO"


def test_traceability_schema_requires_status_and_sections(ae_module=None):
    from utils.ai_engine import TRACEABILITY_SCHEMA

    item = TRACEABILITY_SCHEMA["properties"]["coverage"]["items"]
    assert set(item["required"]) == {"req_id", "status", "sections"}
    assert item["properties"]["status"]["enum"] == ["مغطّى", "جزئي", "غير مغطّى"]


def test_traceability_prompt_bans_invented_evidence():
    from utils.ai_engine import EXTRACT_PROMPTS

    prompt = EXTRACT_PROMPTS["traceability"]
    assert "{requirements}" in prompt and "{sections}" in prompt
    assert "حرفي" in prompt
    assert "لا تخترعه" in prompt


# ─── بناء المدخلات ─────────────────────────────────────────────────────────────


def test_requirements_block_carries_id_and_criticality(tr):
    block = tr.requirements_block(_df([
        {"المعرّف": "REQ-001", "المتطلب": "شهادة ISO 27001", "الأهمية": "High",
         "مرجع البند": "4-7"},
    ]))
    assert "REQ-001" in block and "High" in block and "4-7" in block
    assert "شهادة ISO 27001" in block


def test_multiword_arabic_columns_are_read_correctly(tr):
    """
    مصيدة pandas: أسماء الأعمدة التي تحتوي مسافة ("مرجع البند") ليست معرّفات
    Python صالحة، فيستبدلها itertuples بـ _1 و _2 صامتاً وتُقرأ فارغة.
    الأعمدة ذات الكلمة الواحدة تعمل، فالعطل يمرّ دون أن يُلاحَظ.
    """
    df = _df([{"المعرّف": "REQ-001", "المتطلب": "متطلب", "مرجع البند": "4-7-3",
               "الأهمية": "High"}])
    assert "4-7-3" in tr.requirements_block(df)

    covered = tr.apply_coverage(df, [{"req_id": "REQ-001", "status": "مغطّى",
                                      "sections": ["المنهجية"]}])
    assert covered["القسم المغطّي"].iloc[0] == "المنهجية"


def test_requirements_block_skips_blank_rows(tr):
    block = tr.requirements_block(_df([
        {"المعرّف": "", "المتطلب": ""},
        {"المعرّف": "REQ-002", "المتطلب": "متطلب حقيقي"},
    ]))
    assert block.count("\n") == 0
    assert "REQ-002" in block


def test_sections_block_excludes_unincluded_and_tables(tr):
    """تغطية في قسم لن يُصدَّر ليست تغطية."""
    block = tr.sections_block(SECTIONS, CONTENT.get)
    assert "المنهجية" in block and "الفريق" in block
    assert "قسم غير مُدرَج" not in block
    assert "جدول الامتثال" not in block


def test_sections_block_skips_empty_sections(tr):
    block = tr.sections_block(SECTIONS, lambda key: "" if key == "team" else CONTENT.get(key, ""))
    assert "الفريق" not in block


# ─── تطبيق النتيجة ─────────────────────────────────────────────────────────────


def test_apply_coverage_fills_status_and_owner(tr):
    df = _df([{"المعرّف": "REQ-001", "المتطلب": "شهادة ISO"}])
    out = tr.apply_coverage(df, [
        {"req_id": "REQ-001", "status": "مغطّى", "sections": ["المنهجية"],
         "evidence": "نلتزم بشهادة ISO 27001"},
    ])
    assert out["التغطية"].iloc[0] == "مغطّى"
    assert out["القسم المغطّي"].iloc[0] == "المنهجية"


def test_unreported_requirement_stays_unchecked(tr, st_mod):
    """صمت النموذج عن متطلب ليس تغطية له."""
    df = _df([
        {"المعرّف": "REQ-001", "المتطلب": "أول"},
        {"المعرّف": "REQ-002", "المتطلب": "ثانٍ"},
    ])
    out = tr.apply_coverage(df, [{"req_id": "REQ-001", "status": "مغطّى",
                                  "sections": ["المنهجية"]}])
    assert out["التغطية"].iloc[1] == st_mod.COVERAGE_UNCHECKED


def test_invalid_status_is_not_trusted(tr, st_mod):
    df = _df([{"المعرّف": "REQ-001", "المتطلب": "أول"}])
    out = tr.apply_coverage(df, [{"req_id": "REQ-001", "status": "ممتاز",
                                  "sections": ["المنهجية"]}])
    assert out["التغطية"].iloc[0] == st_mod.COVERAGE_UNCHECKED


def test_gap_is_shown_when_nothing_covers_it(tr):
    df = _df([{"المعرّف": "REQ-001", "المتطلب": "خطة صيانة"}])
    out = tr.apply_coverage(df, [{"req_id": "REQ-001", "status": "غير مغطّى",
                                  "sections": [], "gap": "لا ذكر لخطة الصيانة"}])
    assert out["القسم المغطّي"].iloc[0] == "لا ذكر لخطة الصيانة"


def test_apply_coverage_does_not_mutate_the_input(tr, st_mod):
    df = _df([{"المعرّف": "REQ-001", "المتطلب": "أول"}])
    tr.apply_coverage(df, [{"req_id": "REQ-001", "status": "مغطّى",
                            "sections": ["المنهجية"]}])
    assert df["التغطية"].iloc[0] == ""


# ─── الخلاصة وبوابة التصدير ────────────────────────────────────────────────────


def test_summary_counts_every_status(tr):
    df = _df([
        {"المعرّف": "R1", "المتطلب": "أ", "التغطية": "مغطّى"},
        {"المعرّف": "R2", "المتطلب": "ب", "التغطية": "جزئي"},
        {"المعرّف": "R3", "المتطلب": "ج", "التغطية": "غير مغطّى"},
        {"المعرّف": "R4", "المتطلب": "د", "التغطية": "غير مفحوص"},
    ])
    s = tr.coverage_summary(df)
    assert (s["total"], s["covered"], s["partial"], s["missing"], s["unchecked"]) \
        == (4, 1, 1, 1, 1)


@pytest.mark.parametrize("status", ["غير مغطّى", "جزئي", "غير مفحوص"])
def test_high_criticality_blocks_unless_fully_covered(tr, status):
    """
    "غير مفحوص" يحجب مثل "غير مغطّى": لم نتحقق = لا نعرف، ولا يُبنى على ذلك
    قرار تسليم.
    """
    df = _df([{"المعرّف": "R1", "المتطلب": "ضمان بنكي", "الأهمية": "High",
               "التغطية": status}])
    assert tr.coverage_summary(df)["blocking"]


def test_covered_high_criticality_does_not_block(tr):
    df = _df([{"المعرّف": "R1", "المتطلب": "ضمان بنكي", "الأهمية": "High",
               "التغطية": "مغطّى"}])
    assert tr.coverage_summary(df)["blocking"] == []


def test_low_criticality_never_blocks(tr):
    df = _df([{"المعرّف": "R1", "المتطلب": "تفصيل ثانوي", "الأهمية": "Low",
               "التغطية": "غير مغطّى"}])
    assert tr.coverage_summary(df)["blocking"] == []


def test_summary_is_safe_on_missing_table(tr):
    assert tr.coverage_summary(None)["total"] == 0
    assert tr.coverage_summary(pd.DataFrame())["blocking"] == []


def test_summary_ignores_blank_rows(tr):
    """صف فارغ في محرر الجدول ليس متطلباً."""
    df = _df([{"المعرّف": "", "المتطلب": "", "التغطية": "غير مفحوص"}])
    assert tr.coverage_summary(df)["total"] == 0


# ─── التشغيل ───────────────────────────────────────────────────────────────────


def test_run_returns_none_without_requirements_or_text(tr):
    assert tr.run_coverage_check(_df([]), SECTIONS, CONTENT.get) is None
    assert tr.run_coverage_check(
        _df([{"المعرّف": "R1", "المتطلب": "أ"}]), SECTIONS, lambda k: ""
    ) is None


def test_failed_call_leaves_the_matrix_alone(tr, monkeypatch):
    """نتيجة فحص ناقصة أسوأ من غيابها — تُقرأ كتغطية مؤكَّدة."""
    monkeypatch.setattr(tr, "ai_generate_json", lambda *a, **k: None)
    df = _df([{"المعرّف": "R1", "المتطلب": "أ"}])
    assert tr.run_coverage_check(df, SECTIONS, CONTENT.get) is None


def test_run_maps_results_onto_the_matrix(tr, monkeypatch):
    monkeypatch.setattr(tr, "ai_generate_json", lambda *a, **k: {
        "coverage": [{"req_id": "R1", "status": "مغطّى", "sections": ["المنهجية"]}],
    })
    df = _df([{"المعرّف": "R1", "المتطلب": "شهادة ISO"}])
    out = tr.run_coverage_check(df, SECTIONS, CONTENT.get)
    assert out["التغطية"].iloc[0] == "مغطّى"
