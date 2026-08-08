"""
utils/delivery.py — تحويل الفائز إلى مشروع (14-11).

نفوز، ثم يبدأ فريق التنفيذ من الصفر بقراءة عرضٍ من ثمانين صفحة ليعرف بماذا
التزمنا. وما يُنسى منه لا يُنسى على الجهة: بند وعدنا به في المنهجية ولم يصل خطة
التسليم يصير مخالفة عقدية بعد أشهر.

الوحدة خالية من Streamlit: تأخذ المصفوفة وأقسام العرض وتعيد التزامات مقترَحة.

**ثلاث قواعد تحكم الاستخراج:**

1. **مصدران بثقتين مختلفتين.** صفّ في مصفوفة الامتثال كتبناه بأنفسنا وأقررنا فيه
   بالالتزام — التزام **مؤكَّد** لا يحتاج مراجعة. أمّا جملة في نصّ قسم فاستنتاج
   يحتاج إقرار إنسان. وهذا امتداد لقاعدة المرحلة 12: الصفّ في السجل أقوى من أي
   نصّ حرّ.
2. **الاستخراج اقتراح لا قرار.** ما لم يُقَرّ يبقى `confirmed = 0` ويتصدّر
   القائمة: هو ما ينتظر قراراً، وما أُقرّ صار عملاً يُتابَع.
3. **لكل بند مرجعه.** مدير التنفيذ يسأل «لماذا نحن ملزمون بهذا؟» فيجد رقم
   المتطلب أو اسم القسم — لا ذاكرة أحد. بندٌ بلا مرجع لا يُستخرج أصلاً.
"""
import re
from typing import Optional

# أعمدة مصفوفة الامتثال التي يُبنى عليها الاستخراج
REQ_ID_COLUMN = "المعرّف"
REQ_TEXT_COLUMN = "المتطلب"
REQ_STATUS_COLUMN = "الالتزام"
REQ_CLAUSE_COLUMN = "مرجع البند"
REQ_STRATEGY_COLUMN = "استراتيجية الاستجابة"

# حالات الامتثال التي تعني **وعداً قطعناه**. «لا» ليست التزاماً،
# و«بانتظار التحقق» لم تُحسم — واستخراجها التزاماً يُنشئ تعهّداً لم نقطعه.
COMMITTED_STATUSES = ("نعم", "جزئي")

# صيغ الوعد في نصّ العرض. الاستخراج **لفظي لا نموذجي**: جملة تبدأ بها هي وعد
# صريح، والنموذج يُضيف هنا تخميناً بكلفة ولا يُضيف يقيناً.
_PROMISE_CUES = (
    "نلتزم", "سنلتزم", "نتعهد", "نتعهّد", "سنقوم", "سنوفّر", "سنوفر",
    "سنسلّم", "سنسلم", "نضمن", "سنضمن", "نوفّر", "نوفر", "سنقدّم", "سنقدم",
    "we commit", "we will deliver", "we guarantee", "we will provide",
)

# أقصى طول لعنوان بند التسليم — الفقرة كاملةً ليست بنداً يُتابَع
_TITLE_LIMIT = 160

# أدنى طول للجملة تُعدّ عندها وعداً. «نلتزم بذلك.» ليست بنداً.
_MIN_PROMISE_WORDS = 5


def _rows(df) -> list:
    """صفوف المصفوفة كقواميس — يقبل DataFrame أو قائمة أو None."""
    if df is None:
        return []
    if hasattr(df, "to_dict"):
        try:
            return df.to_dict("records")
        except (TypeError, ValueError):
            return []
    return list(df) if isinstance(df, (list, tuple)) else []


def _clean(text) -> str:
    return " ".join(str(text or "").split())


def _shorten(text: str, limit: int = _TITLE_LIMIT) -> str:
    body = _clean(text)
    return body if len(body) <= limit else body[:limit].rstrip() + "…"


