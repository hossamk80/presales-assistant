"""
اختبارات المرحلة 12 — طبقة الأدلة.

السجلات · مصفوفة الكوادر · حقن الأدلة في قرار الخوض · درجة المحتوى المحلي ·
الملاحق المرقّمة.
"""
import datetime

import pandas as pd
import pytest


@pytest.fixture()
def rec():
    from utils import records
    return records


# ══════════════════════════════════════════════════════════════════════════════
#  تعريف السجلات وسلامتها
# ══════════════════════════════════════════════════════════════════════════════


def test_every_registry_is_well_formed(rec):
    for name, spec in rec.REGISTRIES.items():
        assert spec["label_key"] and spec["hint_key"], name
        keys = [c["key"] for c in spec["columns"]]
        assert keys, name
        assert len(keys) == len(set(keys)), f"عمود مكرّر في {name}"


def test_every_registry_label_exists_in_both_languages(rec):
    """كل تسمية عمود نص واجهة — تخضع لقاعدة ثنائية اللغة."""
    from utils.i18n import UI_STRINGS

    for name, spec in rec.REGISTRIES.items():
        for key in [spec["label_key"], spec["hint_key"]] + \
                [c["label_key"] for c in spec["columns"]]:
            assert key in UI_STRINGS, f"{key} ({name}) غير معرّف في i18n"
            assert UI_STRINGS[key]["ar"].strip() and UI_STRINGS[key]["en"].strip()


def test_blank_rows_are_not_saved(rec):
    """المحرّر يترك صفاً فارغاً دائماً — لا يُحفظ."""
    assert rec.is_blank("people", rec.blank_row("people")) is True
    row = rec.blank_row("people")
    row["name"] = "سارة"
    assert rec.is_blank("people", row) is False


def test_normalize_row_coerces_types(rec):
    row = rec.normalize_row("people", {"name": " سارة ", "years": "7.0",
                                       "cv_document": "nan"})
    assert row["name"] == "سارة"
    assert row["years"] == 7
    # "nan" من pandas ليست قيمة يكتبها مستخدم
    assert row["cv_document"] == ""
    # الأعمدة الغائبة تأخذ قيمها الافتراضية لا KeyError
    assert row["availability"] == "غير معلوم"


def test_a_row_with_only_a_number_is_still_blank(rec):
    """سنوات خبرة بلا اسم ليست صفاً — المحرّر يملأ الرقم افتراضياً."""
    row = rec.blank_row("people")
    row["years"] = 5
    assert rec.is_blank("people", row) is True


# ══════════════════════════════════════════════════════════════════════════════
#  التخزين
# ══════════════════════════════════════════════════════════════════════════════


def test_records_roundtrip(temp_db, rec):
    rows = [rec.normalize_row("certificates",
                              {"kind": "ISO 27001", "number": "A-1",
                               "expiry": "2027-05-01"})]
    temp_db.save_records("certificates", rows)
    assert temp_db.list_records("certificates") == rows


def test_save_replaces_the_whole_registry(temp_db, rec):
    temp_db.save_records("people", [rec.normalize_row("people", {"name": "أ"})])
    temp_db.save_records("people", [rec.normalize_row("people", {"name": "ب"})])
    rows = temp_db.list_records("people")
    assert [r["name"] for r in rows] == ["ب"]


def test_registries_do_not_leak_into_each_other(temp_db, rec):
    temp_db.save_records("people", [rec.normalize_row("people", {"name": "أ"})])
    assert temp_db.list_records("vendors") == []


def test_row_order_is_preserved(temp_db, rec):
    names = ["أول", "ثانٍ", "ثالث"]
    temp_db.save_records(
        "people", [rec.normalize_row("people", {"name": n}) for n in names]
    )
    assert [r["name"] for r in temp_db.list_records("people")] == names


