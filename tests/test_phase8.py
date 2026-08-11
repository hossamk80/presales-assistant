"""
اختبارات المرحلة 8 — قرار Go/No-Go مبني على قدرات الشركة لا على المنافسة وحدها.
"""
import pytest


@pytest.fixture()
def ae():
    from utils import ai_engine
    return ai_engine


@pytest.fixture()
def analysis():
    from views import analysis as mod
    return mod


# ─── ملف الشركة كمقطع سياق ─────────────────────────────────────────────────────


def test_company_block_carries_identity_and_experience(fake_streamlit):
    from utils.state import company_block

    fake_streamlit.session_state.update({
        "c_name": "شركة الحلول المتقدمة",
        "c_cr": "1010123456",
        "c_overview": "خبرة 12 عاماً في أنظمة المستشفيات",
    })
    block = company_block()
    assert "شركة الحلول المتقدمة" in block
    assert "1010123456" in block
    assert "12 عاماً" in block


def test_company_block_empty_when_profile_blank(fake_streamlit):
    """الفراغ يجب أن يكون مكشوفاً لا مقطعاً بترويسة بلا محتوى."""
    from utils.state import company_block

    fake_streamlit.session_state.update({"c_name": "", "c_overview": ""})
    assert company_block() == ""


def test_company_block_excludes_contact_noise(fake_streamlit):
    """الهاتف والبريد لا يُثبتان تأهيلاً — حشوهما يزاحم ما يُثبته."""
    from utils.state import company_block

    fake_streamlit.session_state.update({
        "c_name": "شركة", "c_phone": "+966-11-1234567",
        "c_email": "bids@example.com", "c_web": "https://example.com",
    })
    block = company_block()
    assert "1234567" not in block
    assert "bids@example.com" not in block


# ─── التعليمات ─────────────────────────────────────────────────────────────────


def test_gonogo_prompt_compares_against_company_capability(ae):
    prompt = ae.PROMPTS["gonogo"]
    assert "لهذه الشركة تحديداً" in prompt
    assert "فجوات التأهيل" in prompt
    assert "مطابقة قدرات الشركة" in prompt


def test_gonogo_treats_unevidenced_capability_as_missing(ae):
    """
    افتراض امتلاك شهادة لأن الشركة "تبدو مؤهلة" هو ما يُنتج قرار خوض خاطئ.
    """
    prompt = ae.PROMPTS["gonogo"]
    assert "ناقصاً لا متوفراً" in prompt
    assert "غير معلوم" in prompt


def test_gonogo_separates_disqualifying_from_weakening(ae):
    """
    شرط إلزامي غير مستوفى يمنع التأهل؛ نقص تنافسي يخصم درجات فقط. خلطهما
    يُنتج NO-GO على منافسة قابلة للفوز.
    """
    prompt = ae.PROMPTS["gonogo"]
    assert "يمنع التأهل" in prompt
    assert "يُضعف التنافسية" in prompt


def test_gonogo_keeps_the_decision_human(ae):
    """قاعدة ثابتة في المنتج: النموذج يقترح ولا يقرّر."""
    prompt = ae.PROMPTS["gonogo"]
    assert "القرار النهائي بشري" in prompt


def test_gonogo_prompt_still_follows_output_language(ae):
    assert ae.language_instruction("en") in ae.build_prompt("gonogo", "en")


# ─── تجميع السياق ──────────────────────────────────────────────────────────────


def test_qualification_context_gathers_all_four_sources(analysis, fake_streamlit,
                                                        monkeypatch):
    import pandas as pd

    monkeypatch.setattr(analysis.knowledge, "build_context",
                        lambda *a, **k: "[شهادة — ISO 27001] سارية حتى 2027")
    fake_streamlit.session_state.update({
        "c_name": "شركة الحلول المتقدمة",
        "project_context": {"issuing_entity": "وزارة الصحة"},
        "df_boq": pd.DataFrame({"البند": ["جهاز أشعة"]}),
    })

    ctx = analysis._qualification_context()
    assert "شركة الحلول المتقدمة" in ctx
    assert "ISO 27001" in ctx
    assert "وزارة الصحة" in ctx
    assert "جهاز أشعة" in ctx


def test_qualification_query_targets_proof_not_marketing(analysis):
    query = analysis._QUALIFICATION_QUERY
    for token in ("الشهادات", "التصنيف", "المشاريع السابقة"):
        assert token in query


def test_qualification_context_survives_an_empty_workspace(analysis, fake_streamlit,
                                                           monkeypatch):
    monkeypatch.setattr(analysis.knowledge, "build_context", lambda *a, **k: "")
    fake_streamlit.session_state.update({"c_name": "", "project_context": {},
                                         "df_boq": None})
    assert analysis._qualification_context() == ""


def test_qualification_context_has_no_blank_separators(analysis, fake_streamlit,
                                                       monkeypatch):
    """المقاطع الفارغة تُسقط لئلا تتراكم أسطر فاصلة تُشتّت النموذج."""
    monkeypatch.setattr(analysis.knowledge, "build_context", lambda *a, **k: "")
    fake_streamlit.session_state.update({
        "c_name": "شركة", "project_context": {}, "df_boq": None,
    })
    assert "\n\n\n" not in analysis._qualification_context()
