"""
اختبارات المرحلة 3 (كتابة الأقسام والمساعد الجانبي) والمرحلة 4 (تقييم الوكلاء).
"""
import pytest


@pytest.fixture()
def ae():
    from utils import ai_engine
    return ai_engine


@pytest.fixture()
def builder():
    from views import doc_builder as mod
    return mod


@pytest.fixture()
def review():
    from views import review as mod
    return mod


# ─── 3.1 كاتب الأقسام ──────────────────────────────────────────────────────────


def test_section_prompt_has_all_spec_fields(ae):
    template = ae.PROMPTS["section"]
    for field in ("{title}", "{purpose}", "{guidance}", "{user_steering}",
                  "{company_overview}", "{language_instruction}"):
        assert field in template, f"حقل ناقص في قالب القسم: {field}"


def test_section_prompt_forbids_pricing(ae):
    """
    الفصل الصارم بين الفني والمالي — بند صريح في مواصفات المرحلة 3.
    """
    template = ae.PROMPTS["section"]
    assert "لا تذكر أي تسعير" in template


def test_section_prompt_covers_writing_criteria(ae):
    template = ae.PROMPTS["section"]
    for token in ("النبرة", "عمق المحتوى", "البنية", "السياق المحلي", "المحتوى المحلي"):
        assert token in template


def test_section_prompt_pins_the_arabic_register(ae):
    """
    "لغة رسمية" وحدها لا تمنع العامية ولا الترجمة الحرفية عن الإنجليزية،
    وكلاهما يُضعف العرض أمام لجنة عربية.
    """
    template = ae.PROMPTS["section"]
    assert "الفصحى" in template
    assert "عامية" in template


def test_section_prompt_builds(ae):
    out = ae.build_prompt(
        "section", "ar",
        title="المنهجية", purpose="شرح النهج", guidance="- نقطة",
        company_overview="شركة", eval_weights="40/60",
        compliance_summary="شروط", user_steering="ركّز على التكامل",
    )
    assert "ركّز على التكامل" in out
    assert "{" not in out.replace("{ }", "")


def test_steering_is_passed_into_section_prompt(builder, fake_streamlit):
    fake_streamlit.session_state.update({
        "output_language": "ar",
        "steer_methodology": "أبرز خبرتنا في القطاع الصحي",
    })
    sec = {"key": "methodology", "title": "المنهجية", "rationale": "غرض",
           "key_points": ["نقطة أولى"]}
    prompt = builder._section_prompt(sec)
    assert "أبرز خبرتنا في القطاع الصحي" in prompt
    assert "نقطة أولى" in prompt


def test_missing_steering_does_not_break_prompt(builder, fake_streamlit):
    fake_streamlit.session_state["output_language"] = "ar"
    sec = {"key": "x", "title": "قسم", "guidance": "توجيه"}
    prompt = builder._section_prompt(sec)
    assert "لا توجد توجيهات إضافية" in prompt


# ─── 3.2 المساعد الجانبي ───────────────────────────────────────────────────────


def test_refine_prompt_has_spec_fields(ae):
    template = ae.PROMPTS["refine"]
    assert "{content}" in template and "{edit_request}" in template


def test_refine_prompt_bans_preamble_and_pricing(ae):
    template = ae.PROMPTS["refine"]
    assert "إليك النسخة" in template          # يمنعها صراحةً
    assert "تسعير" in template


def test_refine_prompt_builds(ae):
    out = ae.build_prompt("refine", "ar", content="النص الحالي",
                          edit_request="اجعله أكثر إيجازاً")
    assert "النص الحالي" in out
    assert "اجعله أكثر إيجازاً" in out


def test_refinement_stores_undo_and_replaces_text(builder, fake_streamlit, monkeypatch):
    monkeypatch.setattr(builder, "ai_generate", lambda *a, **k: "النص المنقّح")
    fake_streamlit.session_state.update({
        "output_language": "ar",
        "sec_methodology": "النص الأصلي",
    })
    builder._apply_refinement({"key": "methodology"}, "أوجز", "Gemini 3.6 Flash")

    assert fake_streamlit.session_state["sec_methodology"] == "النص المنقّح"
    assert fake_streamlit.session_state["_undo_sec_methodology"] == "النص الأصلي"


