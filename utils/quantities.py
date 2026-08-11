"""
utils/quantities.py — الكميات المحسوبة واعتمادها (ب-5 · ن-22)

جدول الكميات كان ينقل ما في الكرّاس، وحين لا تُذكر كمية **يضع 1 صامتاً**.
الرقم يخرج في العرض بلا أن يعرف قارئه أنه لم يأتِ من أي مكان.

هذه الوحدة تجعل الاشتقاق **معلناً ومشروطاً بالموافقة**:

- كل كمية تحمل **مصدرها**: منقولة من الكرّاس · محسوبة · يدوية.
- الكمية المحسوبة تحمل **أساس احتسابها**: المعادلة ومن أين جاء كل رقم فيها.
  بلا الأساس لا قيمة للرقم — لا يُراجَع ولا يُدافَع عنه أمام لجنة الفحص.
- الكمية المحسوبة **لا تخرج في أي مستند حتى تُعتمد صراحةً**، والاعتماد يسقط
  إن تغيّر الرقم أو أساسه بعده.

**لماذا الأساس شرطُ وجود لا حقلٌ اختياري**: رقمٌ واثق بلا أساس أسوأ من فراغ.
الفراغ يدفع المهندس إلى الحساب، والرقم الواثق يُعتمد ثم يُحاسَب عليه في
التنفيذ. فبندٌ يعجز النموذج عن ذكر أساسٍ له يُردّ إلى «بلا كمية» ولا يُقترح.

**لا سعر هنا**: الأساس يشرح كيف اشتُقّت الكمية لا كم تكلّف. المظروف الفني
يبقى بلا رقم مالي.

No Streamlit here — pure logic, testable without a UI harness.
"""
import hashlib
from typing import Optional

from utils.state import (
    QTY_DERIVED,
    QTY_FROM_TENDER,
    QTY_MANUAL,
    QTY_SOURCE_OPTIONS,
)

# أقصر أساس مقبول. «محسوبة» أو «حسب الكراسة» ليست أساساً — الأساس يذكر
# المعادلة ومدخلاتها، ولا يفعل ذلك نصٌّ من ثلاث كلمات.
MIN_BASIS_LENGTH = 20

BASIS_COL = "أساس الاحتساب"
SOURCE_COL = "مصدر الكمية"
APPROVED_COL = "معتمَد"
QTY_COL = "الكمية"


def _records(df) -> list:
    if df is None or not hasattr(df, "to_dict"):
        return []
    try:
        return df.to_dict("records")
    except Exception:
        return []


def _text(row: dict, col: str) -> str:
    return " ".join(str(row.get(col, "") or "").split())


def is_derived(row: dict) -> bool:
    return _text(row, SOURCE_COL) == QTY_DERIVED


def is_approved(row: dict) -> bool:
    return bool(row.get(APPROVED_COL))


def has_basis(row: dict) -> bool:
    """أساسٌ يستحق الاسم: يذكر معادلةً ومدخلاتها لا كلمةً مبهمة."""
    return len(_text(row, BASIS_COL)) >= MIN_BASIS_LENGTH


def fingerprint(row: dict) -> str:
    """
    بصمة الرقم وأساسه — عليها يُعلَّق الاعتماد.

    اعتمادٌ على «500 رخصة، رخصة لكل موظف» ليس اعتماداً على «800 رخصة»، ولا على
    الرقم نفسه بأساسٍ آخر. بلا هذا الربط يصير الاعتماد ختماً على ورقة تُملأ
    بعده — نفس منطق `approvals` في 13-8 وسقوط اعتماد الكتلة في 14-4.
    """
    payload = "\x00".join((
        str(row.get(QTY_COL, "")),
        _text(row, BASIS_COL),
        _text(row, "البند"),
        _text(row, "الوحدة"),
    ))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def normalize(df):
    """
    يضبط المصدر والاعتماد على قيم متّسقة قبل العرض أو التصدير.

    ثلاث قواعد تُطبَّق هنا لا في الواجهة، فتسري على الجدول أيّاً كان مصدره
    (استخراج · استيراد منافسة محفوظة · تحرير يدوي):

    1. مصدرٌ غير معروف يُعامَل يدويّاً — لا يُفترض أنه اجتهاد نموذج فيُحجب.
    2. **محسوبة بلا أساس ليست محسوبة**: تُردّ يدويّة، فالفريق يملك رقمه.
    3. غير المحسوبة معتمدة دائماً — النقل من الكرّاس والكتابة اليدوية ليسا
       اجتهاداً يحتاج ختماً.
    """
    import pandas as pd

    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return df

    out = df.copy()
    for col, default in ((BASIS_COL, ""), (SOURCE_COL, QTY_MANUAL),
                         (APPROVED_COL, True)):
        if col not in out.columns:
            out[col] = default

    sources, approvals = [], []
    for row in out.to_dict("records"):
        source = _text(row, SOURCE_COL)
        if source not in QTY_SOURCE_OPTIONS:
            source = QTY_MANUAL
        if source == QTY_DERIVED and not has_basis(row):
            source = QTY_MANUAL
        sources.append(source)
        approvals.append(is_approved(row) if source == QTY_DERIVED else True)

    out[SOURCE_COL] = sources
    out[APPROVED_COL] = approvals
    return out


