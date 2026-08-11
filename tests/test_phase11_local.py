"""
اختبارات المعالجة المحلية — ما يُحسب في النظام لا يُرسَل إلى النموذج.

تنظيف الكراسة · قراءة جدول الكميات من الملف · الاسترجاع اللفظي · سجل التوفير.
مصدرها فرع التحليل الموازي، نُقلت فوق تنفيذ المرحلة 11 المدموج.
"""
import pandas as pd
import pytest

# ══════════════════════════════════════════════════════════════════════════════
#  تنظيف نص الكراسة
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def tp():
    from utils import textprep
    return textprep


# متن يملأ الصفحة كما في كراسة حقيقية: الزخرفة نسبة صغيرة منها لا أغلبها.
_BODY_FILLER = [
    "يلتزم المورد بتوريد وتركيب وتشغيل جميع الأجهزة والمعدات المطلوبة وفق "
    "المواصفات الفنية المرفقة وبما يحقق أهداف الجهة من هذا المشروع.",
    "تشمل الأعمال أعمال التمديدات والتوصيلات والاختبارات والفحوصات اللازمة "
    "قبل التسليم الابتدائي وحتى التسليم النهائي للمشروع.",
    "يقدّم المورد خطة عمل تفصيلية معتمدة تبيّن المراحل والتسليمات ومسؤوليات "
    "كل طرف خلال فترة التنفيذ المتفق عليها في العقد.",
]


def _paged(body_lines, pages=6) -> str:
    """
    كراسة مصطنعة بترويسة وتذييل ورقم صفحة في كل صفحة.

    المتن أكبر من الزخرفة عمداً — كراسة حقيقية كذلك، وسقف الأمان في التنظيف
    يتراجع عن أي نص تكون زخرفته أغلبه.
    """
    out = []
    for page in range(1, pages + 1):
        out.append("وزارة الصحة — الإدارة العامة للمشتريات")
        out.append("كراسة الشروط والمواصفات رقم 4400012345")
        out.extend(body_lines)
        out.extend(f"{page}-{i} {line}" for i, line in enumerate(_BODY_FILLER, start=1))
        out.append(f"صفحة {page} من {pages}")
    return "\n".join(out)


def test_repeated_headers_are_removed(tp):
    text = _paged(["بند فريد رقم كذا يصف متطلباً حقيقياً في هذه الصفحة."])
    cleaned, stats = tp.clean(text)
    assert "وزارة الصحة" not in cleaned
    assert stats["repeated_lines"] > 0
    assert stats["saved"] > 0


def test_page_numbers_are_removed(tp):
    cleaned, stats = tp.clean(_paged(["نص المتطلب هنا وهو مختلف في كل صفحة تقريباً."]))
    assert "صفحة 3 من 6" not in cleaned
    assert stats["page_lines"] > 0


def test_real_content_survives_cleanup(tp):
    """
    القاعدة الحاكمة: بند يسقط في التنظيف يعني متطلباً لا يراه النموذج فلا
    يظهر في المصفوفة فلا يُغطّى في العرض.
    """
    lines = [
        "5-2 يجب على المورد تقديم شهادة الأيزو 27001 سارية المفعول.",
        "5-3 مدة تنفيذ المشروع اثنا عشر شهراً من تاريخ الترسية.",
        "5-4 نسبة المحتوى المحلي المطلوبة لا تقل عن 30%.",
    ]
    cleaned, _ = tp.clean(_paged(lines))
    for line in lines:
        assert line in cleaned, f"سقط بند حقيقي: {line}"


def test_table_of_contents_leaders_are_removed(tp):
    text = "\n".join([
        "المحتويات",
        "المقدمة ................................. 3",
        "الشروط العامة .......................... 12",
        "5-1 متطلب حقيقي لا يُحذف.",
        *_BODY_FILLER,
    ])
    cleaned, stats = tp.clean(text)
    assert "المقدمة ....." not in cleaned
    assert stats["toc_lines"] == 2
    assert "5-1 متطلب حقيقي لا يُحذف." in cleaned


