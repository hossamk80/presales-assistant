"""
utils/orders.py — بناء أمر البيع من المنافسة الفائزة (ب-6)

هذه أول وحدة في النظام **تكتب في نظام لا نملكه**. كل ما سبق يقرأ أو يُصدِّر
ملفاً يراه المستخدم قبل إرساله؛ وهنا يصير الضغط على زرّ صفّاً في دفاتر العميل
المحاسبية. فالحراسة هنا ليست تشدّداً: خطأٌ يخرج من الشاشة ولا يُدرَك.

**خمس بوابات، وكلها قبل أن يغادر شيء:**

1. **الفائزة وحدها.** أمر بيع لمنافسة لم نفز بها التزامٌ لم يقع.
2. **لا كمية غير معتمدة.** الكمية التي اشتقّها النموذج ولم يعتمدها إنسان
   محجوبة عن المستند (ب-5) — ودخولها دفاتر العميل أسوأ: تُفوتَر.
3. **لا سعر.** جدول الكميات في هذا النظام بلا أسعار عمداً، والتسعير عمل
   الفريق المالي في نظامه. نرسل **ما نلتزم بتسليمه**، والسعر يُدخَل هناك.
4. **مسودّة لا أمراً مؤكَّداً.** التأكيد فعلٌ تجاري يخصّ من يملك النظام.
5. **مرة واحدة.** أمر بيع مكرَّر في دفاتر عميل فوضى مالية حقيقية — يُمنع
   بالتخزين لا بالواجهة (انظر `db.connector_order`).

No Streamlit here — pure logic, testable without a UI harness.
"""
import hashlib
from typing import Optional

from utils.history import OUTCOME_WON

# أقصى عدد بنود في أمر واحد. جدولٌ بألف بند يعني خطأً في الاستخراج لا أمراً
# حقيقياً — والدفع بلا حدّ يملأ نظام العميل قبل أن يلاحظ أحد.
MAX_LINES = 300

# طول عنوان البند في نظام العميل. الوصف الكامل يذهب إلى حقل الوصف.
_NAME_LIMIT = 200


class OrderRefused(Exception):
    """سبب رفض البناء — يُعرض للمستخدم بنصّه ولا يُبتلع."""


def _text(value) -> str:
    return " ".join(str(value or "").split())


def reference(project: dict) -> str:
    """
    مرجع الأمر كما يظهر في نظام العميل.

    يحمل معرّف المنافسة عندنا: من يفتح الأمر بعد سنة يعرف من أين جاء، ومن
    يبحث عندنا يجد ما صار إليه. مرجعٌ بلا رابط يجعل التتبّع ذاكرةَ أشخاص.
    """
    pid = project.get("id")
    name = _text(project.get("name")) or "منافسة"
    return f"BID-{pid}-{name}"[:80]


def lines_from_boq(df_boq) -> list:
    """
    بنود الأمر من جدول الكميات — بلا الكميات غير المعتمدة وبلا أسعار.

    يمرّ بـ `quantities.export_df` نفسها التي يمرّ بها المستند: بابٌ واحد
    للخروج، فلا تُفتح للدفع كوّة لا تمرّ بها الحراسة (ب-5).
    """
    from utils import quantities

    exported = quantities.export_df(df_boq)
    if exported is None or getattr(exported, "empty", True):
        return []

    lines = []
    for row in exported.to_dict("records"):
        name = _text(row.get("البند"))
        if not name:
            continue
        try:
            qty = float(row.get("الكمية", 0) or 0)
        except (TypeError, ValueError):
            qty = 0.0
        if qty <= 0:
            # كمية صفر ليست بنداً يُسلَّم؛ وسالبةٌ خطأ إدخال لا مرتجَع
            continue
        lines.append({
            "name": name[:_NAME_LIMIT],
            "quantity": qty,
            "unit": _text(row.get("الوحدة")),
            "description": _text(row.get("الوصف")) or _text(row.get("المواصفات")),
            "code": _text(row.get("كود البناء")),
        })
    return lines


def build(project: dict, df_boq, customer: str = "") -> dict:
    """
    يبني حمولة الأمر أو يرفع `OrderRefused` بسبب مقروء.

    الرفض **بسببه** لا بـ`None`: مستخدمٌ يُمنع بلا أن يُقال له لماذا يُعيد
    المحاولة أو يلتفّ على المنع يدوياً في نظام العميل.
    """
    outcome = _text(project.get("outcome"))
    if outcome != OUTCOME_WON:
        raise OrderRefused(
            f"أمر البيع للمنافسة الفائزة وحدها — حالة هذه: "
            f"«{outcome or 'غير محدّدة'}»."
        )

    lines = lines_from_boq(df_boq)
    if not lines:
        raise OrderRefused(
            "لا بنود صالحة في جدول الكميات. تحقّق من الكميات المحسوبة "
            "غير المعتمدة — لا تخرج حتى تُعتمد."
        )
    if len(lines) > MAX_LINES:
        raise OrderRefused(
            f"{len(lines)} بنداً تتجاوز الحدّ ({MAX_LINES}). "
            "راجع جدول الكميات — هذا العدد يرجّح خطأ استخراج."
        )

    customer = _text(customer) or _text(project.get("entity_name"))
    if not customer:
        raise OrderRefused("الجهة المشترية غير محدَّدة — الأمر بلا عميل لا يُنشأ.")

    return {
        "reference": reference(project),
        "customer": customer,
        "project_id": project.get("id"),
        "lines": lines,
        # الحالة تُرسل صراحةً ولا تُترك لافتراض الخادم
        "state": "draft",
        # لا حقل سعر في الحمولة أصلاً — لا يُنسى ولا يُملأ سهواً
        "priced": False,
    }


def fingerprint(order: dict) -> str:
    """
    بصمة ما أُرسل. تُخزَّن مع الأمر فيُعرف لاحقاً أن الجدول تغيّر بعده.

    الأمر لا يُعاد إرساله تلقائياً عند التغيّر — تصحيحه في نظام العميل عملُ
    من يملكه. لكن **أن يُقال إنه تغيّر** خبرٌ لا يُكتم.
    """
    payload = "\x00".join(
        f'{line["name"]}|{line["quantity"]}|{line["unit"]}'
        for line in order.get("lines", [])
    )
    payload = f'{order.get("customer", "")}\x00{payload}'
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def summary(order: dict) -> dict:
    """معاينة ما سيُكتب — تُعرض قبل الضغط لا بعده."""
    lines = order.get("lines", [])
    return {
        "reference": order.get("reference", ""),
        "customer": order.get("customer", ""),
        "line_count": len(lines),
        "total_quantity": sum(line["quantity"] for line in lines),
        "priced": bool(order.get("priced")),
    }


def drift(order: dict, stored_fingerprint: Optional[str]) -> bool:
    """هل تغيّر جدول الكميات منذ الدفع؟"""
    if not stored_fingerprint:
        return False
    return fingerprint(order) != stored_fingerprint
