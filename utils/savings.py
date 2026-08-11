"""
utils/savings.py — سجل ما وفّرته المعالجة المحلية.

كل تحسين في الكلفة بلا قياس دعوى. هذا السجل يُقيّد لكل استدعاء: كم كان سيُرسَل
لو مرّ النص خاماً، وكم أُرسل فعلاً، وبأي وسيلة اختصرنا الفرق — تنظيف، أو
استرجاع لفظي، أو ذاكرة نتائج، أو قراءة جدول من الملف بلا نموذج أصلاً.

السجل في حالة الجلسة لا في قاعدة البيانات: هو مقياس تشغيل لا بيان عطاء، ولا
معنى لبقائه بعد إغلاق التطبيق. (قياس الاستهلاك الفعلي من عدّاد الموفّر مهمة
مستقلة — البند 11-7 في الخطة.)
"""
import streamlit as st

LEDGER_KEY = "_savings_ledger"

# وسائل التوفير — كل واحدة تُعرض على حدة ليُعرف أيّها يعمل فعلاً
METHOD_CLEANUP = "cleanup"
METHOD_RETRIEVAL = "retrieval"
METHOD_CACHE = "cache"
METHOD_LOCAL_PARSE = "local_parse"
METHOD_DEDUPE = "dedupe"

METHODS = (METHOD_CLEANUP, METHOD_RETRIEVAL, METHOD_CACHE,
           METHOD_LOCAL_PARSE, METHOD_DEDUPE)


def _ledger() -> dict:
    ledger = st.session_state.get(LEDGER_KEY)
    if not isinstance(ledger, dict):
        ledger = {"calls": 0, "avoided_calls": 0, "chars_before": 0,
                  "chars_after": 0, "by_method": {m: 0 for m in METHODS}}
        st.session_state[LEDGER_KEY] = ledger
    ledger.setdefault("by_method", {m: 0 for m in METHODS})
    for method in METHODS:
        ledger["by_method"].setdefault(method, 0)
    return ledger


def record(method: str, chars_before: int, chars_after: int,
           avoided_call: bool = False):
    """
    يقيّد توفيراً واحداً.

    `avoided_call` للحالات التي لم يُستدعَ فيها النموذج إطلاقاً — ذاكرة النتائج
    وقراءة الجدول محلياً. تلك أثمن من تقليص السياق: توفّر الاستدعاء كله.
    """
    ledger = _ledger()
    before, after = max(0, int(chars_before)), max(0, int(chars_after))
    ledger["chars_before"] += before
    ledger["chars_after"] += after
    if method in ledger["by_method"]:
        ledger["by_method"][method] += max(0, before - after)
    if avoided_call:
        ledger["avoided_calls"] += 1
    else:
        ledger["calls"] += 1


def summary() -> dict:
    """
    خلاصة الجلسة بالتوكن.

    التحويل من الأحرف إلى التوكن تقدير محلي (`CHARS_PER_TOKEN`) لا رقم فاتورة —
    يكفي للمقارنة قبل وبعد، ولا يُقدَّم على أنه محاسبة.
    """
    from utils.ai_engine import CHARS_PER_TOKEN

    ledger = _ledger()
    saved_chars = max(0, ledger["chars_before"] - ledger["chars_after"])
    return {
        "calls": ledger["calls"],
        "avoided_calls": ledger["avoided_calls"],
        "tokens_before": int(ledger["chars_before"] / CHARS_PER_TOKEN),
        "tokens_after": int(ledger["chars_after"] / CHARS_PER_TOKEN),
        "tokens_saved": int(saved_chars / CHARS_PER_TOKEN),
        "ratio": (saved_chars / ledger["chars_before"]) if ledger["chars_before"] else 0.0,
        "by_method": {
            method: int(chars / CHARS_PER_TOKEN)
            for method, chars in ledger["by_method"].items()
        },
    }


def reset():
    st.session_state[LEDGER_KEY] = None