def test_duplicate_blocks_are_dropped(tp):
    block = ("هذه فقرة طويلة تصف شروط الضمان النهائي وتفاصيله ومدته وطريقة "
             "تقديمه وما يترتب على الإخلال به من جزاءات تعاقدية محددة، "
             "وتفصّل آلية الإفراج عنه وشروط مصادرته وحالات تمديده، وتبيّن "
             "الجهة المستفيدة منه وصيغته البنكية المعتمدة لدى الجهة الحكومية.")
    other = "\n\n".join(f"{i} {line}" for i, line in enumerate(_BODY_FILLER * 4))
    cleaned, stats = tp.clean(f"{block}\n\n{other}\n\n{block}")
    assert stats["duplicate_blocks"] == 1
    assert cleaned.count("شروط الضمان النهائي") == 1


def test_clauses_differing_only_by_number_are_not_duplicates(tp):
    """
    انحدار: كشف الفقرات المكرّرة كان يُوحّد الأرقام قبل المقارنة، فبندان لا
    يختلفان إلا في رقمهما يصيران بصمة واحدة ويُحذف أحدهما — متطلب كامل يختفي.
    """
    shared = ("يوفّر المورد كوادر فنية مؤهلة ومعتمدة لتشغيل النظام على مدار "
              "الساعة طوال أيام الأسبوع، مع خطة إحلال معتمدة وبديل مؤهل لكل "
              "دور حرج، وتقارير دورية عن الأداء والالتزام بمستويات الخدمة.")
    text = f"5-1 {shared}\n\n5-2 {shared}\n\n5-3 {shared}"
    cleaned, stats = tp.clean(text)

    assert stats["duplicate_blocks"] == 0
    for number in ("5-1", "5-2", "5-3"):
        assert number in cleaned, f"سقط البند {number}"


def test_clause_lines_are_never_treated_as_furniture(tp):
    """سطر يحمل رقم بند محتوى بالتعريف مهما تكرّر — الترويسات بلا أرقام بنود."""
    text = "\n".join(["4-1 يقدّم المورد تقريراً شهرياً."] * 8
                     + ["ترويسة الجهة المصدِرة"] * 8
                     + _BODY_FILLER * 3)
    cleaned, stats = tp.clean(text)
    assert "4-1 يقدّم المورد تقريراً شهرياً." in cleaned
    assert "ترويسة الجهة المصدِرة" not in cleaned


def test_short_repeats_in_tables_survive(tp):
    """«نعم» و«لا ينطبق» تتكرّر مشروعةً في الجداول ولا تُحذف كفقرات مكرّرة."""
    text = "\n\n".join(["نعم"] * 5)
    cleaned, stats = tp.clean(text)
    assert stats["duplicate_blocks"] == 0


def test_excessive_removal_reverts_to_original(tp):
    """
    سقف أمان: حذف مفرط يعني أن الكشف أخطأ. نُعيد الأصل بدل المخاطرة بمتطلب.
    """
    text = "\n".join(["سطر مكرّر تماماً"] * 40)
    cleaned, stats = tp.clean(text)
    assert stats["reverted"] is True
    assert cleaned == text
    assert stats["saved"] == 0


def test_empty_text_is_safe(tp):
    cleaned, stats = tp.clean("")
    assert cleaned == "" and stats["saved"] == 0
    assert tp.clean(None)[0] == ""


def test_identical_attachments_are_deduped(tp):
    texts = {
        "ملحق.pdf": "نص الملحق الفني",
        "ملحق-نسخة.pdf": "نص الملحق الفني",
        "كراسة.pdf": "نص الكراسة",
    }
    kept, dropped = tp.dedupe_attachments(texts)
    assert len(kept) == 2 and len(dropped) == 1
    assert "كراسة.pdf" in kept


def test_dedupe_keeps_distinct_files(tp):
    texts = {"a.pdf": "نص أول", "b.pdf": "نص ثانٍ"}
    kept, dropped = tp.dedupe_attachments(texts)
    assert len(kept) == 2 and not dropped


# ══════════════════════════════════════════════════════════════════════════════
#  قراءة جدول الكميات من الملف — بلا نموذج
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def bp():
    from utils import boq_parser
    return boq_parser


