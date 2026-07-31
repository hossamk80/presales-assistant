"""
utils/traceability.py — تتبّع تغطية المتطلبات في نص العرض.

سبعة أقسام مكتوبة بإتقان لا تنفع إن سقط منها البند 4-7. هذه الوحدة تربط كل
صف في مصفوفة الامتثال بالقسم الذي عالجه فعلاً، وتُخرج ما لم يُعالَج.

المنطق هنا خالٍ من Streamlit عمداً: بوابة التصدير وشاشة الجداول تستهلكان
النتيجة نفسها، ونسخة ثانية من الحساب تعني رقمين متضاربين أمام المستخدم.
"""
from typing import Callable, Optional

import pandas as pd

from utils.ai_engine import (
    DEFAULT_LANGUAGE,
    DEFAULT_MODEL,
    EXTRACT_PROMPTS,
    TRACEABILITY_SCHEMA,
    ai_generate_json,
    language_instruction,
)
from utils.state import (
    COVERAGE_COVERED,
    COVERAGE_MISSING,
    COVERAGE_PARTIAL,
    COVERAGE_UNCHECKED,
)

# الأهمية التي يُمنع التصدير بسببها إن بقيت بلا تغطية.
BLOCKING_CRITICALITY = "High"


def _records(df: Optional[pd.DataFrame]) -> list:
    """
    صفوف الجدول كقواميس بأسماء الأعمدة كما هي.

    itertuples لا يصلح هنا: أسماء الأعمدة التي تحتوي مسافة ("مرجع البند")
    ليست معرّفات Python صالحة فيستبدلها pandas بـ _1 و _2 صامتاً، فتُقرأ
    فارغة ويبدو الحقل غير معبّأ.
    """
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return []
    return df.to_dict("records")


def requirements_block(df: Optional[pd.DataFrame]) -> str:
    """صفوف المصفوفة بصيغة نصية موجزة تكفي للمطابقة."""
    lines = []
    for data in _records(df):
        req_id = str(data.get("المعرّف", "")).strip()
        text = str(data.get("المتطلب", "")).strip()
        if not (req_id or text):
            continue
        criticality = str(data.get("الأهمية", "")).strip()
        clause = str(data.get("مرجع البند", "")).strip()
        parts = [p for p in (req_id, criticality, clause) if p]
        lines.append(f"- [{' | '.join(parts)}] {text}")
    return "\n".join(lines)


def sections_block(sections: list, content_of: Callable[[str], str]) -> str:
    """
    عناوين الأقسام المُدرَجة مع نصوصها.

    الأقسام غير المُدرَجة تُستبعد: تغطية في قسم لن يُصدَّر ليست تغطية.
    """
    blocks = []
    for sec in sections:
        if not sec.get("include") or sec.get("kind") in ("table_compliance", "table_boq"):
            continue
        content = str(content_of(sec["key"]) or "").strip()
        if not content:
            continue
        blocks.append(f"### {sec['title']}\n{content}")
    return "\n\n".join(blocks)


def apply_coverage(df: pd.DataFrame, coverage: list) -> pd.DataFrame:
    """
    يكتب نتيجة الفحص في عمودَي التغطية.

    المتطلب الذي لم يرد في نتيجة النموذج يبقى "غير مفحوص" ولا يُفترض مغطّى —
    الصمت ليس تغطية.
    """
    out = df.copy()
    by_id = {
        str(item.get("req_id", "")).strip(): item
        for item in (coverage or [])
        if str(item.get("req_id", "")).strip()
    }

    statuses, owners = [], []
    for data in _records(out):
        item = by_id.get(str(data.get("المعرّف", "")).strip())
        if not item:
            statuses.append(COVERAGE_UNCHECKED)
            owners.append("")
            continue
        status = str(item.get("status", "")).strip()
        statuses.append(status if status in
                        (COVERAGE_COVERED, COVERAGE_PARTIAL, COVERAGE_MISSING)
                        else COVERAGE_UNCHECKED)
        sections = [str(s).strip() for s in (item.get("sections") or []) if str(s).strip()]
        gap = str(item.get("gap", "")).strip()
        owners.append(" · ".join(sections) if sections else gap)

    out["التغطية"] = statuses
    out["القسم المغطّي"] = owners
    return out


def coverage_summary(df: Optional[pd.DataFrame]) -> dict:
    """
    خلاصة التغطية، وقائمة المتطلبات الحرجة التي تمنع التسليم.

    "غير مفحوص" يُعدّ حاجزاً مثل "غير مغطّى" حين تكون الأهمية عالية: لم نتحقق
    بعد يساوي لا نعرف، وهو ما لا يُبنى عليه قرار تسليم.
    """
    empty = {"total": 0, "covered": 0, "partial": 0, "missing": 0,
             "unchecked": 0, "blocking": []}
    if df is None or df.empty or "التغطية" not in df.columns:
        return empty

    counts = dict(empty)
    blocking = []
    for data in _records(df):
        req = str(data.get("المتطلب", "")).strip()
        req_id = str(data.get("المعرّف", "")).strip()
        if not (req or req_id):
            continue

        counts["total"] += 1
        status = str(data.get("التغطية", "")).strip()
        key = {
            COVERAGE_COVERED: "covered",
            COVERAGE_PARTIAL: "partial",
            COVERAGE_MISSING: "missing",
        }.get(status, "unchecked")
        counts[key] += 1

        criticality = str(data.get("الأهمية", "")).strip()
        if criticality == BLOCKING_CRITICALITY and key in ("missing", "partial", "unchecked"):
            blocking.append(f"{req_id or '—'}: {req}".strip())

    counts["blocking"] = blocking
    return counts


def run_coverage_check(
    df: pd.DataFrame,
    sections: list,
    content_of: Callable[[str], str] = None,
    model_choice: str = DEFAULT_MODEL,
    language: str = DEFAULT_LANGUAGE,
    on_progress: Optional[Callable[[str], None]] = None,
) -> Optional[pd.DataFrame]:
    """
    يشغّل فحص التغطية ويُرجع نسخة محدّثة من الجدول، أو None عند الفشل.

    الفشل لا يمسّ الجدول الأصلي — نتيجة فحص ناقصة أسوأ من غياب الفحص لأنها
    تُقرأ كتغطية مؤكَّدة.
    """
    content_of = content_of or (lambda key: "")
    requirements = requirements_block(df)
    body = sections_block(sections, content_of)
    if not requirements or not body:
        return None

    prompt = EXTRACT_PROMPTS["traceability"].format(
        requirements=requirements, sections=body,
    ) + f"\n{language_instruction(language)}"

    result = ai_generate_json(
        prompt,
        schema=TRACEABILITY_SCHEMA,
        model_choice=model_choice,
        merge_key="coverage",
        on_progress=on_progress,
    )
    if not result:
        return None
    return apply_coverage(df, (result or {}).get("coverage") or [])
