"""
اختبارات موفّر Anthropic — البثّ التدريجي (ب-2) وما كان مخفيّاً معه.

الملف كان **بلا سطرٍ مفحوص** (0% تغطية)، وهو الموفّر الوحيد الذي بقي بلا بثّ.
وقياس التغطية هو ما جعل ذلك مرئياً — ومعه عطبٌ صامت: `temperature` كانت
تُستقبَل وتُهمَل، فحرارةٌ يضبطها المستخدم تسري على Gemini و OpenAI ولا تسري
على Claude بلا خطأ يُرفع.

الـ SDK لا تُستدعى حقيقةً: يُركَّب بديلٌ في `sys.modules` يُنتج نفس أشكال
الأحداث، فتُفحَص **شيفرتنا** لا شبكة أحد.
"""
import sys
import types

import pytest


# ─── بديل الـ SDK ─────────────────────────────────────────────────────────────


class _Usage:
    def __init__(self, input_tokens=0, output_tokens=0, cache_read_input_tokens=0):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_read_input_tokens = cache_read_input_tokens


class _Message:
    """رسالة Anthropic النهائية: محتوىً وعدّادات وسبب توقّف."""

    def __init__(self, text="", usage=None, stop_reason="end_turn"):
        block = types.SimpleNamespace(type="text", text=text)
        self.content = [block]
        self.usage = usage or _Usage(input_tokens=100, output_tokens=20)
        self.stop_reason = stop_reason


def _delta(text):
    return types.SimpleNamespace(
        type="content_block_delta",
        delta=types.SimpleNamespace(type="text_delta", text=text),
    )


class _Stream:
    """مدير سياق يشبه `MessageStream`: يُتكرَّر أحداثاً ثم يُسأل الرسالة."""

    def __init__(self, events, final, record):
        self.events = events
        self.final = final
        self.record = record
        self.final_asked = 0

    def __enter__(self):
        self.record["entered"] = True
        return self

    def __exit__(self, *exc):
        self.record["exited"] = True
        return False

    def __iter__(self):
        return iter(self.events)

    def get_final_message(self):
        self.final_asked += 1
        if not self.record.get("entered") or self.record.get("exited"):
            raise AssertionError("الرسالة النهائية تُقرأ داخل `with` لا خارجه")
        return self.final


class _Messages:
    def __init__(self, owner):
        self.owner = owner

    def create(self, **kwargs):
        self.owner.calls.append(kwargs)
        return self.owner.reply

    def stream(self, **kwargs):
        self.owner.calls.append(kwargs)
        # سجلٌّ جديد لكل دفق: سجلٌّ مشترك يجعل `exited` من دفقٍ سابق يبدو
        # كأنه هذا الدفق — فيكذب الفحص على نفسه.
        self.owner.record = {}
        return _Stream(self.owner.events, self.owner.reply, self.owner.record)

    def count_tokens(self, **kwargs):
        return types.SimpleNamespace(input_tokens=42)


class _Client:
    def __init__(self, api_key=None, **_):
        self.api_key = api_key
        self.calls = []
        self.record = {}
        self.events = []
        self.reply = _Message("جواب")
        self.messages = _Messages(self)


@pytest.fixture()
def sdk(fake_streamlit, monkeypatch):
    """يركّب بديل `anthropic` ويُعيد العميل الذي سيستعمله الموفّر."""
    client = _Client()
    module = types.ModuleType("anthropic")
    module.Anthropic = lambda api_key=None, **kw: client
    monkeypatch.setitem(sys.modules, "anthropic", module)
    fake_streamlit.session_state["api_claude"] = "sk-test"
    return client


@pytest.fixture()
def provider(sdk):
    from utils.providers.anthropic_provider import AnthropicProvider
    return AnthropicProvider()


def _drain(generator):
    """يستنفد المولِّد ويعيد (المقاطع، ما أعاده)."""
    pieces = []
    while True:
        try:
            pieces.append(next(generator))
        except StopIteration as done:
            return pieces, done.value


# ─── البثّ ────────────────────────────────────────────────────────────────────


def test_the_provider_declares_that_it_streams():
    """
    `streams` هو ما تقرأه `run_stream` لتختار المسار. موفّرٌ ينفّذ البثّ ولا
    يعلنه يبقى على الاستدعاء العادي — شيفرةٌ تُكتب ولا تُستعمل.
    """
    from utils.providers.anthropic_provider import AnthropicProvider

    assert AnthropicProvider.streams is True