def test_arabic_headers_are_matched(bp):
    assert bp.match_column("الكمية") == "الكمية"
    assert bp.match_column("وحدة القياس") == "الوحدة"
    assert bp.match_column("المواصفات الفنية") == "المواصفات"
    assert bp.match_column("رقم البند") == "رقم البند"


def test_english_headers_are_matched(bp):
    assert bp.match_column("Quantity") == "الكمية"
    assert bp.match_column("Unit") == "الوحدة"
    assert bp.match_column("Item Description") in ("البند", "الوصف")


def test_price_columns_are_never_matched(bp):
    """
    قاعدة منتج ثابتة: جدول الكميات هنا يخدم العرض الفني. «سعر الوحدة» يحوي
    «الوحدة» فتلتقطه المطابقة الجزئية لولا الاستثناء الصريح.
    """
    for header in ("سعر الوحدة", "الإجمالي", "Unit Price", "Total Amount", "قيمة البند"):
        assert bp.is_price_column(header), header
        assert bp.match_column(header) is None, header


def test_a_clean_sheet_parses_without_ai(bp):
    frame = pd.DataFrame({
        "رقم البند": [1, 2],
        "البند": ["خادم", "مفتاح شبكة"],
        "الوحدة": ["عدد", "عدد"],
        "الكمية": [4, 12],
        "المواصفات": ["64GB RAM", "48 منفذ"],
        "سعر الوحدة": [1000, 500],
    })
    parsed, report = bp.parse_frame(frame)
    assert parsed is not None
    assert report["rows"] == 2
    assert "سعر الوحدة" in report["ignored_price"]
    assert "سعر الوحدة" not in parsed.columns
    assert float(parsed.iloc[1]["الكمية"]) == 12.0


def test_header_below_a_title_block_is_found(bp):
    """ملفات الكميات تبدأ بشعار الجهة واسم المنافسة قبل الجدول."""
    frame = pd.DataFrame([
        ["وزارة الصحة", None, None, None],
        ["جدول الكميات", None, None, None],
        [None, None, None, None],
        ["رقم البند", "البند", "الوحدة", "الكمية"],
        [1, "خادم", "عدد", 4],
        [2, "شاشة", "عدد", 8],
    ])
    parsed, report = bp.parse_frame(frame)
    assert parsed is not None and report["rows"] == 2


def test_total_rows_are_dropped(bp):
    frame = pd.DataFrame({
        "البند": ["خادم", "شاشة", "الإجمالي"],
        "الكمية": [2, 3, 5],
        "الوحدة": ["عدد", "عدد", ""],
    })
    parsed, _ = bp.parse_frame(frame)
    assert len(parsed) == 2
    assert "الإجمالي" not in list(parsed["البند"])


def test_unstructured_sheet_falls_back(bp):
    """الفشل هنا رجوع إلى مسار النموذج لا خسارة."""
    frame = pd.DataFrame({"أ": ["نص حر"], "ب": ["نص آخر"]})
    parsed, report = bp.parse_frame(frame)
    assert parsed is None
    assert report["reason"] in ("no_header", "missing_essential", "low_confidence")


def test_sheet_without_quantity_is_rejected(bp):
    """جدول كميات بلا كمية ليس جدول كميات."""
    frame = pd.DataFrame({"البند": ["خادم"], "الوصف": ["وصف"], "الوحدة": ["عدد"]})
    parsed, report = bp.parse_frame(frame)
    assert parsed is None and report["reason"] == "missing_essential"


def test_arabic_digits_in_quantity(bp):
    frame = pd.DataFrame({"البند": ["خادم"], "الكمية": ["٤"], "الوحدة": ["عدد"]})
    parsed, _ = bp.parse_frame(frame)
    assert float(parsed.iloc[0]["الكمية"]) == 4.0


def test_parsed_columns_match_the_schema(bp):
    from utils.state import BOQ_COLUMNS

    frame = pd.DataFrame({"البند": ["خادم"], "الكمية": [2], "الوحدة": ["عدد"]})
    parsed, _ = bp.parse_frame(frame)
    assert list(parsed.columns) == BOQ_COLUMNS


