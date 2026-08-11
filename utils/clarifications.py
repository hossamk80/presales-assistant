"""
utils/clarifications.py — وحدة الاستفسارات (14-9).

بند غامض في الكرّاس يُرصد في المصفوفة، فيُكتب سؤال في بريد أو ورقة ثم يُنسى.
الموعد يمرّ، ولا أحد يعرف أنّ متطلباً حرجاً بُني على **فهمنا** له لا على جواب
الجهة. وغيابُ الجواب أخطر من ورودِه مخالفاً لتوقّعنا: المخالف يُعالَج، والغائب
يُبنى عليه صامتاً.

هذه الوحدة خالية من Streamlit: تأخذ صفوف الاستفسارات وصفوف المصفوفة وتعيد
أحكاماً — فتُختبر بلا تركيب واجهة.

**قاعدتان تحكمان كل حكم هنا:**

1. **سؤال لم يُرسَل غيابُ جوابه ذنبنا لا ذنب الجهة.** رصده «متأخّراً عن الجهة»
   يُخفي أنّنا لم نسأل بعد، وهو ما يُصلَح بالإرسال لا بالانتظار.
2. **الغائب لا يُفترَض.** استفسار بلا جواب على متطلب حرج يُعرض مخاطرةً صريحة،
   ولا يُعامَل كأنّ الجواب جاء مطابقاً لما نرجوه. وهذا امتداد لقاعدة المنتج:
   الجاهزية أضعف زاوية لا المتوسط، وقرار الامتثال بشري.
"""
from datetime import date
from typing import Optional

# الأهمية التي يصير عندها غياب الجواب مخاطرة حرجة لا ملاحظة.
# نفس العتبة المستعملة في `utils/traceability.py` فلا معياران للحرِج.
from utils.traceability import BLOCKING_CRITICALITY

# عمود معرّف المتطلب في مصفوفة الامتثال، وعمودا أهميته ونصّه.
REQ_ID_COLUMN = "المعرّف"
REQ_CRITICALITY_COLUMN = "الأهمية"
REQ_TEXT_COLUMN = "المتطلب"

# كم يوماً قبل الموعد يُعدّ السؤال «مستحقّاً قريباً» فيُنبَّه عليه.
DUE_SOON_DAYS = 3


def _matrix_rows(df) -> list:
    """صفوف المصفوفة كقواميس — يقبل DataFrame أو قائمة أو None."""
    if df is None:
        return []
    if hasattr(df, "to_dict"):
        try:
            return df.to_dict("records")
        except (TypeError, ValueError):
            return []
    return list(df) if isinstance(df, (list, tuple)) else []


def requirement_index(df) -> dict:
    """معرّف المتطلب ← صفّه في المصفوفة. المعرّفات الفارغة تُسقَط."""
    index = {}
    for row in _matrix_rows(df):
        key = str(row.get(REQ_ID_COLUMN, "") or "").strip()
        if key:
            index[key] = row
    return index


def linked_requirement(clarification: dict, df) -> Optional[dict]:
    """
    صفّ المصفوفة الذي يخصّه الاستفسار، أو `None`.

    `None` تعني «غير مرتبط» لا «غير موجود»: السؤال أُرسل إلى الجهة فعلاً، فحذف
    صفّ عندنا لا يمحو واقعة إرساله ولا يُخفيه من اللوحة.
    """
    req_id = str(clarification.get("req_id", "") or "").strip()
    if not req_id:
        return None
    return requirement_index(df).get(req_id)


def is_blocking(clarification: dict, df) -> bool:
    """هل الاستفسار على متطلب **حرج**؟"""
    row = linked_requirement(clarification, df)
    if row is None:
        return False
    return str(row.get(REQ_CRITICALITY_COLUMN, "") or "").strip() == \
        BLOCKING_CRITICALITY


def days_left(clarification: dict, today: Optional[date] = None) -> Optional[int]:
    """
    الأيام حتى موعد الجواب — سالبة إن مضى، و`None` بلا موعد أو بموعد لم يُقرأ.

    التاريخ يُقرأ بـ `records.parse_date`: كرّاسات الجهات تؤرّخ هجرياً كثيراً
    بلا وسم، وقارئ ميلادي وحده يقرأ «1448-11-14» ماضياً سحيقاً فيُعدّ كل سؤال
    متأخّراً. وتاريخ تعذّرت قراءته **لا يُعدّ فائتاً ولا قائماً** — يبقى قرار
    البشر، فالحكم بتخمين تاريخ يُبنى عليه قرار تسليم.
    """
    from utils import records

    raw = str(clarification.get("due_at", "") or "").strip()
    if not raw:
        return None
    parsed = records.parse_date(raw)
    if parsed is None:
        return None
    return (parsed - (today or date.today())).days


def pending(clarifications: list) -> list:
    """
    ما لم يُجَب بعد ولم يُغلَق — المسودّات والمُرسَل.

    المسودّة **داخلة** عمداً: سؤال كُتب ولم يُرسَل هو أخطر الحالات، لأنّه يبدو
    مُعالَجاً في القائمة ولا أحد ينتظره من الجهة.
    """
    from utils import db

    return [
        c for c in clarifications or []
        if str(c.get("status", "") or "") in (db.CLARIFY_DRAFT, db.CLARIFY_SENT)
    ]


def unsent(clarifications: list) -> list:
    """المسودّات: غياب جوابها ذنبنا لا ذنب الجهة."""
    from utils import db

    return [c for c in clarifications or []
            if str(c.get("status", "") or "") == db.CLARIFY_DRAFT]