def test_only_text_deltas_are_yielded(provider, sdk):
    """
    الدفق يحمل أحداثاً كثيرة (بداية رسالة · بداية كتلة · نهايتها). ما يُخرَج
    هو نصٌّ فقط: حدثٌ آخر يُمرَّر كأنه نصّ يحشو المستند بضجيج.
    """
    sdk.events = [
        types.SimpleNamespace(type="message_start"),
        types.SimpleNamespace(type="content_block_start"),
        _delta("نلتزم "),
        types.SimpleNamespace(type="ping"),
        _delta("بتسليم "),
        _delta("الخطة."),
        types.SimpleNamespace(type="content_block_stop"),
        types.SimpleNamespace(type="message_stop"),
    ]

    pieces, result = _drain(provider.generate_stream("claude-x", "اكتب"))

    assert pieces == ["نلتزم ", "بتسليم ", "الخطة."]
    assert result.provider == "anthropic"
    assert result.model == "claude-x"


def test_an_empty_delta_is_not_yielded(provider, sdk):
    """مقطعٌ فارغ يُحسب تقدّماً زائفاً في الواجهة."""
    sdk.events = [_delta(""), _delta("نصّ"), _delta(None)]

    pieces, _ = _drain(provider.generate_stream("claude-x", "اكتب"))

    assert pieces == ["نصّ"]


def test_the_usage_comes_from_the_final_message(provider, sdk):
    """
    Anthropic ترسل `input_tokens` في بداية الدفق و `output_tokens` في آخره.
    جمعٌ محليّ تقديرٌ، والفوترة لا تُبنى على تقدير (11-8). والمخزَّن مؤقتاً
    يُضاف إلى الدخل **ويُسجَّل منفصلاً** فتُحتسب كلفته بسعره لا بسعر الجديد.
    """
    sdk.events = [_delta("نصّ")]
    sdk.reply = _Message(
        "نصّ", usage=_Usage(input_tokens=300, output_tokens=80,
                            cache_read_input_tokens=200),
    )

    _, result = _drain(provider.generate_stream("claude-x", "اكتب"))

    assert result.usage.input_tokens == 500      # 300 + 200 مخزَّن
    assert result.usage.cached_tokens == 200
    assert result.usage.output_tokens == 80


def test_a_refusal_raises_instead_of_delivering_the_partial_text(provider, sdk):
    """
    `stop_reason == "refusal"` لا يظهر إلا في نهاية الدفق، وقد يكون نصٌّ جزئي
    وصل قبله. يُرفع استثناءً كما في الاستدعاء العادي: نصُّ رفضٍ منقوص يُسلَّم
    كأنه جواب أسوأ من فشلٍ معلَن.
    """
    from utils.providers.base import ProviderError

    sdk.events = [_delta("لا أستطيع")]
    sdk.reply = _Message("لا أستطيع", stop_reason="refusal")

    generator = provider.generate_stream("claude-x", "اكتب")
    assert next(generator) == "لا أستطيع"     # المقطع وصل فعلاً

    with pytest.raises(ProviderError, match="refusal"):
        _drain(generator)


def test_the_connection_is_closed_even_when_the_consumer_walks_away(provider, sdk):
    """
    مولِّدٌ يُترك بلا استنفاد يُغلَق عند جمع القمامة، و`with` هو ما يضمن إغلاق
    الاتصال حينها. بدونه يبقى اتصالٌ مفتوحٌ لكل قسمٍ أُلغي عرضه.
    """
    sdk.events = [_delta("أ"), _delta("ب"), _delta("ج")]

    generator = provider.generate_stream("claude-x", "اكتب")
    assert next(generator) == "أ"
    assert sdk.record.get("entered") is True
    assert sdk.record.get("exited") is None

    generator.close()

    assert sdk.record.get("exited") is True


# ─── `temperature` كانت تُهمَل ────────────────────────────────────────────────


def test_the_temperature_reaches_the_request_when_streaming(provider, sdk):
    """
    حارس ارتداد: المعامل كان في التوقيع ولا يدخل الوسائط — فالحرارة تسري على
    الموفّرين الآخرين ولا تسري على Claude بلا أي أثر ظاهر.
    """
    sdk.events = [_delta("نصّ")]

    _drain(provider.generate_stream("claude-x", "اكتب", temperature=0.2))

    assert sdk.calls[-1]["temperature"] == 0.2