def test_empty_frame_is_handled(bp):
    parsed, report = bp.parse_frame(pd.DataFrame())
    assert parsed is None and report["reason"] == "empty"
    assert bp.parse_frame(None)[0] is None


# ══════════════════════════════════════════════════════════════════════════════
#  الاسترجاع اللفظي
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def rt():
    from utils import retrieval
    return retrieval


def _booklet() -> str:
    filler = ("مواصفات الكابلات النحاسية والألياف البصرية وطرق التمديد "
              "والاختبار والفحص والتسليم في المواقع المختلفة. " * 40)
    return "\n".join([
        "1-1 مقدمة عامة عن المشروع وأهدافه.",
        filler,
        "7-3 يلتزم المورد بنسبة محتوى محلي لا تقل عن 30% وفق سياسة المحتوى المحلي.",
        "7-4 تُحتسب نسبة المحتوى المحلي وفق شهادة المحتوى المحلي المعتمدة.",
        filler,
        "9-1 الضمان الابتدائي بنسبة 1% من قيمة العرض وساري لمدة 90 يوماً.",
        filler,
    ])


def test_clauses_split_on_clause_boundaries(rt):
    chunks = rt.split_clauses(_booklet())
    assert len(chunks) > 1
    assert any("7-3" in c for c in chunks)


def test_search_finds_the_relevant_clause(rt):
    index = rt.build_index(_booklet())
    hits = index.search("المحتوى المحلي ونسبته المطلوبة", top_k=3)
    assert hits
    assert "المحتوى المحلي" in hits[0]["text"]


def test_focused_context_shrinks_and_keeps_the_answer(rt):
    text = _booklet()
    focused, stats = rt.focused_context(text, "المحتوى المحلي", budget_chars=3000)
    assert stats["applied"] is True
    assert stats["after"] < stats["before"]
    assert "محتوى محلي" in focused or "المحتوى المحلي" in focused


def test_short_text_is_returned_untouched(rt):
    """لا فائدة من الاسترجاع تحت السقف، والمخاطرة بإسقاط بند بلا مقابل."""
    text = "بند قصير واحد فقط."
    focused, stats = rt.focused_context(text, "أي استعلام", budget_chars=10000)
    assert focused == text and stats["applied"] is False


def test_unmatched_query_returns_everything(rt):
    """
    استعلام لا يُطابق شيئاً لا يعني أن الكراسة خالية — يعني أن الاسترجاع لم
    يفهم. نُعيد النص كاملاً بدل إرسال لا شيء.
    """
    text = _booklet()
    focused, stats = rt.focused_context(text, "zzzz qqqq", budget_chars=500)
    assert focused == text and stats["applied"] is False


def test_selected_chunks_keep_document_order(rt):
    """البنود تُقرأ متسلسلة؛ خلطها يجعل الشرط يسبق سياقه."""
    text = _booklet()
    focused, stats = rt.focused_context(
        text, "المحتوى المحلي والضمان الابتدائي", budget_chars=4000)
    if stats["applied"] and "7-3" in focused and "9-1" in focused:
        assert focused.index("7-3") < focused.index("9-1")


def test_tokenizer_normalizes_arabic_spelling(rt):
    assert rt.tokenize("الأعمال") == rt.tokenize("الاعمال")
    assert rt.tokenize("شهادة") == rt.tokenize("شهاده")


# ══════════════════════════════════════════════════════════════════════════════
#  سجل التوفير
# ══════════════════════════════════════════════════════════════════════════════


def test_ledger_accumulates_by_method(fake_streamlit):
    from utils import savings

    savings.reset()
    savings.record(savings.METHOD_CLEANUP, 10_000, 6_000)
    savings.record(savings.METHOD_RETRIEVAL, 20_000, 4_000)
    report = savings.summary()

    assert report["tokens_saved"] > 0
    assert report["by_method"][savings.METHOD_CLEANUP] > 0
    assert report["by_method"][savings.METHOD_RETRIEVAL] > report["by_method"][savings.METHOD_CLEANUP]
    assert 0 < report["ratio"] < 1


