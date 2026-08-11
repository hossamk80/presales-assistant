"""
اختبارات المرحلة 10 — إصلاح العيوب التي رصدتها مراجعة 360 درجة.

أربعة عيوب: إشعار سرية عربي داخل عرض إنجليزي · قالب افتراضي يحجب التصدير ·
تاريخ هجري بلا قراءة · فشل عابر يُسقط تحليلاً كاملاً.
"""
import datetime

import pytest


# ─── إشعار السرية يتبع لغة المخرجات ───────────────────────────────────────────


@pytest.fixture()
def file_handler():
    from utils import file_handler
    return file_handler


def test_confidentiality_notice_follows_output_language(file_handler):
    """
    العيب: النص كان مكتوباً عربياً في `views/doc_builder.py`، فيخرج العرض
    الإنجليزي الكامل حاملاً صفحة عربية أمام لجنة الفتح.
    """
    arabic = file_handler.confidentiality_notice("شركة الحلول", "ar")
    english = file_handler.confidentiality_notice("Solutions Co", "en")

    assert "سري للغاية" in arabic
    assert "شركة الحلول" in arabic

    assert "strictly confidential" in english.lower()
    assert "Solutions Co" in english
    assert not any("؀" <= ch <= "ۿ" for ch in english), \
        "الإشعار الإنجليزي يحوي حروفاً عربية"


def test_confidentiality_notice_both_languages(file_handler):
    both = file_handler.confidentiality_notice("Acme", "both")
    assert "سري للغاية" in both
    assert "strictly confidential" in both.lower()


def test_confidentiality_notice_falls_back_to_arabic(file_handler):
    """لغة غير معروفة لا تُخرج نصاً فارغاً."""
    assert "سري للغاية" in file_handler.confidentiality_notice("Acme", "zz")


def test_confidentiality_notice_tolerates_missing_company(file_handler):
    assert file_handler.confidentiality_notice("", "en").strip()
    assert file_handler.confidentiality_notice(None, "ar").strip()


# ─── رمز اسم الشركة لا يحجب التصدير ───────────────────────────────────────────


def test_company_token_is_resolved(file_handler):
    """
    العيب: خطاب التقديم الافتراضي يحمل `[اسم الشركة]`، وبوابة التصدير تحجب
    أي نص فيه `[...]`. فكان المستخدم الجديد يجد التصدير محجوباً بنص شحنّاه نحن.
    """
    from utils.state import STATE_SCHEMA

    default = STATE_SCHEMA["c_cover_template"]
    assert "[اسم الشركة]" in default, "القالب الافتراضي تغيّر — حدّث الاختبار"

    resolved = file_handler.resolve_document_tokens(default, "شركة الحلول التقنية")
    assert "[اسم الشركة]" not in resolved
    assert "شركة الحلول التقنية" in resolved


def test_resolved_cover_passes_the_export_placeholder_gate(file_handler):
    """القالب الافتراضي بعد الاستبدال لا يوقفه فحص النص النائب."""
    from utils.state import STATE_SCHEMA
    from views.doc_builder import PLACEHOLDER_RE

    resolved = file_handler.resolve_document_tokens(
        STATE_SCHEMA["c_cover_template"], "شركة الحلول"
    )
    assert not PLACEHOLDER_RE.search(resolved)


def test_unknown_company_keeps_blocking(file_handler):
    """
    اسم شركة مفقود يُبقي الحجب: غلاف بلا اسم مُقدِّم عيب لا يقلّ عن نص نائب
    منسي، فلا يُرفع الحجب بإخفاء الرمز.
    """
    from views.doc_builder import PLACEHOLDER_RE

    text = "نفيدكم نحن [اسم الشركة] برغبتنا…"
    assert PLACEHOLDER_RE.search(file_handler.resolve_document_tokens(text, ""))
    assert PLACEHOLDER_RE.search(file_handler.resolve_document_tokens(text, "   "))


def test_english_company_token_is_resolved(file_handler):
    out = file_handler.resolve_document_tokens("We, [Company Name], hereby…", "Acme")
    assert out == "We, Acme, hereby…"


def test_other_placeholders_are_left_to_the_gate(file_handler):
    """
    الرموز المعروفة وحدها تُستبدل. نص نائب حقيقي تركه النموذج يجب أن يبقى
    ليحجبه الفحص.
    """
    from views.doc_builder import PLACEHOLDER_RE

    out = file_handler.resolve_document_tokens(
        "نفيدكم نحن [اسم الشركة] بخبرة [عدد] سنوات", "شركة الحلول"
    )
    assert "شركة الحلول" in out
    assert PLACEHOLDER_RE.search(out), "النص النائب الحقيقي اختفى"


# ─── التاريخ الهجري ───────────────────────────────────────────────────────────


@pytest.fixture()
def submission():
    from utils import submission
    return submission


def _hijri_available() -> bool:
    try:
        import hijridate  # noqa: F401
        return True
    except ImportError:
        try:
            import hijri_converter  # noqa: F401
            return True
        except ImportError:
            return False


hijri_only = pytest.mark.skipif(
    not _hijri_available(), reason="مكتبة التحويل الهجري غير مثبّتة"
)


@hijri_only
def test_hijri_date_is_converted(submission):
    """
    العيب: الكراسات الحكومية السعودية تؤرّخ هجرياً، وكان القارئ ميلادياً فقط
    فيصمت بلا حكم على شهادة منتهية.
    """
    parsed = submission.parse_date("1447/03/15 هـ")
    assert parsed is not None
    assert parsed.year == 2025 and parsed.month == 9