def test_the_temperature_reaches_the_plain_request_too(provider, sdk):
    provider.generate("claude-x", "اكتب", temperature=0.7)

    assert sdk.calls[-1]["temperature"] == 0.7


def test_no_temperature_key_when_the_user_did_not_set_one(provider, sdk):
    """
    `None` تعني «اتبع افتراض النموذج» لا «صفر». إرسالها صريحةً يفرض قيمةً لم
    يطلبها أحد.
    """
    sdk.events = [_delta("نصّ")]

    _drain(provider.generate_stream("claude-x", "اكتب"))
    provider.generate("claude-x", "اكتب")

    for call in sdk.calls:
        assert "temperature" not in call


# ─── ما يبقى مشتركاً بين المسارين ────────────────────────────────────────────


def test_the_cache_marker_follows_the_prompt_size_in_both_paths(provider, sdk):
    """
    دون الحدّ لا تُقبل البادئة في الذاكرة المؤقتة أصلاً، فالعلامة بلا معنى
    وتُرسَل في كل طلب بلا مقابل.
    """
    from utils.providers.anthropic_provider import CACHE_MIN_CHARS

    sdk.events = [_delta("نصّ")]

    provider.generate("claude-x", "قصير")
    assert "cache_control" not in sdk.calls[-1]

    _drain(provider.generate_stream("claude-x", "ط" * CACHE_MIN_CHARS))
    assert sdk.calls[-1]["cache_control"] == {"type": "ephemeral"}


def test_a_missing_key_is_refused_before_any_request(provider, sdk, fake_streamlit):
    """مفتاحٌ غائب يُرفع قبل بناء أي طلب — لا بعد محاولةٍ تفشل عند الخادم."""
    from utils.providers.base import ProviderError

    fake_streamlit.session_state["api_claude"] = ""

    with pytest.raises(ProviderError, match="missing_key"):
        _drain(provider.generate_stream("claude-x", "اكتب"))

    assert sdk.calls == []


def test_max_tokens_falls_back_to_the_declared_default(provider, sdk):
    """Anthropic تُلزم بـ `max_tokens`: طلبٌ بلاها يُرفض عند الخادم."""
    from utils.providers.anthropic_provider import DEFAULT_MAX_TOKENS

    sdk.events = [_delta("نصّ")]

    _drain(provider.generate_stream("claude-x", "اكتب"))
    assert sdk.calls[-1]["max_tokens"] == DEFAULT_MAX_TOKENS

    _drain(provider.generate_stream("claude-x", "اكتب", max_tokens=500))
    assert sdk.calls[-1]["max_tokens"] == 500


def test_embedding_is_refused_with_a_reason(provider, sdk):
    """Anthropic لا توفّر نماذج تضمين — والرسالة تقول ما يفعله المستخدم."""
    from utils.providers.base import ProviderError

    with pytest.raises(ProviderError, match="تضمين"):
        provider.embed("m", ["نصّ"], "RETRIEVAL_DOCUMENT", 768)


# ─── التكامل مع `run_stream` ─────────────────────────────────────────────────


def test_run_stream_uses_the_streaming_path_for_anthropic(temp_db, sdk,
                                                          fake_streamlit,
                                                          monkeypatch):
    """
    **شرط قبول ب-2 لهذا الموفّر**: المسار المستعمل هو البثّ لا السقوط إلى
    استدعاء عادي — والواجهة ترى النصّ **متراكماً** في كل مرة.
    """
    from utils import providers
    from utils.providers.anthropic_provider import AnthropicProvider

    sdk.events = [_delta("نلتزم "), _delta("بالخطة.")]
    fake_streamlit.session_state["ai_provider"] = "anthropic"
    fake_streamlit.session_state["api_claude"] = "sk-test"
    monkeypatch.setattr(providers, "get_provider", lambda name: AnthropicProvider())

    seen = []
    result = providers.run_stream("claude-x", "اكتب", on_chunk=seen.append)

    assert seen == ["نلتزم ", "نلتزم بالخطة."]
    assert result.text == "نلتزم بالخطة."
    # ولم يُستدعَ المسار العادي ولو مرّة
    assert all("stream" not in str(call.get("messages", "")) for call in sdk.calls)