def test_entity_lookup_ignores_spelling_variants(temp_db, rec):
    """«وزارة الصحة» و«وزاره الصحه» جهة واحدة — وإلا بقي الملف غير مستدعىً."""
    temp_db.save_records("entities", [
        rec.normalize_row("entities", {"name": "وزارة الصحة", "sector": "صحي"}),
    ])
    found = temp_db.find_entity("وزاره الصحه ")
    assert found and found["sector"] == "صحي"
    assert temp_db.find_entity("وزارة التعليم") is None


# ══════════════════════════════════════════════════════════════════════════════
#  الصلاحية والتواريخ
# ══════════════════════════════════════════════════════════════════════════════


def test_expiring_before_the_deadline_is_detected(rec):
    rows = [{"expiry": "2027-01-01"}, {"expiry": "2030-01-01"}]
    expiring = rec.expiring_before(rows, "expiry", datetime.date(2028, 1, 1))
    assert [r["expiry"] for r in expiring] == ["2027-01-01"]


def test_hijri_expiry_is_read_not_ignored(rec):
    """
    شهادات التصنيف تُؤرَّخ هجرياً كثيراً. قارئ ميلادي وحده يُسقطها من الفحص
    صامتةً — وهي بالضبط ما يجب أن يُفحص.
    """
    parsed = rec.parse_date("1448-11-14")
    assert parsed is not None, "تاريخ هجري لم يُقرأ"
    assert parsed.year in (2027, 2028)


def test_unreadable_date_is_neither_valid_nor_expired(rec):
    rows = [{"expiry": "قريباً"}]
    assert rec.expiring_before(rows, "expiry", datetime.date(2030, 1, 1)) == []
    assert len(rec.undated(rows, "expiry")) == 1


def test_no_deadline_means_no_expiry_judgement(rec):
    assert rec.expiring_before([{"expiry": "2000-01-01"}], "expiry", None) == []


# ══════════════════════════════════════════════════════════════════════════════
#  حقن السجلات في قرار الخوض (12-6)
# ══════════════════════════════════════════════════════════════════════════════


def test_records_block_carries_the_rows(temp_db, fake_streamlit, rec):
    from utils.state import records_block

    temp_db.save_records("references", [
        rec.normalize_row("references", {
            "client": "وزارة الصحة", "scope": "شبكات", "our_role": "مقاول رئيسي",
        }),
    ])
    block = records_block()
    assert "وزارة الصحة" in block and "شبكات" in block


def test_records_block_is_empty_without_records(temp_db, fake_streamlit):
    from utils.state import records_block

    assert records_block() == ""


def test_entity_block_recalls_the_profile(temp_db, fake_streamlit, rec):
    from utils.state import entity_block

    temp_db.save_records("entities", [
        rec.normalize_row("entities", {
            "name": "وزارة الصحة",
            "evaluation_pattern": "توزن الخبرة السابقة بثقل",
        }),
    ])
    fake_streamlit.session_state["project_context"] = {
        "issuing_entity": "وزاره الصحه",
    }
    assert "توزن الخبرة السابقة بثقل" in entity_block()


def test_entity_block_empty_when_unknown(temp_db, fake_streamlit):
    from utils.state import entity_block

    fake_streamlit.session_state["project_context"] = {"issuing_entity": "جهة"}
    assert entity_block() == ""


def test_gonogo_prompt_prefers_rows_over_prose():
    """قاعدة الحكم يجب أن تذكر السجلات صراحةً، وإلا بقي القرار على نص حر."""
    from utils import ai_engine

    prompt = ai_engine.PROMPTS["gonogo"]
    assert "سجلات أدلة الشركة" in prompt
    assert "غير معلوم" in prompt


# ══════════════════════════════════════════════════════════════════════════════
#  مصفوفة الكوادر (12-2)
# ══════════════════════════════════════════════════════════════════════════════


def test_personnel_schema_is_well_formed():
    from utils import ai_engine

    schema = ai_engine.KEY_PERSONNEL_SCHEMA
    assert schema["type"] == "OBJECT"
    role = schema["properties"]["roles"]["items"]
    for field in ("required_role", "candidate", "evidence", "gap"):
        assert field in role["properties"]


