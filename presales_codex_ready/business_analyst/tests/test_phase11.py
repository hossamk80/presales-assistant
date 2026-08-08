"""اختبارات المرحلة 11: طبقة الموفّرين، القياس، الحدّ، الذاكرة، والاسترجاع."""
import json
import struct

import pytest


@pytest.fixture()
def providers_pkg(temp_db):
    from utils import providers
    return providers


@pytest.fixture()
def cat():
    from utils.providers import catalog
    return catalog


# ─── 11-3: سجل النماذج ────────────────────────────────────────────────────────


def test_catalog_is_well_formed(cat):
    for name, info in cat.load_catalog().items():
        assert info.get("label"), name
        for model_id, m in (info.get("models") or {}).items():
            assert m.get("label"), model_id
            assert m.get("context", 0) > 0, model_id
            for field in ("in", "cached", "out"):
                assert field in m, f"{model_id} ينقصه {field}"


def test_catalog_override_file_extends_without_code(cat, tmp_path, monkeypatch):
    """إضافة نموذج جديد بتحرير السجل وحده — شرط قبول 11-3."""
    override = {
        "gemini": {"models": {"gemini-9-ultra": {
            "label": "Gemini 9 Ultra", "context": 2_000_000, "json": True,
            "in": 9.0, "cached": 1.0, "out": 27.0, "tier": "",
        }}},
    }
    path = tmp_path / "models.json"
    path.write_text(json.dumps(override), encoding="utf-8")
    monkeypatch.setattr(cat, "MODELS_PATH", str(path))
    cat._cached_catalog = None

    assert cat.model_info("gemini", "gemini-9-ultra")
    # النماذج الأصلية باقية — الدمج لا يستبدل
    assert cat.model_info("gemini", "gemini-3.6-flash")


def test_every_task_has_a_declared_default_model(cat):
    """لكل مهمة نموذج افتراضي معلن — شرط قبول 11-5."""
    for provider in cat.provider_names():
        if not cat.models_of(provider):
            continue
        for task in cat.TASK_TIERS:
            assert cat.task_default_model(provider, task), (provider, task)


def test_cost_uses_provider_counters(cat):
    """الكلفة من عدّادات الموفّر: المخزَّن أرخص من الطازج (11-7)."""
    fresh = cat.cost_of("anthropic", "claude-sonnet-5", 1_000_000, 0, 0)
    cached = cat.cost_of("anthropic", "claude-sonnet-5", 1_000_000, 1_000_000, 0)
    assert fresh == pytest.approx(3.0)
    assert cached == pytest.approx(0.30)
    out = cat.cost_of("anthropic", "claude-sonnet-5", 0, 0, 1_000_000)
    assert out == pytest.approx(15.0)


# ─── 11-1 / 11-2: التجريد وتبديل الموفّر ─────────────────────────────────────


def test_switching_provider_changes_model_options(providers_pkg, fake_streamlit):
    """تبديل الموفّر يتم من الإعدادات وحدها — الواجهات تقرأ الخيارات ديناميكياً."""
    fake_streamlit.session_state["ai_provider"] = "gemini"
    gemini_options = providers_pkg.model_options()
    fake_streamlit.session_state["ai_provider"] = "anthropic"
    claude_options = providers_pkg.model_options()
    assert gemini_options != claude_options
    assert any("Claude" in o for o in claude_options)


def test_resolve_model_follows_active_provider(temp_db, fake_streamlit):
    from utils import ai_engine

    fake_streamlit.session_state["ai_provider"] = "anthropic"
    assert ai_engine.resolve_model("Claude Sonnet 5") == "claude-sonnet-5"
    # اسم Gemini تاريخي محفوظ في منافسة قديمة يظل يُحلّ لمعرّفه
    assert ai_engine.resolve_model("Gemini 3.6 Flash") == "gemini-3.6-flash"
    # اسم مجهول مع موفّر غير Gemini يعود لافتراضي الموفّر النشط
    assert ai_engine.resolve_model("؟؟") in ai_engine.providers.catalog.models_of("anthropic")