def pending(df) -> list:
    """
    الكميات المحسوبة التي تنتظر اعتماداً — ما تعرضه لوحة المراجعة.

    Returns:
        `[{"index", "item", "unit", "quantity", "basis", "fingerprint"}]`
    """
    items = []
    for i, row in enumerate(_records(normalize(df))):
        if is_derived(row) and not is_approved(row):
            items.append({
                "index": i,
                "item": _text(row, "البند"),
                "unit": _text(row, "الوحدة"),
                "quantity": row.get(QTY_COL, ""),
                "basis": _text(row, BASIS_COL),
                "fingerprint": fingerprint(row),
            })
    return items


def counts(df) -> dict:
    """عدّاد للواجهة: منقول · محسوب معتمَد · محسوب معلَّق."""
    rows = _records(normalize(df))
    derived = [r for r in rows if is_derived(r)]
    return {
        "total": len(rows),
        "from_tender": sum(1 for r in rows
                           if _text(r, SOURCE_COL) == QTY_FROM_TENDER),
        "derived": len(derived),
        "approved": sum(1 for r in derived if is_approved(r)),
        "pending": sum(1 for r in derived if not is_approved(r)),
    }


def approve(df, indexes=None, approved: bool = True):
    """
    يعتمد الكميات المحسوبة المحدَّدة (أو كلها إن لم تُحدَّد) أو يسحب اعتمادها.

    الاعتماد **فعل إنسان**: الواجهة تتحقق من الصلاحية قبل الاستدعاء، وهذه
    الوحدة لا تعرف من المستخدم ولا تفترض له صلاحية.
    """
    out = normalize(df)
    if out is None or out.empty:
        return out

    records = out.to_dict("records")
    targets = range(len(records)) if indexes is None else indexes
    flags = list(out[APPROVED_COL])

    for i in targets:
        if 0 <= i < len(records) and is_derived(records[i]):
            flags[i] = bool(approved)

    out[APPROVED_COL] = flags
    return out


def refresh_approvals(df, previous=None):
    """
    يُسقط اعتماد كل بند تغيّر رقمه أو أساسه منذ اعتماده.

    يُستدعى بعد كل تحرير للجدول: البصمة تُقارَن بما كانت عليه، فتعديل الكمية
    بعد اعتمادها يعيدها إلى الانتظار بدل أن تحمل ختماً لرقم آخر.
    """
    out = normalize(df)
    if out is None or out.empty:
        return out

    before = {}
    for row in _records(normalize(previous)):
        if is_derived(row) and is_approved(row):
            before[fingerprint(row)] = True

    flags = []
    for row in out.to_dict("records"):
        if not is_derived(row):
            flags.append(True)
        elif is_approved(row):
            # معتمَدٌ الآن ولم يكن معتمَداً بهذه البصمة ⇐ تغيّر بعد الاعتماد
            flags.append(fingerprint(row) in before if before else True)
        else:
            flags.append(False)

    out[APPROVED_COL] = flags
    return out


def export_df(df, drop_internal: bool = True):
    """
    الجدول كما يخرج في المستند: بلا الكميات المحسوبة غير المعتمدة.

    والأعمدة الثلاثة الداخلية تُسقَط — أساس الاحتساب أداة عملٍ داخلية، ونشره
    في العرض يكشف للجنة أي الأرقام اجتهادٌ منا وأيّها منقول عنها.
    """
    import pandas as pd

    out = normalize(df)
    if out is None or not isinstance(out, pd.DataFrame) or out.empty:
        return out

    keep = [
        not (is_derived(r) and not is_approved(r))
        for r in out.to_dict("records")
    ]
    out = out[pd.Series(keep, index=out.index)]

    if drop_internal:
        out = out.drop(columns=[c for c in (BASIS_COL, SOURCE_COL, APPROVED_COL)
                                if c in out.columns])
    return out


def blocking_note(df) -> Optional[str]:
    """
    تحذير التصدير حين تُحجب كميات — أو `None` إن لم يُحجب شيء.

    الحجب الصامت أسوأ من الرقم المشكوك فيه: فريقٌ يرى بنداً في الشاشة ولا
    يجده في المستند يظنّه عطلاً، فيصدّر ناقصاً وهو يحسبه كاملاً.
    """
    n = counts(df)["pending"]
    if not n:
        return None
    return (
        f"{n} كمية محسوبة لم تُعتمد بعد — لن تخرج في المستند. "
        "راجع أساس احتسابها واعتمدها أو صحّح الرقم يدوياً."
    )
