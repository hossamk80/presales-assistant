"""
utils/timeline.py — الجدول الزمني: التحقّق والرسم.

الجدول الزمني قسم إلزامي تُقيّمه لجان اعتماد بمعيار مستقل، وكان يخرج من النظام
نصاً حراً: بلا مراحل ولا اعتماديات ولا معالم قابلة للتحقق. هذه الوحدة تفحص
الخطة المُهيكلة وترسمها، وهي خالية من Streamlit لتُستدعى من الشاشة ومن بنّاء
المستند معاً.

**قاعدة حاكمة**: عمود «معلم دفع» علامة داخلية لا تُصدَّر. الفني والمالي مظروفان
منفصلان، ومخطط يحمل معالم الدفع داخل العرض الفني يُسقطه فاحص المظاريف.
"""
import re
from typing import Optional

import pandas as pd

# أعمدة تبقى داخل النظام ولا تدخل المستند الفني المصدَّر
EXPORT_EXCLUDED_COLUMNS = ("معلم دفع",)

# أقصى عدد أعمدة زمنية في المخطط قبل التجميع إلى أشهر — أعرض من ذلك لا يتّسع
# في صفحة A4 فيخرج مضغوطاً غير مقروء.
MAX_GANTT_COLUMNS = 16
WEEKS_PER_MONTH = 4

# وحدات المدة ومقابلها بالأسابيع. الشهر أربعة أسابيع تقريباً — تقريب مقصود
# لأن الكراسات تكتب المدة بالأشهر والخطة تُبنى بالأسابيع.
_DURATION_UNITS = (
    (("أسبوع", "أسابيع", "اسبوع", "اسابيع", "week"), 1),
    (("شهر", "أشهر", "اشهر", "شهور", "month"), WEEKS_PER_MONTH),
    (("سنة", "سنوات", "سنه", "عام", "أعوام", "year"), 52),
    (("يوم", "أيام", "ايام", "day"), 0),          # تُحسب بالقسمة أدناه
)

# أعداد عربية مكتوبة بالحروف ترد كثيراً في الكراسات («اثنا عشر شهراً»)
_ARABIC_NUMERALS = {
    "واحد": 1, "شهر واحد": 1, "شهرين": 2, "اثنين": 2, "اثنان": 2, "اثني": 2,
    "ثلاثة": 3, "ثلاث": 3, "أربعة": 4, "اربعة": 4, "أربع": 4, "اربع": 4,
    "خمسة": 5, "خمس": 5, "ستة": 6, "ست": 6, "سبعة": 7, "سبع": 7,
    "ثمانية": 8, "ثمان": 8, "تسعة": 9, "تسع": 9, "عشرة": 10, "عشر": 10,
    "اثنا عشر": 12, "اثني عشر": 12, "أربعة وعشرين": 24, "ثمانية عشر": 18,
    "ستة وثلاثين": 36,
}

_EASTERN_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def parse_duration_weeks(text) -> Optional[int]:
    """
    يقرأ مدة مكتوبة نصاً ويُرجعها بالأسابيع، أو None إن تعذّر.

    المدة غير المقروءة لا تُقدَّر: الخطة تُقاس عليها، ورقم مُختلَق يُبطل القياس
    ويمرّر خطة تتجاوز العقد.
    """
    raw = str(text or "").strip().translate(_EASTERN_DIGITS)
    if not raw:
        return None

    number = None
    digits = re.search(r"(\d+(?:\.\d+)?)", raw)
    if digits:
        number = float(digits.group(1))
    else:
        for word, value in sorted(_ARABIC_NUMERALS.items(), key=lambda kv: -len(kv[0])):
            if word in raw:
                number = float(value)
                break
    if number is None or number <= 0:
        return None

    lowered = raw.lower()
    for names, weeks in _DURATION_UNITS:
        if any(name in lowered for name in names):
            if weeks == 0:                       # أيام
                return max(1, round(number / 7))
            return max(1, round(number * weeks))
    return None


def contract_weeks(project_context: Optional[dict] = None,
                   extracted_weeks=None) -> Optional[int]:
    """
    مدة العقد بالأسابيع: من الاستخراج المُهيكل، وإلا من نص السياق الموحّد.

    يُرجع None حين لا تُذكر — فلا يُحكم على الخطة بسقف مُختلَق.
    """
    try:
        weeks = int(extracted_weeks)
        if weeks > 0:
            return weeks
    except (TypeError, ValueError):
        pass
    return parse_duration_weeks((project_context or {}).get("contract_duration"))


def _rows(df: Optional[pd.DataFrame]) -> list:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return []
    out = []
    for data in df.to_dict("records"):
        name = str(data.get("المرحلة", "")).strip()
        if not name:
            continue
        out.append({
            "number": _int(data.get("رقم المرحلة"), 0),
            "name": name,
            "start": max(1, _int(data.get("البداية (أسبوع)"), 1)),
            "duration": max(1, _int(data.get("المدة (أسبوع)"), 1)),
            "depends_on": str(data.get("يعتمد على", "")).strip(),
            "deliverables": str(data.get("التسليمات", "")).strip(),
            "weight": _float(data.get("وزن الإنجاز %"), 0.0),
        })
    return out