def test_personnel_prompt_forbids_inventing_a_name():
    """اسم مُختلق يمرّ إلى العرض فيُكتشف عند التحقق ويُسقط المنافسة."""
    from utils import ai_engine

    prompt = ai_engine.EXTRACT_PROMPTS["key_personnel"]
    assert "لا تخترع اسماً" in prompt
    assert "{people}" in prompt


def test_personnel_to_df_keeps_roles_without_a_candidate(fake_streamlit):
    """الدور الذي يُحذف لأنه بلا مرشّح هو الفجوة التي تُكتشف في لجنة الفحص."""
    from utils.state import personnel_to_df

    df = personnel_to_df({"roles": [
        {"required_role": "مدير مشروع", "requirements": "PMP + 10 سنوات",
         "candidate": "سارة", "evidence": "PMP · 12 سنة"},
        {"required_role": "مسؤول أمن معلومات", "requirements": "CISSP",
         "candidate": "", "gap": "لا مرشّح في السجل"},
    ]})
    assert len(df) == 2
    assert "مسؤول أمن معلومات" in list(df["الدور المطلوب"])


def test_personnel_gaps_flags_missing_and_gapped_roles(fake_streamlit):
    from utils.state import personnel_gaps, personnel_to_df

    df = personnel_to_df({"roles": [
        {"required_role": "مدير مشروع", "requirements": "PMP",
         "candidate": "سارة", "evidence": "PMP"},
        {"required_role": "مهندس شبكات", "requirements": "CCNP", "candidate": ""},
        {"required_role": "محلل أمن", "requirements": "CISSP",
         "candidate": "خالد", "gap": "الشهادة منتهية"},
    ]})
    gaps = personnel_gaps(df)
    assert "مهندس شبكات" in gaps and "محلل أمن" in gaps
    assert "مدير مشروع" not in gaps


def test_personnel_df_survives_a_snapshot_roundtrip(temp_db, fake_streamlit):
    from utils.state import (
        get_state_snapshot, load_state_snapshot, personnel_to_df,
    )

    fake_streamlit.session_state["df_personnel"] = personnel_to_df({"roles": [
        {"required_role": "مدير مشروع", "requirements": "PMP", "candidate": "سارة"},
    ]})
    snapshot = get_state_snapshot()
    fake_streamlit.session_state["df_personnel"] = None
    load_state_snapshot(snapshot)
    assert "مدير مشروع" in list(
        fake_streamlit.session_state["df_personnel"]["الدور المطلوب"]
    )


# ══════════════════════════════════════════════════════════════════════════════
#  درجة المحتوى المحلي (12-8)
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def lc():
    from utils import local_content
    return local_content


def test_required_percentage_is_read_from_the_rfp(lc):
    assert lc.required_percentage("لا تقل نسبة المحتوى المحلي عن 40%") == 40.0
    assert lc.required_percentage("النسبة 25٪ للبند الأول و 60٪ إجمالاً") == 60.0


def test_no_declared_percentage_is_none_not_zero(lc):
    """غياب الرقم يعني «غير معلن» — صفرٌ يُنتج فجوة كاذبة."""
    assert lc.required_percentage("يلتزم المورد بالمحتوى المحلي") is None
    assert lc.required_percentage("") is None


def test_impossible_percentages_are_ignored(lc):
    assert lc.required_percentage("بلغت الزيادة 350%") is None


def test_missing_components_are_excluded_not_zeroed(lc):
    """
    صفر عن غياب بيانات يُنتج درجة متشائمة كاذبة يُبنى عليها قرار انسحاب.
    """
    only_band = lc.score("بلاتيني", boq_rows=[], vendors=[])
    assert only_band["estimate"] == pytest.approx(100.0)
    assert set(only_band["missing"]) == {"mandatory_items", "local_support"}


