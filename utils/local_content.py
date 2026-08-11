"""
utils/local_content.py — درجة المحتوى المحلي والسعودة (12-8)

الكراسات السعودية تشترط نسبة محتوى محلي، والعروض تردّ عليها بجملة: «نلتزم
بمتطلبات المحتوى المحلي». تلك الجملة لا تُقاس ولا تُقارن بالحد المطلوب، فلا
يعرف فريق العطاء أين يقف حتى تُعلن النتيجة.

هنا يُحسب **رقم صريح** من معطيات موجودة أصلاً في النظام: نطاق السعودة من ملف
الشركة، ونصيب البنود المدرجة في القائمة الإلزامية من جدول الكميات، والموردون
ذوو الدعم المحلي من سجل الموردين.

**الرقم تقدير داخلي للتخطيط لا شهادة محتوى محلي.** الاحتساب الرسمي منهجية
تصدرها هيئة المحتوى المحلي وتُدقَّق بمستندات؛ ما هنا يقرّب الصورة ليُعرف حجم
الفجوة مبكراً. الوحدة تعلن ذلك في مخرجها (`is_estimate`) وتعرضه الواجهة.

الوحدة خالية من Streamlit ليُختبر حسابها وحده.
"""
import re
from typing import Optional

# أوزان المكوّنات. مجموعها 1.0، وهي **تقدير تخطيطي** لا أوزان نظامية:
# السعودة أثقل لأنها الأكثر تكراراً كشرط صريح في الكراسات.
WEIGHTS = {"saudization": 0.5, "mandatory_items": 0.3, "local_support": 0.2}

# نطاقات السعودة ودرجتها التقريبية (0–100)
NITAQAT_BANDS = {
    "بلاتيني": 100.0,
    "أخضر مرتفع": 85.0,
    "أخضر متوسط": 70.0,
    "أخضر منخفض": 55.0,
    "أصفر": 30.0,
    "أحمر": 0.0,
}
BAND_OPTIONS = ["غير محدد"] + list(NITAQAT_BANDS)


def band_score(band: str) -> Optional[float]:
    """درجة النطاق، أو None إن لم يُحدَّد — لا نفترض نطاقاً."""
    return NITAQAT_BANDS.get(str(band or "").strip())


_PERCENT_RE = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s*(?:%|٪|بالمئة|في المئة|بالمائة)")


def required_percentage(text: str) -> Optional[float]:
    """
    الحد المطلوب من نص الكراسة (مثل «لا تقل نسبة المحتوى المحلي عن 40%»).

    يُرجع None إن لم يرد رقم — وغيابه يعني «غير معلن في الكراسة» لا صفراً.
    أعلى نسبة مذكورة هي المُعتمدة: الكراسات تذكر نسباً فرعية، والحد الأعلى
    هو ما يُقاس عليه القبول.
    """
    values = []
    for match in _PERCENT_RE.finditer(str(text or "")):
        try:
            value = float(match.group(1).replace(",", "."))
        except ValueError:
            continue
        if 0 <= value <= 100:
            values.append(value)
    return max(values) if values else None


def mandatory_share(boq_rows: list) -> Optional[float]:
    """نصيب بنود القائمة الإلزامية من جدول الكميات، أو None إن لا جدول."""
    rows = [r for r in boq_rows or [] if str(r.get("البند", "")).strip()]
    if not rows:
        return None
    flagged = sum(1 for r in rows if bool(r.get("القائمة الإلزامية")))
    return flagged / len(rows) * 100.0


def local_support_share(vendors: list) -> Optional[float]:
    """نصيب الموردين ذوي الدعم المحلي، أو None إن لا سجل موردين."""
    rows = [v for v in vendors or [] if str(v.get("vendor", "")).strip()]
    if not rows:
        return None
    supported = sum(1 for v in rows if bool(v.get("local_support")))
    return supported / len(rows) * 100.0


def score(band: str, boq_rows: list, vendors: list,
          requirement_text: str = "") -> dict:
    """
    يحسب الدرجة التقديرية وفجوتها عن الحد المطلوب.

    المكوّن الذي لا معطيات له **يُستبعد من الحساب ولا يُحتسب صفراً**، ويُعاد
    وزنه على البقية: صفر عن غياب بيانات يُنتج درجة متشائمة كاذبة يُبنى عليها
    قرار انسحاب. ويُعلَن المكوّن الناقص في `missing` ليُعرف مصدر النقص.
    """
    components = {
        "saudization": band_score(band),
        "mandatory_items": mandatory_share(boq_rows),
        "local_support": local_support_share(vendors),
    }
    available = {k: v for k, v in components.items() if v is not None}
    missing = [k for k, v in components.items() if v is None]

    total_weight = sum(WEIGHTS[k] for k in available)
    estimate = (
        sum(WEIGHTS[k] * v for k, v in available.items()) / total_weight
        if total_weight else None
    )

    required = required_percentage(requirement_text)
    gap = (required - estimate) if (required is not None and estimate is not None) else None

    return {
        "components": components,
        "missing": missing,
        "estimate": estimate,
        "required": required,
        "gap": gap if (gap is None or gap > 0) else 0.0,
        "meets": None if gap is None else gap <= 0,
        "is_estimate": True,
    }