def test_local_provider_is_ready_without_a_key(providers_pkg, fake_streamlit):
    """المحلي يعمل بلا مفتاح — شرط قبول 11-2."""
    fake_streamlit.session_state["ai_provider"] = "local"
    assert providers_pkg.has_credentials() is True


def test_keyed_provider_requires_its_own_key(providers_pkg, fake_streamlit):
    """كل موفّر يعمل بمفتاحه هو — مفتاح Gemini لا يُجيز استدعاء Claude."""
    fake_streamlit.session_state["ai_provider"] = "anthropic"
    fake_streamlit.session_state["api_gemini"] = "gemini-key"
    assert providers_pkg.has_credentials() is False
    fake_streamlit.session_state["api_claude"] = "claude-key"
    assert providers_pkg.has_credentials() is True


def test_embed_readiness_follows_embedding_provider(providers_pkg, fake_streamlit):
    """جاهزية الفهرسة تُقاس على موفّر التضمين لا على موفّر النص (11-6)."""
    fake_streamlit.session_state["ai_provider"] = "local"
    fake_streamlit.session_state["embed_provider"] = "gemini"
    assert providers_pkg.embed_ready() is False
    fake_streamlit.session_state["api_gemini"] = "gemini-key"
    assert providers_pkg.embed_ready() is True


def test_schema_conversion_to_standard_json_schema(providers_pkg):
    from utils.providers.base import to_json_schema

    gemini_schema = {
        "type": "OBJECT",
        "properties": {
            "items": {"type": "ARRAY", "items": {
                "type": "OBJECT",
                "properties": {"name": {"type": "STRING"}},
                "required": ["name"],
            }},
        },
        "required": ["items"],
    }
    out = to_json_schema(gemini_schema)
    assert out["type"] == "object"
    assert out["additionalProperties"] is False
    inner = out["properties"]["items"]["items"]
    assert inner["type"] == "object"
    assert inner["properties"]["name"]["type"] == "string"


# ─── 11-7 / 11-13: التسجيل وذاكرة النتائج ────────────────────────────────────


class _StubProvider:
    """موفّر وهمي يعدّ الاستدعاءات ويُرجع استهلاكاً معلوماً."""

    name = "gemini"

    def __init__(self):
        from utils.providers.base import GenResult, Usage

        self.calls = 0
        self._result = lambda: GenResult(
            text="النتيجة", provider="gemini", model="gemini-3.6-flash",
            usage=Usage(input_tokens=1000, cached_tokens=400, output_tokens=200),
            elapsed_ms=15,
        )

    def generate(self, model_id, prompt, temperature=None, max_tokens=None):
        self.calls += 1
        return self._result()

    def generate_json(self, model_id, prompt, schema, temperature=None, max_tokens=None):
        self.calls += 1
        result = self._result()
        result.parsed = {"ok": True}
        result.text = '{"ok": true}'
        return result


def test_every_call_is_logged_from_provider_counters(providers_pkg, temp_db, monkeypatch):
    stub = _StubProvider()
    monkeypatch.setattr(providers_pkg, "get_provider", lambda name: stub)

    result = providers_pkg.run("gemini-3.6-flash", "تعليمات", task="write")
    assert result.text == "النتيجة"

    rows = temp_db.usage_summary("model")
    assert rows and rows[0]["input_tokens"] == 1000
    assert rows[0]["cached_tokens"] == 400
    assert rows[0]["output_tokens"] == 200
    assert rows[0]["cost"] > 0


def test_repeat_call_served_from_cache_without_tokens(providers_pkg, temp_db, monkeypatch):
    """إعادة الضغط بلا تغيير معطيات لا تُنفق توكن — شرط قبول 11-13."""
    stub = _StubProvider()
    monkeypatch.setattr(providers_pkg, "get_provider", lambda name: stub)

    first = providers_pkg.run("gemini-3.6-flash", "تعليمات")
    second = providers_pkg.run("gemini-3.6-flash", "تعليمات")
    assert stub.calls == 1, "الاستدعاء الثاني كان يجب أن يُخدم من الذاكرة"
    assert second.text == first.text

    totals = temp_db.usage_totals("")
    assert totals["cache_hits"] == 1
    # تغيير المعطيات يتجاوز الذاكرة
    providers_pkg.run("gemini-3.6-flash", "تعليمات أخرى")
    assert stub.calls == 2


