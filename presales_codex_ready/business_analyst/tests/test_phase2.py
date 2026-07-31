"""
اختبارات المرحلة 2: هيكل العرض وفق معايير اعتماد، ومصفوفة الامتثال الموسّعة.
"""
import pandas as pd
import pytest


@pytest.fixture()
def ae():
    from utils import ai_engine
    return ai_engine


@pytest.fixture()
def tables():
    from views import tables as mod
    return mod


@pytest.fixture()
def builder():
    from views import doc_builder as mod
    return mod


@pytest.fixture()
def state():
    from utils import state as mod
    return mod


# ─── 2.1 هيكل العرض ────────────────────────────────────────────────────────────


def test_outline_schema_matches_spec(ae):
    props = ae.OUTLINE_SCHEMA["properties"]
    assert "proposal_title" in props
    item = props["outline"]["items"]["properties"]
    assert {"section_id", "section_title", "purpose", "key_points_to_address"} <= set(item)
    assert item["section_id"]["type"] == "INTEGER"
    assert item["key_points_to_address"]["type"] == "ARRAY"


def test_outline_prompt_lists_every_mandatory_section(ae):
    prompt = ae.outline_prompt("ar")
    for name in ae.MANDATORY_OUTLINE_SECTIONS:
        assert name in prompt, f"القسم الإلزامي غائب عن التعليمات: {name}"
    assert "{mandatory_sections}" not in prompt


def test_outline_prompt_forbids_pricing(ae):
    """الفصل بين الفني والمالي شرط في معايير اعتماد."""
    prompt = ae.outline_prompt("ar")
    assert "التسعير" in prompt
    assert "قيمة مالية" in prompt or "مالية" in prompt


def test_outline_prompt_follows_language(ae):
    assert ae.language_instruction("en") in ae.outline_prompt("en")
    assert ae.language_instruction("ar") in ae.outline_prompt("ar")


def test_seven_mandatory_sections_defined(ae):
    assert len(ae.MANDATORY_OUTLINE_SECTIONS) == 7


@pytest.mark.parametrize("keyword", [
    "الملخص التنفيذي",
    "ملف الشركة",
    "المنهجية",
    "الجدول الزمني",
    "الهيكل التنظيمي",
    "ضمان الجودة",
])
def test_mandatory_list_matches_the_etimad_six(ae, keyword):
    """الأقسام الستة القياسية في معايير اعتماد، كل منها قسم قائم بذاته."""
    assert any(keyword in name for name in ae.MANDATORY_OUTLINE_SECTIONS), keyword


def test_local_content_stays_mandatory_beyond_the_six(ae):
    """
    المحتوى المحلي ليس ضمن الستة القياسية لكنه إلزامي وله وزن تقييمي في
    المنافسات السعودية — إسقاطه يُفقد درجات لا يعوّضها حسن الصياغة.
    """
    assert any("المحتوى المحلي" in n for n in ae.MANDATORY_OUTLINE_SECTIONS)


def test_methodology_and_timeline_are_separate_sections(ae):
    """تُقيّمهما لجان اعتماد بمعيارين مستقلين، فدمجهما يُضعف الاثنين."""
    methodology = [n for n in ae.MANDATORY_OUTLINE_SECTIONS if "المنهجية" in n]
    timeline = [n for n in ae.MANDATORY_OUTLINE_SECTIONS if "الجدول الزمني" in n]
    assert len(methodology) == 1 and len(timeline) == 1
    assert methodology[0] != timeline[0]
    assert "معالم" in timeline[0]


def test_outline_prompt_demands_persuasive_order_and_scoring_link(ae):
    prompt = ae.outline_prompt("ar")
    assert "الإقناع" in prompt
    assert "معيار تقييم" in prompt


def test_methodology_must_cover_risk_mitigation(ae):
    """عرض بلا معالجة للمخاطر يبدو غير واقعي أمام لجنة الفحص."""
    assert "إدارة المخاطر" in ae.outline_prompt("ar")