def test_failed_refinement_leaves_text_untouched(builder, fake_streamlit, monkeypatch):
    """فشل الاستدعاء يجب ألا يمسح عمل المستخدم."""
    monkeypatch.setattr(builder, "ai_generate", lambda *a, **k: None)
    fake_streamlit.session_state.update({
        "output_language": "ar",
        "sec_methodology": "النص الأصلي",
    })
    builder._apply_refinement({"key": "methodology"}, "أوجز", "Gemini 3.6 Flash")

    assert fake_streamlit.session_state["sec_methodology"] == "النص الأصلي"
    assert "_undo_sec_methodology" not in fake_streamlit.session_state


def test_refinement_receives_the_tender_context(builder, fake_streamlit, monkeypatch):
    """
    بلا سياق المنافسة كان "أضف مؤشرات أداء" يُنتج مؤشرات عامة بدل مستويات
    الخدمة المطلوبة في هذه الكراسة.
    """
    seen = {}

    def fake_generate(prompt, **kwargs):
        seen.update(kwargs)
        return "نص منقّح"

    monkeypatch.setattr(builder, "ai_generate", fake_generate)
    monkeypatch.setattr(builder, "_kb_context", lambda sec: "")
    fake_streamlit.session_state.update({
        "output_language": "ar",
        "sec_methodology": "نص",
        "rfp_raw_text": "الكراسة تشترط زمن استجابة 4 ساعات",
        "project_context": {"issuing_entity": "وزارة الصحة"},
    })

    builder._apply_refinement({"key": "methodology"}, "أضف مؤشرات أداء", "Gemini 3.6 Flash")

    assert "زمن استجابة 4 ساعات" in seen["rfp_context"]
    assert "وزارة الصحة" in seen["extra_context"]


# ─── 3.2ب سؤال المساعد ─────────────────────────────────────────────────────────


def test_ask_prompt_forbids_rewriting_the_section(ae):
    template = ae.PROMPTS["ask"]
    assert "{question}" in template and "{content}" in template
    assert "لا تُعِد كتابة القسم" in template
    assert "لا تُخمّن" in template


def test_question_never_touches_the_section_text(builder, fake_streamlit, monkeypatch):
    """
    السؤال المكتوب في خانة التعديل كان يُعامَل أمراً بالتحرير فيُتلف القسم.
    """
    monkeypatch.setattr(builder, "ai_generate", lambda *a, **k: "نعم، غُطّي في الفقرة الثانية.")
    monkeypatch.setattr(builder, "_kb_context", lambda sec: "")
    fake_streamlit.session_state.update({
        "output_language": "ar",
        "sec_methodology": "النص الأصلي",
    })

    builder._answer_question({"key": "methodology"}, "هل غطّينا شرط السعودة؟",
                             "Gemini 3.6 Flash")

    assert fake_streamlit.session_state["sec_methodology"] == "النص الأصلي"
    assert "_undo_sec_methodology" not in fake_streamlit.session_state
    thread = fake_streamlit.session_state["_qa_methodology"]
    assert thread == [("هل غطّينا شرط السعودة؟", "نعم، غُطّي في الفقرة الثانية.")]


def test_failed_question_records_nothing(builder, fake_streamlit, monkeypatch):
    monkeypatch.setattr(builder, "ai_generate", lambda *a, **k: None)
    monkeypatch.setattr(builder, "_kb_context", lambda sec: "")
    fake_streamlit.session_state.update({"output_language": "ar", "sec_x": "نص"})

    builder._answer_question({"key": "x"}, "سؤال", "Gemini 3.6 Flash")

    assert "_qa_x" not in fake_streamlit.session_state