def commitments_from_matrix(df) -> list:
    """
    الالتزامات المأخوذة من مصفوفة الامتثال — **مؤكَّدة**.

    هذه أقررنا بها بأنفسنا صفّاً صفّاً، فلا تحتاج مراجعة ثانية. و«لا» ليست
    التزاماً، و«بانتظار التحقق» لم تُحسم — استخراجها يُنشئ تعهّداً لم نقطعه.

    Returns:
        `[{"title", "source", "source_ref", "clause_ref", "confirmed"}]`
    """
    out = []
    for row in _rows(df):
        status = _clean(row.get(REQ_STATUS_COLUMN))
        if status not in COMMITTED_STATUSES:
            continue
        title = _clean(row.get(REQ_TEXT_COLUMN))
        if not title:
            continue
        # الاستراتيجية توضّح **كيف** نفي بالجزئي — بدونها يبقى البند غامضاً
        strategy = _clean(row.get(REQ_STRATEGY_COLUMN))
        if status == "جزئي" and strategy:
            title = f"{title} — {strategy}"
        out.append({
            "title": _shorten(title),
            "source": "matrix",
            "source_ref": _clean(row.get(REQ_ID_COLUMN)),
            "clause_ref": _clean(row.get(REQ_CLAUSE_COLUMN)),
            "confirmed": True,
        })
    return out


def _promises(text: str) -> list:
    """جمل الوعد الصريح في نصّ قسم."""
    body = _clean(text)
    if not body:
        return []

    found = []
    for sentence in re.split(r"(?<=[.؟!?])\s+|\n+", body):
        candidate = sentence.strip(" -•*\t")
        if len(candidate.split()) < _MIN_PROMISE_WORDS:
            continue
        lowered = candidate.lower()
        if any(cue.lower() in lowered for cue in _PROMISE_CUES):
            found.append(candidate)
    return found


def commitments_from_sections(sections: list, content_of) -> list:
    """
    الوعود الصريحة في نصّ الأقسام — **اقتراحات تنتظر إقرار إنسان**.

    الاستخراج لفظي لا نموذجي: صيغة «نلتزم» و«سنسلّم» وعدٌ صريح، والنموذج هنا
    يُضيف تخميناً بكلفة ولا يُضيف يقيناً — ولو أخطأ صار **تعهّداً مخترعاً** في
    قائمة يُبنى عليها التنفيذ، وهو ما تمنعه القاعدة الثالثة من القواعد الثابتة.

    Args:
        content_of: دالّة `key -> نصّ القسم` — الوحدة لا تعرف من أين يأتي.
    """
    out = []
    seen = set()
    for section in sections or []:
        if not section.get("include", True):
            continue
        key = str(section.get("key", "") or "")
        title = _clean(section.get("title")) or key
        for promise in _promises(content_of(key) if key else ""):
            short = _shorten(promise)
            marker = short.lower()
            if marker in seen:
                continue
            seen.add(marker)
            out.append({
                "title": short,
                "source": "section",
                "source_ref": key,
                "clause_ref": title,
                "confirmed": False,
            })
    return out


def extract_commitments(df, sections: list, content_of) -> list:
    """
    كل الالتزامات المقترَحة: المصفوفة أولاً (مؤكَّدة) ثم نصّ الأقسام.

    التكرار يُسقَط بالعنوان: متطلب في المصفوفة كُتب وعداً في القسم أيضاً بندٌ
    واحد لا اثنان، ويُحتفظ بنسخة **المصفوفة** لأنها تحمل مرجع البند.
    """
    matrix = commitments_from_matrix(df)
    seen = {item["title"].lower() for item in matrix}

    out = list(matrix)
    for item in commitments_from_sections(sections, content_of):
        if item["title"].lower() in seen:
            continue
        seen.add(item["title"].lower())
        out.append(item)
    return out


def can_convert(project: Optional[dict]) -> bool:
    """
    هل تصلح هذه المنافسة للتحويل؟ **الفائزة وحدها**.

    تحويل خاسرة أو معلَّقة يُنشئ خطة تسليم لعملٍ لم نفز به، ويُدخل في لوحة
    التنفيذ التزامات لا تخصّ أحداً. والنتيجة واقعة يسجّلها إنسان (المرحلة 10)،
    فالشرط قراءةٌ لها لا حكمٌ من عندنا.
    """
    from utils import history

    if not project:
        return False
    return _clean(project.get("outcome")) == history.OUTCOME_WON


def summary(deliverables: list) -> dict:
    """عدّادات لوحة التسليم: الإجمالي · بانتظار الإقرار · المفتوح · المنجز."""
    items = deliverables or []
    return {
        "total": len(items),
        "unconfirmed": sum(1 for d in items if not d.get("confirmed")),
        "open": sum(1 for d in items
                    if d.get("status") == "open" and d.get("confirmed")),
        "done": sum(1 for d in items if d.get("status") == "done"),
        "from_matrix": sum(1 for d in items if d.get("source") == "matrix"),
    }