@hijri_only
def test_hijri_day_first_order(submission):
    assert submission.parse_date("15/03/1447هـ") == submission.parse_date("1447/03/15 هـ")


@hijri_only
def test_hijri_deadline_inside_a_sentence(submission):
    deadline = submission.deadline_date(
        {"submission_deadline": "آخر موعد لتقديم العروض 1447/03/15هـ الساعة 12 ظهراً"}
    )
    assert deadline is not None and deadline.year == 2025


@hijri_only
def test_expiry_before_hijri_deadline_is_flagged(submission):
    """الشهادة تنتهي قبل موعد مكتوب هجرياً — يجب أن تُرصد كما تُرصد مع الميلادي."""
    import pandas as pd

    df = pd.DataFrame([{
        "المستند": "شهادة الزكاة والضريبة",
        "مرجع البند": "5-2",
        "إلزامي": True,
        "لدينا": "نعم",
        "تاريخ الانتهاء": "2025-08-01",
        "مرفق في المظروف": True,
        "ملاحظات": "",
    }])
    summary = submission.submission_summary(df, {"submission_deadline": "1447/03/15هـ"})
    assert summary["expiring"], "شهادة منتهية قبل موعد هجري لم تُرصد"


def test_hijri_is_never_read_as_gregorian(submission):
    """
    القاعدة الحاكمة: تاريخ موسوم بالهجري لا يُقرأ ميلادياً بحال. بدونها يصير
    1447/03/15 موعداً في القرن الخامس عشر ويُبنى عليه حكم.
    """
    parsed = submission.parse_date("1447/03/15 هـ")
    assert parsed is None or parsed.year > 1900

    deadline = submission.deadline_date({"submission_deadline": "الموعد 1447/03/15 هـ"})
    assert deadline is None or deadline.year > 1900


def test_gregorian_still_parses(submission):
    """الإصلاح لا يمسّ المسار الميلادي."""
    assert submission.parse_date("2026-09-01") == datetime.date(2026, 9, 1)
    assert submission.parse_date("01/09/2026") == datetime.date(2026, 9, 1)
    assert submission.parse_date("") is None
    assert submission.parse_date("نص بلا تاريخ") is None


def test_gregorian_deadline_inside_a_sentence_still_works(submission):
    assert submission.deadline_date(
        {"submission_deadline": "آخر موعد 2026-09-01 الساعة 12 ظهراً"}
    ) == datetime.date(2026, 9, 1)


# ─── إعادة المحاولة على الفشل العابر ──────────────────────────────────────────


@pytest.fixture()
def engine(monkeypatch):
    from utils import ai_engine
    # لا انتظار فعلي في الاختبارات
    monkeypatch.setattr(ai_engine.time, "sleep", lambda *_: None)
    return ai_engine


class _Boom(Exception):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


def test_transient_errors_are_detected(engine):
    assert engine._is_transient(_Boom("503 Service Unavailable"))
    assert engine._is_transient(_Boom("RESOURCE_EXHAUSTED: quota"))
    assert engine._is_transient(_Boom("deadline exceeded"))
    assert engine._is_transient(_Boom("boom", code=429))


def test_permanent_errors_are_not_retried(engine):
    """مفتاح خاطئ أو طلب مرفوض لا يُصلحه الانتظار — إعادة المحاولة تهدر الوقت."""
    assert not engine._is_transient(_Boom("401 API key not valid"))
    assert not engine._is_transient(_Boom("PERMISSION_DENIED"))
    assert not engine._is_transient(ValueError("bad schema"))


def test_retry_recovers_from_a_transient_failure(engine):
    """
    العيب: استدعاء عابر فاشل كان يُسقط تحليلاً من عشرات الاستدعاءات، وقد
    استُهلك التوكن مرتين.
    """
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise _Boom("503 unavailable")
        return "ok"

    assert engine._with_retry(flaky) == "ok"
    assert attempts["n"] == 3


def test_retry_gives_up_and_reraises(engine):
    def always_down():
        raise _Boom("503 unavailable")

    with pytest.raises(_Boom):
        engine._with_retry(always_down)


def test_permanent_failure_is_raised_immediately(engine):
    attempts = {"n": 0}

    def denied():
        attempts["n"] += 1
        raise _Boom("PERMISSION_DENIED")

    with pytest.raises(_Boom):
        engine._with_retry(denied)
    assert attempts["n"] == 1, "أُعيدت المحاولة على خطأ دائم"


def test_retry_reports_progress_through_the_callback(engine):
    messages = []
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise _Boom("429 rate limit")
        return "ok"

    engine._with_retry(flaky, messages.append)
    assert messages, "لم يُبلَّغ المستخدم بإعادة المحاولة"


def test_call_survives_a_transient_failure(engine, fake_streamlit):
    """المسار الكامل: `_call` يُرجع النص رغم فشل أول محاولة."""
    from utils.providers import GenResult

    fake_streamlit.session_state["api_gemini"] = "test-key"
    attempts = {"n": 0}

    def flaky_run(model_id, prompt, schema=None, task="write"):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise _Boom("503 unavailable")
        return GenResult(text="النتيجة")

    engine.providers.run = flaky_run
    assert engine._call("prompt", "model-id") == "النتيجة"
    assert attempts["n"] == 2