def test_avoided_calls_are_counted_separately(fake_streamlit):
    """توفير الاستدعاء كله أثمن من تقليص سياقه."""
    from utils import savings

    savings.reset()
    savings.record(savings.METHOD_LOCAL_PARSE, 5_000, 0, avoided_call=True)
    savings.record(savings.METHOD_CLEANUP, 1_000, 800)
    report = savings.summary()
    assert report["avoided_calls"] == 1
    assert report["calls"] == 1


def test_empty_ledger_is_zero(fake_streamlit):
    from utils import savings

    savings.reset()
    report = savings.summary()
    assert report["tokens_saved"] == 0 and report["ratio"] == 0.0


# ══════════════════════════════════════════════════════════════════════════════
#  الجسر: التضمين إن توفّر، وإلا الاسترجاع اللفظي
# ══════════════════════════════════════════════════════════════════════════════


def _long_rfp() -> str:
    """كراسة أطول من سقف الاسترجاع، فيها بند محتوى محلي واحد بين حشو."""
    filler = "\n\n".join(
        f"{i}-1 يلتزم المورد بتوريد وتركيب الكابلات والمحولات وفق المواصفات "
        f"الفنية المرفقة رقم {i} وبما يحقق أهداف الجهة من هذا المشروع الحيوي."
        for i in range(1, 60)
    )
    clause = ("30-4 يلتزم المورد بنسبة المحتوى المحلي المعلنة في القائمة "
              "الإلزامية ويقدّم شهادة المحتوى المحلي سارية عند التقديم.")
    return filler + "\n\n" + clause + "\n\n" + filler


def test_falls_back_to_lexical_retrieval_without_an_embedding_key(
        temp_db, fake_streamlit):
    """
    الموفّر المحلي بلا مفتاح تضمين كان يفقد الاسترجاع كلياً فتُمرَّر الكراسة
    كاملة. الاسترجاع اللفظي يسدّ ذلك بلا شبكة ولا كلفة.
    """
    from utils import knowledge

    fake_streamlit.session_state["ai_provider"] = "local"
    fake_streamlit.session_state["embed_provider"] = "gemini"
    fake_streamlit.session_state["api_gemini"] = ""   # لا مفتاح تضمين

    body = _long_rfp()
    block = knowledge.rfp_context_for(body, "الالتزام بالمحتوى المحلي")

    assert block, "لم يُسترجَع شيء رغم توفّر المسار اللفظي"
    assert "المحتوى المحلي" in block
    assert len(block) < len(body), "الاسترجاع لم يقلّص السياق"


def test_lexical_fallback_is_recorded_as_a_saving(temp_db, fake_streamlit):
    from utils import knowledge, savings

    fake_streamlit.session_state["api_gemini"] = ""
    knowledge.rfp_context_for(_long_rfp(), "الالتزام بالمحتوى المحلي")

    assert savings.summary()["by_method"][savings.METHOD_RETRIEVAL] > 0


def test_embedding_path_wins_when_a_key_is_present(temp_db, fake_streamlit,
                                                   monkeypatch):
    """مع مفتاح تضمين يبقى المسار الدلالي هو المستخدم لا اللفظي."""
    from utils import knowledge

    fake_streamlit.session_state["api_gemini"] = "key"
    monkeypatch.setattr(knowledge, "embed_texts",
                        lambda texts, task_type: [[1.0, 0.0] for _ in texts])

    block = knowledge.rfp_context_for("بند قصير عن المحتوى المحلي", "المحتوى المحلي")
    assert "مسترجعة آلياً" in block, "لم يُستخدم مسار التضمين رغم توفّر المفتاح"


def test_short_rfp_is_left_alone(temp_db, fake_streamlit):
    """كراسة أقصر من السقف لا تُقلَّص — لا فائدة، والمخاطرة إسقاط بند."""
    from utils import knowledge

    fake_streamlit.session_state["api_gemini"] = ""
    assert knowledge.rfp_context_for("بند واحد قصير", "أي استعلام") == ""
