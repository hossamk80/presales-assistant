"""
اختبارات المرحلة 1: تصنيف المرفقات، مخطط الكميات الموسّع، وسياق المشروع.
"""
import pandas as pd
import pytest


@pytest.fixture()
def state():
    from utils import state as mod
    return mod


@pytest.fixture()
def tables():
    from views import tables as mod
    return mod


@pytest.fixture()
def ae():
    from utils import ai_engine
    return ai_engine


# ─── تصنيف المرفقات ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("name,expected", [
    ("BOQ_2026.xlsx", "boq"),
    ("جدول_الكميات.pdf", "boq"),
    ("bill of quantities.csv", "boq"),
    ("prices.xls", "boq"),
    ("الملحق_الفني.pdf", "annex"),
    ("Technical_Annex_A.docx", "annex"),
    ("specifications.pdf", "annex"),
    ("كراسة_الشروط.pdf", "rfp"),
    ("RFP_booklet.pdf", "rfp"),
    ("random_file.pdf", "rfp"),
])
def test_attachment_role_detection(state, name, expected):
    assert state.guess_attachment_role(name) == expected


def test_spreadsheets_default_to_boq(state):
    """جداول البيانات في كراسات اعتماد شبه دائماً جداول كميات."""
    assert state.guess_attachment_role("annex_data.xlsx") == "annex"  # الاسم يغلب الامتداد
    assert state.guess_attachment_role("sheet1.xlsx") == "boq"


def test_role_text_groups_by_role(state, fake_streamlit):
    fake_streamlit.session_state.update({
        "attachment_texts": {"a.pdf": "نص الكراسة", "b.xlsx": "بنود", "c.pdf": "ملحق"},
        "attachment_roles": {"a.pdf": "rfp", "b.xlsx": "boq", "c.pdf": "annex"},
    })
    assert state.role_text("rfp") == "نص الكراسة"
    assert state.role_text("boq") == "بنود"
    assert state.role_text("annex") == "ملحق"
    assert state.role_text("other") == ""


def test_role_text_empty_without_attachments(state, fake_streamlit):
    fake_streamlit.session_state.clear()
    assert state.role_text("rfp") == ""


# ─── مخطط الكميات الموسّع ──────────────────────────────────────────────────────


def test_boq_schema_has_all_nine_fields(ae):
    props = ae.BOQ_SCHEMA["properties"]["items"]["items"]["properties"]
    assert set(props) == {
        "item_number", "category", "item_name", "unit", "description",
        "specifications", "construction_code", "quantity", "mandatory_list_flag",
    }
    assert props["mandatory_list_flag"]["type"] == "BOOLEAN"
    assert props["quantity"]["type"] == "NUMBER"


def test_boq_rows_map_every_field(tables, state):
    items = [{
        "item_number": "1.2",
        "category": "أجهزة",
        "item_name": "خادم تطبيقات",
        "unit": "وحدة",
        "description": "خادم رفوف",
        "specifications": "معالج 32 نواة، ذاكرة 128 جيجابايت",
        "construction_code": "SRV-32-128",
        "quantity": 4,
        "mandatory_list_flag": True,
    }]
    df = tables._boq_to_df(items)
    assert list(df.columns) == state.BOQ_COLUMNS
    row = df.iloc[0]
    assert row["رقم البند"] == "1.2"
    assert row["التصنيف"] == "أجهزة"
    assert row["البند"] == "خادم تطبيقات"
    assert row["المواصفات"].startswith("معالج")
    assert row["كود البناء"] == "SRV-32-128"
    assert row["الكمية"] == 4
    assert row["القائمة الإلزامية"] is True or bool(row["القائمة الإلزامية"])


def test_boq_unit_is_preserved_verbatim(tables):
    """
    الوحدة لا تُجبَر على قائمة مغلقة — إجبارها يُفقد معلومة لازمة للتسعير.
    """
    items = [{"item_name": "خدمة", "unit": "مقطوعية", "quantity": 1,
              "mandatory_list_flag": False}]
    assert tables._boq_to_df(items).iloc[0]["الوحدة"] == "مقطوعية"


def test_boq_item_number_falls_back_to_index(tables):
    items = [
        {"item_name": "أ", "unit": "وحدة", "quantity": 1, "mandatory_list_flag": False},
        {"item_name": "ب", "unit": "وحدة", "quantity": 1, "mandatory_list_flag": False},
    ]
    df = tables._boq_to_df(items)
    assert list(df["رقم البند"]) == ["1", "2"]