def test_qa_thread_drops_the_oldest_exchange(builder, fake_streamlit, monkeypatch):
    monkeypatch.setattr(builder, "ai_generate", lambda *a, **k: "جواب")
    monkeypatch.setattr(builder, "_kb_context", lambda sec: "")
    fake_streamlit.session_state.update({"output_language": "ar", "sec_x": "نص"})

    for i in range(builder.QA_THREAD_LIMIT + 3):
        builder._answer_question({"key": "x"}, f"سؤال {i}", "Gemini 3.6 Flash")

    thread = fake_streamlit.session_state["_qa_x"]
    assert len(thread) == builder.QA_THREAD_LIMIT
    assert thread[0][0] == "سؤال 3"


def test_discussion_is_not_saved_with_the_tender(fake_streamlit):
    """النقاش وسيلة لا مُخرَج — المحفوظ نص القسم وتوجيهه فقط."""
    from utils.state import get_state_snapshot

    fake_streamlit.session_state.update({
        "_qa_methodology": [("سؤال", "جواب")],
        "sec_ai_methodology": "نص",
        "steer_methodology": "توجيه",
    })
    dynamic = get_state_snapshot().get("_dynamic_sections", {})
    assert "sec_ai_methodology" in dynamic
    assert "steer_methodology" in dynamic
    assert "_qa_methodology" not in dynamic


# ─── 4 تقييم الوكلاء ───────────────────────────────────────────────────────────


def test_review_schema_carries_score_and_recommendations(ae):
    props = ae.REVIEW_SCHEMA["properties"]
    assert props["readiness_score"]["type"] == "INTEGER"
    assert props["recommendations"]["type"] == "ARRAY"
    assert props["strengths"]["type"] == "ARRAY"
    assert "assessment" in props
    assert set(ae.REVIEW_SCHEMA["required"]) == {
        "readiness_score", "assessment", "strengths", "recommendations", "findings",
    }


def test_three_agents_defined(ae):
    assert set(ae.REVIEW_LENSES) == {"technical", "commercial", "legal"}


@pytest.mark.parametrize("value,expected", [
    (85, 85), (0, 0), (100, 100),
    (150, 100), (-5, 0),          # خارج المدى يُقصّ
    ("72", 72), (None, 0), ("abc", 0),
])
def test_score_clamping(review, value, expected):
    assert review._clamp_score(value) == expected


def test_scalar_fields_survive_chunked_merge(ae, monkeypatch):
    """
    درجة الجاهزية حقل قياسي لا قائمة. دمج الأجزاء كان يُرجع القائمة وحدها
    فتضيع الدرجة على الكراسات الكبيرة.
    """
    def fake_call_json(prompt, model_id, schema, on_progress=None):
        return {"readiness_score": 71, "assessment": "جيد",
                "recommendations": ["توصية"], "findings": [{"issue": "x"}]}

    monkeypatch.setattr(ae, "_call_json", fake_call_json)
    big = "ح" * (ae.CONTEXT_CHAR_BUDGET * 2 + 10)
    out = ae.ai_generate_json("p", ae.REVIEW_SCHEMA, rfp_context=big,
                              merge_key="findings")
    assert out["readiness_score"] == 71
    assert out["assessment"] == "جيد"
    assert len(out["findings"]) == 3


def test_review_lens_prompts_are_distinct(ae):
    prompts = [lens["prompt"] for lens in ae.REVIEW_LENSES.values()]
    assert len(set(prompts)) == 3


# ─── 4.1 لجنة المراجعة ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("lens_key,tokens", [
    ("technical", ("الجدوى الفنية", "المنهجية", "الجدول", "الفريق", "SLA")),
    ("commercial", ("جدول الكميات", "التسعير", "مخاطر الكلفة", "الدفعات",
                    "التوريد والتركيب")),
    ("legal", ("نظام المنافسات والمشتريات", "المحتوى المحلي",
               "القائمة الإلزامية", "الضمان الابتدائي", "الضمان النهائي",
               "الكفالة", "الغرامات")),
])
def test_each_agent_covers_its_domain(ae, lens_key, tokens):
    prompt = ae.REVIEW_LENSES[lens_key]["prompt"]
    for token in tokens:
        assert token in prompt, f"{lens_key} لا يغطي: {token}"