def test_json_cache_roundtrip_keeps_parsed_object(providers_pkg, temp_db, monkeypatch):
    stub = _StubProvider()
    monkeypatch.setattr(providers_pkg, "get_provider", lambda name: stub)
    schema = {"type": "OBJECT", "properties": {"ok": {"type": "BOOLEAN"}}}

    first = providers_pkg.run("gemini-3.6-flash", "استخرج", schema=schema)
    second = providers_pkg.run("gemini-3.6-flash", "استخرج", schema=schema)
    assert stub.calls == 1
    assert first.parsed == {"ok": True}
    assert second.parsed == {"ok": True}


def test_cache_can_be_disabled(providers_pkg, temp_db, monkeypatch, fake_streamlit):
    stub = _StubProvider()
    monkeypatch.setattr(providers_pkg, "get_provider", lambda name: stub)
    fake_streamlit.session_state["ai_cache_enabled"] = False

    providers_pkg.run("gemini-3.6-flash", "تعليمات")
    providers_pkg.run("gemini-3.6-flash", "تعليمات")
    assert stub.calls == 2


# ─── 11-9: حدّ الإنفاق الشهري ────────────────────────────────────────────────


def _spend(temp_db, providers_pkg, cost: float):
    temp_db.log_ai_usage(
        project_id=None, project_name="", task="write", provider="gemini",
        model="gemini-3.6-flash", input_tokens=0, cached_tokens=0,
        output_tokens=0, cost=cost, elapsed_ms=0, status="ok",
        month=providers_pkg.month_key(),
    )


def test_budget_blocks_at_100_percent(providers_pkg, temp_db, fake_streamlit, monkeypatch):
    """التجاوز يمنع الاستدعاء برسالة صريحة لا بفشل صامت — شرط قبول 11-9."""
    from utils.providers import BudgetExceeded

    fake_streamlit.session_state["ai_month_budget"] = 10.0
    _spend(temp_db, providers_pkg, 10.0)

    stub = _StubProvider()
    monkeypatch.setattr(providers_pkg, "get_provider", lambda name: stub)
    with pytest.raises(BudgetExceeded):
        providers_pkg.run("gemini-3.6-flash", "تعليمات")
    assert stub.calls == 0, "استدعاء نُفّذ رغم بلوغ الحدّ"


def test_budget_warns_at_80_percent(providers_pkg, temp_db, fake_streamlit):
    fake_streamlit.session_state["ai_month_budget"] = 10.0
    _spend(temp_db, providers_pkg, 8.5)
    providers_pkg.check_budget()
    assert any(kind == "warning" for kind, _ in fake_streamlit.messages)


def test_engine_reports_budget_stop_to_user(temp_db, fake_streamlit):
    from utils import ai_engine
    from utils.providers import BudgetExceeded

    def blocked_run(*a, **k):
        raise BudgetExceeded("الحدّ")

    ai_engine.providers.run = blocked_run
    assert ai_engine._call("تعليمات", "gemini-3.6-flash") is None
    assert any(kind == "error" for kind, _ in fake_streamlit.messages)


# ─── 11-6: إبطال متجهات المستودع عند تغيير نموذج التضمين ─────────────────────


def _pack(vector):
    return struct.pack(f"{len(vector)}f", *vector)


def test_stale_chunks_are_counted_and_excluded(temp_db, fake_streamlit, monkeypatch):
    """تغيير النموذج يعرض التحذير ولا يُفقد المستودع بلا علم — شرط قبول 11-6."""
    from utils import knowledge

    doc = temp_db.add_kb_document("قديم.pdf", "project", 100)
    temp_db.add_kb_chunks(doc, [(0, "نص قديم", 3, _pack([1.0, 0.0, 0.0]))],
                          embed_model="gemini/old-model")
    doc2 = temp_db.add_kb_document("جديد.pdf", "project", 100)
    temp_db.add_kb_chunks(doc2, [(0, "نص جديد", 3, _pack([1.0, 0.0, 0.0]))],
                          embed_model=knowledge.active_embed_model())

    assert knowledge.stale_chunk_count() == 1

    monkeypatch.setattr(knowledge, "embed_texts",
                        lambda texts, task_type: [[1.0, 0.0, 0.0]])
    hits = knowledge.search("استعلام")
    assert [h["text"] for h in hits] == ["نص جديد"], \
        "مقطع بنموذج قديم دخل نتائج البحث"