def test_boq_handles_bad_quantity(tables):
    items = [
        {"item_name": "أ", "unit": "وحدة", "quantity": "abc", "mandatory_list_flag": False},
        {"item_name": "ب", "unit": "وحدة", "quantity": None, "mandatory_list_flag": False},
        {"item_name": "ج", "unit": "وحدة", "quantity": "12", "mandatory_list_flag": False},
    ]
    df = tables._boq_to_df(items)
    assert list(df["الكمية"]) == [1, 1, 12]


def test_boq_flag_defaults_false_when_absent(tables):
    items = [{"item_name": "أ", "unit": "وحدة", "quantity": 1}]
    assert bool(tables._boq_to_df(items).iloc[0]["القائمة الإلزامية"]) is False


def test_boq_skips_unnamed_items(tables, state):
    items = [{"item_name": "  ", "unit": "وحدة", "quantity": 1, "mandatory_list_flag": False}]
    df = tables._boq_to_df(items)
    assert list(df.columns) == state.BOQ_COLUMNS


# ─── ترقية الجداول المحفوظة ────────────────────────────────────────────────────


def test_migrate_legacy_boq_table(state):
    """
    منافسات محفوظة قبل التوسيع تحمل خمسة أعمدة. بدون الترقية يفشل محرر
    البيانات على أعمدة لا يجدها وتضيع بيانات المستخدم.
    """
    legacy = pd.DataFrame({
        "البند": ["ترخيص"],
        "الوصف": ["سنوي"],
        "الكمية": [50],
        "الوحدة": ["ترخيص"],
        "ملاحظات": ["يشمل الدعم"],
    })
    out = state.migrate_boq_df(legacy)
    assert list(out.columns) == state.BOQ_COLUMNS
    assert out.iloc[0]["البند"] == "ترخيص"
    assert out.iloc[0]["الكمية"] == 50
    # "ملاحظات" القديمة تنتقل إلى "المواصفات"
    assert out.iloc[0]["المواصفات"] == "يشمل الدعم"
    assert bool(out.iloc[0]["القائمة الإلزامية"]) is False


def test_migrate_is_idempotent(state):
    once = state.migrate_boq_df(state.DEFAULT_BOQ_DF.copy())
    twice = state.migrate_boq_df(once)
    assert list(twice.columns) == state.BOQ_COLUMNS
    assert len(twice) == len(once)


def test_migrate_handles_none_and_garbage(state):
    assert list(state.migrate_boq_df(None).columns) == state.BOQ_COLUMNS
    assert list(state.migrate_boq_df("not a frame").columns) == state.BOQ_COLUMNS


def test_default_boq_matches_columns(state):
    assert list(state.DEFAULT_BOQ_DF.columns) == state.BOQ_COLUMNS


# ─── سياق المشروع ──────────────────────────────────────────────────────────────


def test_project_context_schema_matches_spec(ae):
    props = ae.PROJECT_CONTEXT_SCHEMA["properties"]
    assert set(props) == {
        "project_title", "issuing_entity", "submission_deadline", "scope_summary",
        "key_deliverables", "technical_constraints", "contractual_penalties",
        "required_certifications", "local_content_requirements",
    }
    for key in ("key_deliverables", "technical_constraints",
                "contractual_penalties", "required_certifications"):
        assert props[key]["type"] == "ARRAY"
    assert set(ae.PROJECT_CONTEXT_SCHEMA["required"]) == set(props)


def test_project_context_prompt_exists(ae):
    assert "project_context" in ae.EXTRACT_PROMPTS
    assert "المحتوى المحلي" in ae.EXTRACT_PROMPTS["project_context"]


def test_boq_prompt_mentions_mandatory_list(ae):
    prompt = ae.EXTRACT_PROMPTS["boq_items"]
    assert "القائمة الإلزامية" in prompt
    assert "mandatory_list_flag" in prompt


def test_project_context_block_renders(fake_streamlit):
    from views import doc_builder

    fake_streamlit.session_state["project_context"] = {
        "project_title": "بوابة إلكترونية",
        "issuing_entity": "وزارة الاختبار",
        "submission_deadline": "2026-09-01",
        "scope_summary": "تطوير بوابة",
        "key_deliverables": ["تحليل", "تنفيذ"],
        "technical_constraints": [],
        "contractual_penalties": ["غرامة تأخير 1%"],
        "required_certifications": ["ISO 27001"],
        "local_content_requirements": "حد أدنى 40%",
    }
    block = doc_builder._project_context_block()
    assert "وزارة الاختبار" in block
    assert "تحليل · تنفيذ" in block
    assert "حد أدنى 40%" in block
    # الحقول الفارغة لا تُحقن كسطور فارغة
    assert "القيود الفنية" not in block


def test_project_context_block_empty_without_context(fake_streamlit):
    from views import doc_builder

    fake_streamlit.session_state["project_context"] = {}
    assert doc_builder._project_context_block() == ""