def test_quality_is_not_folded_into_the_methodology(ae):
    """
    ضمان الجودة قسم إلزامي مستقل (السادس)؛ حشره داخل المنهجية يكرّره ويُشتّت
    ما تُقيّمه اللجنة بمعيار واحد.
    """
    from utils.state import DEFAULT_SECTIONS

    methodology = next(s for s in DEFAULT_SECTIONS if s["key"] == "methodology")
    assert "إدارة المخاطر" in methodology["guidance"]
    assert "ضمان الجودة" not in methodology["guidance"]


def test_outline_prompt_frames_boq_as_scope_not_pricing(ae):
    prompt = ae.outline_prompt("ar")
    assert "نطاق العمل" in prompt and "لا لتسعّره" in prompt


def test_timeline_keyword_is_not_satisfied_by_the_methodology_title(builder):
    """
    "خطة" وحدها تُطابق "خطة التنفيذ" داخل قسم المنهجية، فيبدو الجدول الزمني
    موجوداً وهو غائب.
    """
    titles = "المنهجية الفنية المقترحة وخطة التنفيذ"
    assert builder._covers(titles, "المنهجية الفنية المقترحة وخطة التنفيذ")
    assert not builder._covers(titles, "الجدول الزمني ومعالم التسليم")


@pytest.mark.parametrize("title", [
    "الجدول الزمني ومعالم التسليم",
    "خطة المشروع والجدول الزمني",
    "مراحل التنفيذ والمعالم",
])
def test_timeline_is_recognised_however_it_is_worded(builder, title):
    assert builder._covers(title, "الجدول الزمني ومعالم التسليم")


def test_every_mandatory_name_matches_itself(builder, ae):
    for name in ae.MANDATORY_OUTLINE_SECTIONS:
        assert builder._covers(name, name), name


# ─── نطاق جدول الكميات في تعليمات الهيكل ───────────────────────────────────────


def test_boq_scope_excludes_quantities_and_prices(fake_streamlit):
    """
    مهندس الهيكل يحتاج ما سيُنفَّذ لا كم؛ تمرير الكميات يفتح باب تسرّب أرقام
    إلى العرض الفني بلا مقابل.
    """
    import pandas as pd
    from utils.state import boq_scope_block

    fake_streamlit.session_state["df_boq"] = pd.DataFrame({
        "رقم البند": ["1"],
        "التصنيف": ["توريد"],
        "البند": ["مبدّل شبكي"],
        "الوصف": ["مبدّل 48 منفذاً"],
        "المواصفات": ["Layer 3"],
        "الكمية": ["120"],
    })
    block = boq_scope_block()
    assert "مبدّل شبكي" in block
    assert "Layer 3" in block
    assert "120" not in block


def test_boq_scope_empty_when_no_table(fake_streamlit):
    from utils.state import boq_scope_block

    fake_streamlit.session_state["df_boq"] = None
    assert boq_scope_block() == ""


def test_boq_scope_truncates_long_tables(fake_streamlit):
    import pandas as pd
    from utils.state import boq_scope_block

    fake_streamlit.session_state["df_boq"] = pd.DataFrame({
        "البند": [f"بند {i}" for i in range(100)],
    })
    block = boq_scope_block(limit=10)
    assert "بند 9" in block
    assert "بند 10" not in block
    assert "90 بنداً آخر" in block


def test_outline_applied_in_section_id_order(builder, fake_streamlit):
    from utils.state import DEFAULT_SECTIONS

    fake_streamlit.session_state["proposal_sections"] = DEFAULT_SECTIONS
    proposed = [
        {"section_id": 3, "section_title": "ثالث", "purpose": "ج", "key_points_to_address": []},
        {"section_id": 1, "section_title": "أول", "purpose": "أ", "key_points_to_address": ["ن1"]},
        {"section_id": 2, "section_title": "ثانٍ", "purpose": "ب", "key_points_to_address": []},
    ]
    builder._apply_proposed_outline(proposed)

    titles = [s["title"] for s in fake_streamlit.session_state["proposal_sections"]
              if s["kind"] == "ai"]
    assert titles == ["أول", "ثانٍ", "ثالث"]