def test_reindex_updates_stale_chunks(temp_db, fake_streamlit, monkeypatch):
    from utils import knowledge

    doc = temp_db.add_kb_document("قديم.pdf", "project", 100)
    temp_db.add_kb_chunks(doc, [(0, "نص", 3, _pack([1.0, 0.0, 0.0]))],
                          embed_model="gemini/old-model")

    monkeypatch.setattr(knowledge, "embed_texts",
                        lambda texts, task_type: [[0.0, 1.0, 0.0] for _ in texts])
    monkeypatch.setattr(knowledge, "EMBED_DIMS", 3)
    assert knowledge.reindex_all() == 1
    assert knowledge.stale_chunk_count() == 0


# ─── 11-11: فهرسة الكراسة واسترجاعها ─────────────────────────────────────────


def test_rfp_indexing_retrieves_relevant_clause(temp_db, fake_streamlit, monkeypatch):
    """متطلب في عمق الكراسة يُسترجَع للقسم الذي يخصّه — شرط قبول 11-11."""
    from utils import knowledge

    sla_chunk = "يلتزم المورّد بمستوى خدمة SLA لا يقل عن 99.9٪ شهرياً."
    other_chunk = "تُقدَّم العروض في مظروفين منفصلين فني ومالي."
    vectors = {sla_chunk: [1.0, 0.0], other_chunk: [0.0, 1.0],
               "مستويات الخدمة": [1.0, 0.0]}

    def fake_embed(texts, task_type):
        return [vectors.get(t, [0.5, 0.5]) for t in texts]

    monkeypatch.setattr(knowledge, "embed_texts", fake_embed)
    monkeypatch.setattr(knowledge, "chunk_text",
                        lambda text, **k: [sla_chunk, other_chunk])

    assert knowledge.index_rfp("نص الكراسة الكامل")
    hits = knowledge.rfp_retrieve("مستويات الخدمة", top_k=1)
    assert hits == [sla_chunk]

    block = knowledge.rfp_context_block("مستويات الخدمة", top_k=1)
    assert sla_chunk in block and other_chunk not in block


def test_rfp_index_is_reused_until_text_changes(temp_db, fake_streamlit, monkeypatch):
    from utils import knowledge

    calls = {"n": 0}

    def fake_embed(texts, task_type):
        calls["n"] += 1
        return [[1.0, 0.0] for _ in texts]

    monkeypatch.setattr(knowledge, "embed_texts", fake_embed)
    knowledge.index_rfp("نص الكراسة")
    first = calls["n"]
    knowledge.index_rfp("نص الكراسة")
    assert calls["n"] == first, "أُعيدت فهرسة كراسة لم تتغير"
    knowledge.index_rfp("نص كراسة معدّلة")
    assert calls["n"] > first


# ─── 11-10: الموجز المضغوط ───────────────────────────────────────────────────


def test_matrix_block_compresses_requirements(temp_db, fake_streamlit):
    import pandas as pd
    from utils.state import matrix_block

    fake_streamlit.session_state["df_compliance"] = pd.DataFrame({
        "المعرّف": ["REQ-001"],
        "المتطلب": ["توفير دعم فني على مدار الساعة"],
        "الأهمية": ["High"],
    })
    block = matrix_block()
    assert "REQ-001" in block and "دعم فني" in block


def test_matrix_block_empty_without_matrix(temp_db, fake_streamlit):
    from utils.state import matrix_block

    assert matrix_block() == ""


# ─── التكامل مع المحرك ───────────────────────────────────────────────────────