def _int(value, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _tokens(text: str) -> set:
    """كلمات دالّة لمطابقة تسليم بمرحلة."""
    words = re.split(r"[^\w]+", str(text or ""), flags=re.UNICODE)
    return {w.lower() for w in words if len(w) > 3}


def validate(df: Optional[pd.DataFrame],
             project_context: Optional[dict] = None,
             extracted_weeks=None) -> dict:
    """
    يفحص الخطة الزمنية.

    `errors` ما يجعل الخطة غير قابلة للتنفيذ أو مخالفة للكراسة.
    `warnings` ما يُضعفها أمام لجنة الفحص دون أن يُبطلها.
    """
    result = {
        "errors": [], "warnings": [], "phases": 0,
        "span_weeks": 0, "contract_weeks": contract_weeks(project_context, extracted_weeks),
        "uncovered_deliverables": [],
    }
    phases = _rows(df)
    result["phases"] = len(phases)
    if not phases:
        return result

    span = max(p["start"] + p["duration"] - 1 for p in phases)
    result["span_weeks"] = span

    limit = result["contract_weeks"]
    if limit and span > limit:
        result["errors"].append(
            f"الخطة تمتد {span} أسبوعاً ومدة العقد {limit} أسبوعاً — "
            f"تجاوز {span - limit} أسبوعاً."
        )

    # الاعتماديات: مرحلة تبدأ قبل انتهاء ما تعتمد عليه خطة غير واقعية
    by_number = {p["number"]: p for p in phases if p["number"]}
    for phase in phases:
        for ref in re.findall(r"\d+", phase["depends_on"]):
            parent = by_number.get(int(ref))
            if parent is None:
                result["warnings"].append(
                    f"«{phase['name']}» يعتمد على مرحلة رقم {ref} غير موجودة."
                )
                continue
            parent_end = parent["start"] + parent["duration"] - 1
            if phase["start"] <= parent_end:
                result["errors"].append(
                    f"«{phase['name']}» يبدأ في الأسبوع {phase['start']} "
                    f"قبل انتهاء «{parent['name']}» في الأسبوع {parent_end}."
                )

    # فجوة في التسلسل: أسابيع لا تعمل فيها أي مرحلة
    covered = set()
    for p in phases:
        covered.update(range(p["start"], p["start"] + p["duration"]))
    gaps = [w for w in range(1, span + 1) if w not in covered]
    if gaps:
        result["warnings"].append(
            f"أسابيع بلا أي نشاط: {', '.join(str(w) for w in gaps[:8])}"
            + ("…" if len(gaps) > 8 else "")
        )

    # الأوزان
    total_weight = sum(p["weight"] for p in phases)
    if total_weight and abs(total_weight - 100) > 1:
        result["warnings"].append(
            f"مجموع أوزان الإنجاز {total_weight:.0f}% لا 100%."
        )

    # كل تسليم رئيسي في الكراسة يجب أن يقع في مرحلة
    deliverables = (project_context or {}).get("key_deliverables") or []
    if deliverables:
        planned = _tokens(" ".join(p["deliverables"] + " " + p["name"] for p in phases))
        for item in deliverables:
            wanted = _tokens(item)
            if wanted and not (wanted & planned):
                result["uncovered_deliverables"].append(str(item))
        if result["uncovered_deliverables"]:
            result["errors"].append(
                f"{len(result['uncovered_deliverables'])} تسليماً في الكراسة "
                f"بلا مرحلة تقابله."
            )

    return result


def export_df(df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    """
    نسخة الجدول الصالحة للمستند الفني — بلا الأعمدة المالية.

    «معلم دفع» يفيد الفريق التجاري داخل النظام ولا يدخل المظروف الفني.
    """
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return None
    keep = [c for c in df.columns if c not in EXPORT_EXCLUDED_COLUMNS]
    return df[keep] if keep else None


def gantt_grid(df: Optional[pd.DataFrame],
               max_columns: int = MAX_GANTT_COLUMNS) -> Optional[dict]:
    """
    يبني شبكة المخطط الزمني: صف لكل مرحلة، وخانة مظلَّلة لكل وحدة زمنية تعمل
    فيها.

    تُرسم جدولاً مظلَّلاً لا صورة: يخرج نفسه في Word و PDF بلا مكتبة رسم ولا
    خط مفقود، ويبقى مقروءاً عند الطباعة بالأبيض والأسود.

    يُرجع {"unit", "columns", "rows"} أو None إن لا مراحل.
    """
    phases = _rows(df)
    if not phases:
        return None

    span = max(p["start"] + p["duration"] - 1 for p in phases)

    # التجميع إلى أشهر متى تجاوزت الأسابيع عرض الصفحة
    unit, size = "week", 1
    if span > max_columns:
        unit, size = "month", WEEKS_PER_MONTH
        while (span + size - 1) // size > max_columns:
            size += WEEKS_PER_MONTH

    count = max(1, (span + size - 1) // size)
    rows = []
    for phase in phases:
        first = (phase["start"] - 1) // size
        last = (phase["start"] + phase["duration"] - 2) // size
        rows.append({
            "label": phase["name"],
            "cells": [first <= i <= last for i in range(count)],
        })

    return {
        "unit": unit,
        "unit_weeks": size,
        "columns": count,
        "span_weeks": span,
        "rows": rows,
    }