def test_key_points_become_section_guidance(builder, fake_streamlit):
    """النقاط الجوهرية هي ما يوجّه صياغة القسم لاحقاً."""
    from utils.state import DEFAULT_SECTIONS

    fake_streamlit.session_state["proposal_sections"] = DEFAULT_SECTIONS
    builder._apply_proposed_outline([{
        "section_id": 1,
        "section_title": "المنهجية",
        "purpose": "شرح النهج",
        "key_points_to_address": ["نقطة أولى", "نقطة ثانية"],
    }])

    sec = next(s for s in fake_streamlit.session_state["proposal_sections"]
               if s["title"] == "المنهجية")
    assert sec["key_points"] == ["نقطة أولى", "نقطة ثانية"]
    assert "نقطة أولى" in sec["guidance"]
    assert sec["rationale"] == "شرح النهج"


def test_non_numeric_section_id_does_not_crash(builder, fake_streamlit):
    from utils.state import DEFAULT_SECTIONS

    fake_streamlit.session_state["proposal_sections"] = DEFAULT_SECTIONS
    builder._apply_proposed_outline([
        {"section_id": "غير رقمي", "section_title": "أ", "purpose": "", "key_points_to_address": []},
        {"section_id": 1, "section_title": "ب", "purpose": "", "key_points_to_address": []},
    ])
    titles = [s["title"] for s in fake_streamlit.session_state["proposal_sections"]
              if s["kind"] == "ai"]
    assert titles == ["ب", "أ"]


def test_as_int_fallback(builder):
    assert builder._as_int(3) == 3
    assert builder._as_int("4") == 4
    assert builder._as_int(None) == 9999
    assert builder._as_int("x") == 9999


@pytest.mark.parametrize("name", [
    "الملخص التنفيذي", "مؤهلات الشركة والخبرات السابقة", "المنهجية والنهج الفني",
    "خطة العمل والجدول الزمني", "هيكل الفريق والحوكمة",
    "إدارة الجودة ومستويات الخدمة", "الالتزام بالمحتوى المحلي",
])
def test_mandatory_matcher_accepts_reworded_titles(builder, name):
    """
    النموذج يصوغ العناوين بألفاظ مختلفة؛ المطابقة الحرفية تُنتج إنذارات كاذبة.
    """
    assert builder._covers(name, name)


def test_mandatory_matcher_detects_absence(builder):
    assert not builder._covers("خطاب التقديم وإشعار السرية", "الالتزام بالمحتوى المحلي")


# ─── 2.2 مصفوفة الامتثال ───────────────────────────────────────────────────────


def test_compliance_schema_matches_spec(ae):
    props = ae.COMPLIANCE_SCHEMA["properties"]["requirements"]["items"]["properties"]
    assert {
        "req_id", "category", "clause_reference", "requirement_summary",
        "criticality", "proposed_compliance_strategy",
    } <= set(props)
    assert props["category"]["enum"] == ["Technical", "Operational", "Administrative", "Legal"]
    assert props["criticality"]["enum"] == ["High", "Medium", "Low"]


def test_compliance_rows_map_every_field(tables, state):
    items = [{
        "req_id": "REQ-001",
        "category": "Legal",
        "clause_reference": "بند 4-2",
        "requirement_summary": "شهادة سعودة سارية",
        "criticality": "High",
        "proposed_compliance_strategy": "نرفق الشهادة في الملحق أ",
        "certificate": "شهادة سعودة",
    }]
    df = tables._compliance_to_df(items)
    assert list(df.columns) == state.COMPLIANCE_COLUMNS
    row = df.iloc[0]
    assert row["المعرّف"] == "REQ-001"
    assert row["التصنيف"] == "Legal"
    assert row["مرجع البند"] == "بند 4-2"
    assert row["الأهمية"] == "High"
    assert "الملحق أ" in row["استراتيجية الاستجابة"]