def test_legal_agent_separates_the_three_guarantees(ae):
    """
    ثلاثة أشياء مختلفة يخلطها الاختصار: الضمان الابتدائي (مع العرض)، والنهائي
    (عند الترسية)، وفترة الكفالة على المُورَّد. كل واحد غيابه له كلفة مختلفة.
    """
    prompt = ae.REVIEW_LENSES["legal"]["prompt"]
    assert "الضمان الابتدائي" in prompt
    assert "الضمان النهائي" in prompt
    assert "فترة الضمان والكفالة" in prompt


def test_commercial_agent_enforces_financial_isolation(ae):
    """
    وجود تسعير داخل العرض الفني سبب استبعاد لا ملاحظة تحسين — يجب أن يطلب
    البرومبت تسجيله ملاحظة حرجة لا مجرد التنبيه إليه.
    """
    prompt = ae.REVIEW_LENSES["commercial"]["prompt"]
    assert "حرجة" in prompt
    assert "الفصل المالي" in prompt


def test_every_agent_asks_for_the_full_panel_output(ae):
    for key, lens in ae.REVIEW_LENSES.items():
        for field in ("readiness_score", "strengths", "recommendations", "findings"):
            assert field in lens["prompt"], f"{key} لا يطلب {field}"


def test_overall_readiness_is_the_weakest_agent(review):
    scores = {"technical": {"score": 92}, "commercial": {"score": 85},
              "legal": {"score": 95}}
    # المتوسط 90.7 — يخفي أن الزاوية التجارية هي الحاكمة
    assert review._overall_readiness(scores) == 85


def test_overall_readiness_with_no_scores(review):
    assert review._overall_readiness({}) == 0


def test_panel_uses_fused_project_context(fake_streamlit):
    """
    سياق المشروع الموحّد يُبنى مرة واحدة ويُشارك بين كاتب الأقسام واللجنة —
    نسخة ثانية منه في review.py كانت ستتباعد عن الأصل.
    """
    from utils.state import project_context_block
    from views import doc_builder, review as review_mod

    assert doc_builder._project_context_block is project_context_block
    assert review_mod.project_context_block is project_context_block

    fake_streamlit.session_state["project_context"] = {
        "issuing_entity": "وزارة الصحة",
        "contractual_penalties": ["1% لكل أسبوع تأخير"],
    }
    block = project_context_block()
    assert "وزارة الصحة" in block
    assert "1% لكل أسبوع تأخير" in block


def test_project_context_block_empty_when_unfused(fake_streamlit):
    fake_streamlit.session_state["project_context"] = {}
    from utils.state import project_context_block
    assert project_context_block() == ""


def test_strengths_are_collected_per_agent(review, fake_streamlit, monkeypatch):
    monkeypatch.setattr(review, "ai_generate_json", lambda *a, **k: {
        "readiness_score": 88,
        "assessment": "قوي",
        "strengths": ["منهجية مفصّلة", "  "],      # الفارغ يُسقَط
        "recommendations": ["أضف مؤشرات"],
        "findings": [],
    })
    fake_streamlit.session_state.update({"output_language": "ar", "review_scores": {}})
    sections = [{"key": "methodology", "title": "المنهجية", "content": "نص"}]

    review._run_lens("technical", sections, "Gemini 3.6 Flash", lambda m: None)

    agent = fake_streamlit.session_state["review_scores"]["technical"]
    assert agent["score"] == 88
    assert agent["strengths"] == ["منهجية مفصّلة"]


def test_agent_panel_survives_scores_saved_before_strengths_existed(review, fake_streamlit):
    """منافسة محفوظة قبل إضافة نقاط القوة يجب ألا تُسقط الصفحة بـ KeyError."""
    fake_streamlit.session_state["review_scores"] = {
        "technical": {"label": "فنية", "icon": "🛠️", "score": 80,
                      "assessment": "جيد", "recommendations": []},
    }
    review._render_agent_scores([])          # لا استثناء