def test_call_json_returns_provider_parsed_object(temp_db, fake_streamlit, monkeypatch):
    from utils import ai_engine
    from utils.providers import GenResult

    def fake_run(model_id, prompt, schema=None, task="extract"):
        return GenResult(parsed={"requirements": []}, text=None)

    ai_engine.providers.run = fake_run
    out = ai_engine._call_json("تعليمات", "gemini-3.6-flash", {"type": "OBJECT"})
    assert out == {"requirements": []}


def test_missing_key_error_is_still_reported(temp_db, fake_streamlit):
    """فشل الاستدعاء لا يمسح نص المستخدم — يُرجع None برسالة واضحة."""
    from utils import ai_engine

    assert ai_engine.ai_generate("تعليمات") is None
    assert any(kind == "error" for kind, _ in fake_streamlit.messages)


# ─── البثّ التدريجي (ب-2) ─────────────────────────────────────────────────────
#
# انتظار القسم دقيقةً بلا أي إشارة كان يجعل المستخدم يظنّ النظام معلَّقاً فيعيد
# الضغط — **فتُنفَق توكنات مرّتين على قسم واحد**. والبثّ لا يجوز أن يُضعف أياً
# من ضمانات المسار العادي: الذاكرة · الميزانية · القياس · وألّا يُسلَّم ناقص.


class _StreamingProvider:
    """موفّر يبثّ ثلاثة مقاطع ثم يُعيد عدّاداته."""

    name = "gemini"
    streams = True

    def __init__(self, pieces=None):
        self.pieces = pieces or ["نلتزم ", "بتسليم ", "الخطة."]
        self.calls = 0

    def generate_stream(self, model_id, prompt, temperature=None, max_tokens=None):
        from utils.providers.base import GenResult, Usage

        self.calls += 1
        for piece in self.pieces:
            yield piece
        return GenResult(provider=self.name, model=model_id,
                         usage=Usage(input_tokens=120, output_tokens=30),
                         elapsed_ms=900)


def test_the_text_arrives_in_pieces_and_accumulates(temp_db, fake_streamlit,
                                                    monkeypatch):
    """**شرط قبول ب-2**: النصّ يُعرض وهو يُكتب لا بعد اكتماله."""
    from utils import providers

    monkeypatch.setattr(providers, "get_provider", lambda name: _StreamingProvider())
    seen = []

    result = providers.run_stream("m", "اكتب", on_chunk=seen.append)

    assert seen == ["نلتزم ", "نلتزم بتسليم ", "نلتزم بتسليم الخطة."]
    assert result.text == "نلتزم بتسليم الخطة."


def test_the_usage_comes_from_the_provider_not_an_estimate(temp_db, fake_streamlit,
                                                           monkeypatch):
    """العدّادات تصل في آخر الدفق — والفوترة لا تُبنى على تقدير محلي (11-7)."""
    from utils import providers

    monkeypatch.setattr(providers, "get_provider", lambda name: _StreamingProvider())
    result = providers.run_stream("m", "اكتب")

    assert result.usage.input_tokens == 120
    assert result.usage.output_tokens == 30


def test_a_cached_result_is_served_without_streaming(temp_db, fake_streamlit,
                                                     monkeypatch):
    """
    البثّ لإخفاء انتظار، ولا انتظار في نتيجة محفوظة (11-13). فتُسلَّم دفعةً
    واحدة بلا استدعاء ثانٍ.
    """
    from utils import providers

    provider = _StreamingProvider()
    monkeypatch.setattr(providers, "get_provider", lambda name: provider)

    providers.run_stream("m", "اكتب")
    seen = []
    providers.run_stream("m", "اكتب", on_chunk=seen.append)

    assert provider.calls == 1                    # لم يُستدعَ الموفّر ثانيةً
    assert seen == ["نلتزم بتسليم الخطة."]        # دفعة واحدة لا مقاطع