def test_score_combines_available_components(lc):
    result = lc.score(
        "أخضر متوسط",                                   # 70
        boq_rows=[{"البند": "أ", "القائمة الإلزامية": True},
                  {"البند": "ب", "القائمة الإلزامية": False}],   # 50
        vendors=[{"vendor": "س", "local_support": True}],        # 100
    )
    expected = (0.5 * 70 + 0.3 * 50 + 0.2 * 100) / 1.0
    assert result["estimate"] == pytest.approx(expected)
    assert result["missing"] == []


def test_gap_against_the_required_level(lc):
    result = lc.score("أصفر", boq_rows=[], vendors=[],
                      requirement_text="لا تقل النسبة عن 50%")
    assert result["required"] == 50.0
    assert result["gap"] == pytest.approx(20.0)
    assert result["meets"] is False


def test_no_gap_when_the_estimate_clears_the_bar(lc):
    result = lc.score("بلاتيني", boq_rows=[], vendors=[],
                      requirement_text="لا تقل النسبة عن 50%")
    assert result["meets"] is True
    assert result["gap"] == 0.0


def test_score_is_always_declared_an_estimate(lc):
    """الرقم تقدير تخطيطي لا شهادة — الواجهة تعرض ذلك اعتماداً على العلم."""
    assert lc.score("بلاتيني", [], [])["is_estimate"] is True


def test_unknown_band_leaves_saudization_missing(lc):
    result = lc.score("غير محدد", boq_rows=[], vendors=[])
    assert result["estimate"] is None
    assert "saudization" in result["missing"]


# ══════════════════════════════════════════════════════════════════════════════
#  الملاحق المرقّمة (12-9)
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def apx():
    from utils import appendices
    return appendices


def _loader(data):
    return lambda registry: data.get(registry, [])


def test_appendices_are_lettered_in_order(apx, rec):
    built = apx.build_all(_loader({
        "people": [rec.normalize_row("people", {"name": "سارة"})],
        "certificates": [rec.normalize_row("certificates", {"kind": "ISO"})],
    }))
    assert [a["letter"] for a in built] == ["أ", "ب"]
    assert "السير الذاتية" in built[0]["title"]


def test_empty_registries_do_not_consume_a_letter(apx, rec):
    """ملحق فارغ في عرض يوحي بدليل غير موجود، وثغرة في الترقيم تُربك القارئ."""
    built = apx.build_all(_loader({
        "certificates": [rec.normalize_row("certificates", {"kind": "ISO"})],
    }))
    assert len(built) == 1
    assert built[0]["letter"] == "أ"


def test_internal_columns_are_not_exported(apx, rec):
    """الإتاحة تخدم الفريق داخلياً ولا تُعرض للجهة."""
    built = apx.build_all(
        _loader({"people": [rec.normalize_row("people", {"name": "سارة"})]}),
        labels={c["label_key"]: c["key"] for c in rec.columns_of("people")},
    )
    assert "availability" not in built[0]["headers"]
    assert "name" in built[0]["headers"]


def test_booleans_render_as_words(apx, rec):
    built = apx.build_all(_loader({"vendors": [
        rec.normalize_row("vendors", {"vendor": "س", "local_support": True}),
    ]}))
    assert any("نعم" in row for row in built[0]["rows"])


def test_selection_limits_which_appendices_are_built(apx, rec):
    data = {
        "people": [rec.normalize_row("people", {"name": "سارة"})],
        "certificates": [rec.normalize_row("certificates", {"kind": "ISO"})],
    }
    built = apx.build_all(_loader(data), selected=["certificates"])
    assert len(built) == 1 and built[0]["registry"] == "certificates"


def test_available_lists_only_populated_registries(apx, rec):
    data = {"people": [rec.normalize_row("people", {"name": "سارة"})]}
    assert apx.available(_loader(data)) == ["people"]


def test_every_appendix_row_matches_its_headers(apx, rec):
    built = apx.build_all(_loader({
        "references": [rec.normalize_row("references", {"client": "وزارة"})],
    }))
    for appendix in built:
        for row in appendix["rows"]:
            assert len(row) == len(appendix["headers"])
