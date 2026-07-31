"""اختبارات محرك الذكاء الاصطناعي: النماذج، التقسيم، اللغة، ومخرجات JSON."""
import pytest


@pytest.fixture()
def ae():
    from utils import ai_engine
    return ai_engine


def test_known_models_resolve(ae):
    for display, model_id in ae.MODELS.items():
        assert ae.resolve_model(display) == model_id


def test_unknown_or_legacy_model_falls_back(ae):
    """أسماء نماذج قديمة محفوظة في مشاريع سابقة يجب ألا تُسقط التوليد."""
    assert ae.resolve_model("Gemini 1.5 Flash") == ae.MODELS[ae.DEFAULT_MODEL]
    assert ae.resolve_model("") == ae.MODELS[ae.DEFAULT_MODEL]


def test_split_is_lossless_and_bounded(ae):
    text = ("فقرة اختبار طويلة نسبياً لقياس التقسيم. " * 20 + "\n\n") * 60
    for size in (5000, 20000, len(text) + 10):
        chunks = ae._split_into_chunks(text, size)
        assert all(len(c) <= size for c in chunks)
        normalized = "".join(c.replace(" ", "").replace("\n", "") for c in chunks)
        assert normalized == text.replace(" ", "").replace("\n", "")


def test_split_returns_single_chunk_when_within_budget(ae):
    assert ae._split_into_chunks("قصير", 100) == ["قصير"]


def test_strip_code_fence(ae):
    assert ae._strip_code_fence('```json\n{"a":1}\n```') == '{"a":1}'
    assert ae._strip_code_fence("```\n{}\n```") == "{}"
    assert ae._strip_code_fence('{"a":2}') == '{"a":2}'


def test_language_instructions_distinct(ae):
    assert ae.is_rtl("ar") is True
    assert ae.is_rtl("en") is False
    assert ae.language_instruction("ar") != ae.language_instruction("en")
    # لغة غير معروفة ترجع للافتراضي بدل الانهيار
    assert ae.language_instruction("xx") == ae.language_instruction(ae.DEFAULT_LANGUAGE)
    assert ae.is_rtl("xx") is True


def test_every_prompt_template_accepts_language(ae):
    """
    كل قالب يحمل {language_instruction}. لو أُضيف قالب بلا هذا الحقل فلن
    تتبدّل لغته مع الإعداد — هذا الاختبار يكشف ذلك.
    """
    for key, template in ae.PROMPTS.items():
        assert "{language_instruction}" in template, f"القالب {key} لا يدعم اللغة"


def test_build_prompt_injects_language(ae):
    out = ae.build_prompt("gonogo", "en")
    assert ae.language_instruction("en") in out
    assert "{language_instruction}" not in out


def test_estimate_tokens_monotonic(ae):
    assert ae.estimate_tokens("") == 0
    assert ae.estimate_tokens("ا" * 100) < ae.estimate_tokens("ا" * 200)


def test_json_merge_concatenates_across_chunks(ae, monkeypatch):
    calls = {"n": 0}

    def fake_call_json(prompt, model_id, schema):
        calls["n"] += 1
        return {"requirements": [{"requirement": f"req-{calls['n']}"}]}

    monkeypatch.setattr(ae, "_call_json", fake_call_json)

    big = "ح" * (ae.CONTEXT_CHAR_BUDGET * 3 + 500)
    result = ae.ai_generate_json(
        "p", ae.COMPLIANCE_SCHEMA, rfp_context=big, merge_key="requirements"
    )
    assert calls["n"] == 4
    assert len(result["requirements"]) == 4


def test_json_single_call_when_context_fits(ae, monkeypatch):
    calls = {"n": 0}

    def fake_call_json(prompt, model_id, schema):
        calls["n"] += 1
        return {"requirements": []}

    monkeypatch.setattr(ae, "_call_json", fake_call_json)
    ae.ai_generate_json("p", ae.COMPLIANCE_SCHEMA, rfp_context="نص قصير",
                        merge_key="requirements")
    assert calls["n"] == 1


def test_generate_without_key_reports_error(ae, fake_streamlit):
    fake_streamlit.session_state.clear()
    assert ae.ai_generate("أي تعليمات") is None
    assert any(kind == "error" for kind, _ in fake_streamlit.messages)


def test_schemas_are_well_formed(ae):
    for schema in (ae.COMPLIANCE_SCHEMA, ae.BOQ_SCHEMA,
                   ae.OUTLINE_SCHEMA, ae.REVIEW_SCHEMA):
        assert schema["type"] == "OBJECT"
        assert schema["properties"]
        for field in schema["required"]:
            assert field in schema["properties"]


def test_review_lenses_complete(ae):
    assert set(ae.REVIEW_LENSES) == {"technical", "commercial", "legal"}
    for lens in ae.REVIEW_LENSES.values():
        assert lens["label"] and lens["icon"] and lens["prompt"]