def overdue(clarifications: list, today: Optional[date] = None) -> list:
    """
    ما **أُرسل** ومضى موعده بلا جواب.

    المسودّات مستبعدة هنا بقصد (القاعدة الأولى): موعدٌ مضى على سؤال لم نُرسله
    ليس تأخّراً من الجهة، وخلطهما يجعل اللوحة تشكو مِمّن لم يُسأل.
    """
    from utils import db

    out = []
    for item in clarifications or []:
        if str(item.get("status", "") or "") != db.CLARIFY_SENT:
            continue
        left = days_left(item, today)
        if left is not None and left < 0:
            out.append(item)
    return out


def due_soon(clarifications: list, today: Optional[date] = None,
             within: int = DUE_SOON_DAYS) -> list:
    """ما أُرسل ويستحقّ جوابه خلال أيام — تنبيه قبل أن يصير تأخّراً."""
    from utils import db

    out = []
    for item in clarifications or []:
        if str(item.get("status", "") or "") != db.CLARIFY_SENT:
            continue
        left = days_left(item, today)
        if left is not None and 0 <= left <= within:
            out.append(item)
    return out


def risks(clarifications: list, df, today: Optional[date] = None) -> list:
    """
    المخاطر التي يجب أن تُرى قبل التسليم — الأشدّ أولاً.

    الحكم على **الحرِج بلا جواب** لا على كل معلَّق: قائمة تشكو من كل سؤال لم
    يُجَب تُهمَل، وتُهمَل معها الثلاثة التي كانت تستحقّ التوقّف.

    Returns:
        `[{"kind", "severity", "message", "clarification"}]`.
        فارغة تعني لا مخاطرة **مرصودة**، لا أنّ كل شيء محسوم.
    """
    findings = []

    for item in unsent(clarifications):
        blocking = is_blocking(item, df)
        findings.append({
            "kind": "not_sent",
            "severity": "حرجة" if blocking else "تنبيه",
            "message": (
                f"استفسار لم يُرسَل بعد{_req_suffix(item)}: "
                f"{_short(item.get('question'))}"
            ),
            "clarification": item,
        })

    for item in overdue(clarifications, today):
        blocking = is_blocking(item, df)
        late = abs(days_left(item, today) or 0)
        findings.append({
            "kind": "overdue",
            "severity": "حرجة" if blocking else "تنبيه",
            "message": (
                f"مضى {late} يوماً على موعد جواب استفسار{_req_suffix(item)} "
                f"بلا جواب: {_short(item.get('question'))}"
            ),
            "clarification": item,
        })

    # الحرِج أولاً، ثم غير المُرسَل قبل المتأخّر: الأول بيدنا والثاني بيد الجهة
    order = {"not_sent": 0, "overdue": 1}
    findings.sort(key=lambda f: (f["severity"] != "حرجة", order[f["kind"]]))
    return findings


def _req_suffix(clarification: dict) -> str:
    req_id = str(clarification.get("req_id", "") or "").strip()
    return f" على المتطلب {req_id}" if req_id else ""


def _short(text, limit: int = 90) -> str:
    body = " ".join(str(text or "").split())
    return body if len(body) <= limit else body[:limit].rstrip() + "…"


def answers_block(clarifications: list) -> str:
    """
    أجوبة الجهة كمقطع سياق يُحقن في كتابة الأقسام.

    **المُجاب وحده يدخل هنا.** جواب الجهة الرسمي يعلو على فهمنا للبند الغامض،
    فحقنه هو ثمرة السؤال كلّه. أمّا المعلَّق فلا يُحقن بأي صيغة: تمريره ولو
    موسوماً بـ«بانتظار الجواب» يجعل النموذج يبني عليه، وهو عين ما يمنعه هذا
    البند — الغائب لا يُفترَض.
    """
    from utils import db

    lines = []
    for item in clarifications or []:
        if str(item.get("status", "") or "") != db.CLARIFY_ANSWERED:
            continue
        answer = str(item.get("answer", "") or "").strip()
        if not answer:
            continue
        head = "- سؤالنا"
        req_id = str(item.get("req_id", "") or "").strip()
        if req_id:
            head += f" على المتطلب {req_id}"
        lines.append(f"{head}: {_short(item.get('question'), 200)}\n  جواب الجهة: {answer}")

    if not lines:
        return ""
    return (
        "\n\n--- أجوبة الجهة على استفساراتنا (تعلو على أي فهم مخالف للبند) ---\n"
        + "\n".join(lines)
        + "\nهذه أجوبة رسمية: اعتمدها حيث تعارضت مع ظاهر نص الكرّاس، ولا تخترع "
          "جواباً لسؤال لم يُذكر هنا."
    )


def summary(clarifications: list, df, today: Optional[date] = None) -> dict:
    """عدّادات تعرضها الشاشة: الإجمالي · المعلَّق · غير المُرسَل · المتأخّر · الحرِج."""
    from utils import db

    items = clarifications or []
    answered = [c for c in items
                if str(c.get("status", "") or "") == db.CLARIFY_ANSWERED]
    late = overdue(items, today)
    return {
        "total": len(items),
        "pending": len(pending(items)),
        "unsent": len(unsent(items)),
        "overdue": len(late),
        "due_soon": len(due_soon(items, today)),
        "answered": len(answered),
        "blocking": sum(1 for c in pending(items) if is_blocking(c, df)),
    }