def test_a_broken_stream_raises_and_stores_nothing(temp_db, fake_streamlit,
                                                   monkeypatch):
    """
    **الأهمّ**: قسمٌ مبتور يبدو مكتوباً هو ما يصل الجهة. الفشل يرفع ولا يُسلِّم
    الناقص كأنه تامّ، ولا يُخزَّن الناقص في الذاكرة — وإلا سُلِّم كاملاً في
    المرة القادمة بلا استدعاء.
    """
    from utils import providers
    from utils.providers.base import Provider, ProviderError

    class Broken(Provider):
        name = "gemini"
        streams = True

        def generate_stream(self, model_id, prompt, temperature=None, max_tokens=None):
            yield "نصف "
            raise ProviderError("انقطع الاتصال")

    monkeypatch.setattr(providers, "get_provider", lambda name: Broken())

    with pytest.raises(ProviderError):
        providers.run_stream("m", "مختلف", on_chunk=lambda t: None)

    fp = providers.fingerprint("gemini", "m", "مختلف", None, None)
    assert providers.db.ai_cache_get(fp) is None


def test_a_provider_without_streaming_still_works(temp_db, fake_streamlit,
                                                  monkeypatch):
    """
    موفّر لا يدعم البثّ **لا يُكسَر**: يسقط إلى استدعاء عادي فيرى المستخدم
    النتيجة دفعةً واحدة كما اليوم. البثّ تحسينٌ لا شرط عمل.
    """
    from utils import providers
    from utils.providers.base import GenResult, Provider

    class Plain(Provider):
        name = "gemini"
        streams = False

        def generate(self, model_id, prompt, temperature=None, max_tokens=None):
            return GenResult(text="نصّ كامل", provider=self.name, model=model_id)

    monkeypatch.setattr(providers, "get_provider", lambda name: Plain())
    seen = []

    result = providers.run_stream("m", "اكتب", on_chunk=seen.append)

    assert result.text == "نصّ كامل"
    assert seen == ["نصّ كامل"]


def test_the_budget_is_checked_before_the_first_piece(temp_db, fake_streamlit,
                                                      monkeypatch):
    """
    حدّ الإنفاق يُفحَص **قبل** بدء الدفق لا بعده (11-9): دفقٌ بدأ أنفق بالفعل.
    """
    from utils import providers
    from utils.providers.base import BudgetExceeded

    provider = _StreamingProvider()
    monkeypatch.setattr(providers, "get_provider", lambda name: provider)

    def over(*a, **k):
        raise BudgetExceeded("تجاوز الحدّ")

    monkeypatch.setattr(providers, "check_budget", over)

    with pytest.raises(BudgetExceeded):
        providers.run_stream("m", "اكتب")
    assert provider.calls == 0


def test_the_fixed_rules_reach_a_streamed_call_too(temp_db, fake_streamlit,
                                                   monkeypatch):
    """
    14-2: القواعد الثابتة تُلحق في `_call` — والمسار المبثوث يمرّ به كذلك، وإلا
    صار البثّ باباً خلفياً حول منع التسعير وشرط القرار البشري.
    """
    from utils import ai_engine, providers

    captured = {}

    def spy(model_id, prompt, task="write", on_chunk=None):
        from utils.providers.base import GenResult

        captured["prompt"] = prompt
        if on_chunk:
            on_chunk("رد")
        return GenResult(text="رد", provider="gemini", model=model_id)

    monkeypatch.setattr(providers, "run_stream", spy)
    ai_engine.ai_generate("اكتب قسماً", on_chunk=lambda t: None)

    assert ai_engine.has_fixed_rules(captured["prompt"])


def test_json_calls_are_not_streamed(fake_streamlit):
    """
    الاستخراج المُهيكل لا يُبثّ عمداً: JSON ناقص لا يُحلَّل، والبثّ لا يُظهر
    منه شيئاً مفيداً للمستخدم — كلفةٌ في التعقيد بلا مقابل.
    """
    import inspect

    from utils import ai_engine

    assert "on_chunk" not in inspect.signature(ai_engine.ai_generate_json).parameters
    assert "on_chunk" in inspect.signature(ai_engine.ai_generate).parameters


def test_the_live_preview_degrades_where_there_is_no_display(fake_streamlit):
    """
    البثّ تحسينٌ في العرض: غيابُ مكان العرض يُسقط المعاينة وحدها ولا يُسقط
    توليد قسم.
    """
    from views import doc_builder

    on_chunk, close = doc_builder._live_preview()

    assert on_chunk is None
    assert close() is None