def test_compliance_status_stays_a_human_decision(tables):
    """
    النموذج يقترح استراتيجية؛ إعلان الالتزام قرار بشري. لو بدأ الجدول
    بـ"نعم" لخرجت مصفوفة تدّعي التزاماً غير محقّق.
    """
    items = [{
        "req_id": f"REQ-{i:03d}", "category": "Technical",
        "requirement_summary": f"متطلب {i}", "criticality": "High",
        "proposed_compliance_strategy": "استراتيجية",
    } for i in range(5)]
    assert set(tables._compliance_to_df(items)["الالتزام"]) == {"بانتظار التحقق"}


def test_mandatory_requirement_is_marked(tables):
    items = [{
        "req_id": "REQ-001", "category": "Technical",
        "requirement_summary": "شرط", "criticality": "High",
        "proposed_compliance_strategy": "خطة", "mandatory": True,
    }]
    assert "⛔" in tables._compliance_to_df(items).iloc[0]["استراتيجية الاستجابة"]


def test_invalid_enums_fall_back(tables):
    items = [{
        "req_id": "", "category": "Nonsense",
        "requirement_summary": "متطلب", "criticality": "Urgent",
        "proposed_compliance_strategy": "",
    }]
    row = tables._compliance_to_df(items).iloc[0]
    assert row["التصنيف"] == "Technical"
    assert row["الأهمية"] == "Medium"
    assert row["المعرّف"] == "REQ-001"      # مُولَّد عند غيابه


def test_compliance_skips_blank_requirements(tables, state):
    df = tables._compliance_to_df([{"req_id": "REQ-001", "requirement_summary": "  "}])
    assert list(df.columns) == state.COMPLIANCE_COLUMNS


def test_compliance_prompt_covers_spec_rules(ae):
    prompt = ae.EXTRACT_PROMPTS["compliance_items"]
    for token in ("REQ-001", "Technical", "Legal", "High", "clause_reference"):
        assert token in prompt


# ─── ترقية الجداول المحفوظة ────────────────────────────────────────────────────


def test_migrate_legacy_compliance_table(state):
    legacy = pd.DataFrame({
        "المتطلب التقني": ["شهادة ISO"],
        "الالتزام": ["نعم"],
        "التبرير / الملاحظة": ["مرفقة في الملحق"],
        "الشهادة المطلوبة": ["ISO 27001"],
    })
    out = state.migrate_compliance_df(legacy)
    assert list(out.columns) == state.COMPLIANCE_COLUMNS
    assert out.iloc[0]["المتطلب"] == "شهادة ISO"
    assert out.iloc[0]["استراتيجية الاستجابة"] == "مرفقة في الملحق"
    # قرار المستخدم السابق يُحترم ولا يُعاد ضبطه
    assert out.iloc[0]["الالتزام"] == "نعم"
    assert out.iloc[0]["الشهادة المطلوبة"] == "ISO 27001"


def test_compliance_migration_is_idempotent(state):
    once = state.migrate_compliance_df(state.DEFAULT_COMPLIANCE_DF.copy())
    twice = state.migrate_compliance_df(once)
    assert list(twice.columns) == state.COMPLIANCE_COLUMNS
    assert len(twice) == len(once)


def test_compliance_migration_handles_garbage(state):
    assert list(state.migrate_compliance_df(None).columns) == state.COMPLIANCE_COLUMNS
    assert list(state.migrate_compliance_df("nope").columns) == state.COMPLIANCE_COLUMNS


def test_default_compliance_matches_columns(state):
    assert list(state.DEFAULT_COMPLIANCE_DF.columns) == state.COMPLIANCE_COLUMNS
