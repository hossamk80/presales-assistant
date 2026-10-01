"""
utils/ai_engine/prompts.py — بناء البرومبت وتحريره من الواجهة (14-1).

البرومبت المعروض يأتي من القاعدة إن حُرِّر، ومن `library` إن لم يُحرَّر.
"""

import streamlit as st

from typing import Optional

from .language import DEFAULT_LANGUAGE, language_instruction
from .library import EXTRACT_PROMPTS, PROMPTS
from .review import REVIEW_LENSES
from .schemas import MANDATORY_OUTLINE_SECTIONS


def build_prompt(prompt_key: str, language: str = DEFAULT_LANGUAGE, **fields) -> str:
    """
    يملأ قالب تعليمات مع تعليمة اللغة المناسبة.

    القالب هو النص الساري (14-1): تجاوز محرَّر إن وُجد، وإلا الافتراضي. ونصٌّ
    محرَّر يفشل تنسيقه لا يُسقط التوليد — يُسقَط هو إلى الافتراضي.
    """
    values = {"language_instruction": language_instruction(language), **fields}
    text = active_prompt(prompt_key, active_sector(), language)
    try:
        return text.format(**values)
    except (KeyError, IndexError, ValueError):
        return PROMPTS[prompt_key].format(**values)


def outline_prompt(language: str = DEFAULT_LANGUAGE) -> str:
    """تعليمات اقتراح الهيكل مع الأقسام الإلزامية وتعليمة اللغة."""
    return (
        active_prompt("outline", active_sector(), language).format(
            mandatory_sections="\n".join(
                f"   - {name}" for name in MANDATORY_OUTLINE_SECTIONS
            )
        )
        + f"\n{language_instruction(language)}"
    )


# ─── تحرير البرومبتات (14-1) ──────────────────────────────────────────────────
#
# النصوص أدناه (`PROMPTS` · `EXTRACT_PROMPTS` · `REVIEW_LENSES`) هي **الافتراضي
# ومصدره الوحيد**. الواجهة تحرّرها فيُحفظ التعديل تجاوزاً في جدول `prompts`،
# ويُقرأ هنا في كل استدعاء — فالتعديل يسري بلا إعادة تشغيل، واستعادة الافتراضي
# حذفُ التجاوز.
#
# **حاجزان لا يُتجاوزان**:
#   · القواعد الثابتة (14-2) تُلحق في `_call` بعد هذا كله، فلا يُزيلها تحرير.
#   · حقول القالب: نص محرَّر يستعمل حقلاً لا نعرفه يرفع `KeyError` وقت التوليد،
#     فيُفحص قبل الحفظ، ويُسقَط إلى الافتراضي وقت الاستدعاء إن أفلت.

# وكيل كل مفتاح — يُعرض في الواجهة ويُخزَّن مع التجاوز.
AGENT_WRITE = "write"


AGENT_EXTRACT = "extract"


AGENT_REVIEW = "review"


REVIEW_PROMPT_PREFIX = "review:"


def editable_prompts() -> dict:
    """كل ما يمكن تحريره: مفتاح ← (الوكيل، النص الافتراضي)."""
    catalog = {key: (AGENT_WRITE, text) for key, text in PROMPTS.items()}
    catalog.update({key: (AGENT_EXTRACT, text)
                    for key, text in EXTRACT_PROMPTS.items()})
    catalog.update({f"{REVIEW_PROMPT_PREFIX}{key}": (AGENT_REVIEW, lens["prompt"])
                    for key, lens in REVIEW_LENSES.items()})
    return catalog


def default_prompt(key: str) -> str:
    entry = editable_prompts().get(key)
    return entry[1] if entry else ""


def prompt_fields(text: str) -> set:
    """حقول القالب `{...}` — أساس فحص أي نص محرَّر."""
    import string

    return {
        name for _, name, _, _ in string.Formatter().parse(str(text or "")) if name
    }


def prompt_problem(key: str, text: str) -> Optional[str]:
    """
    يعيد مفتاح i18n إن كان النص المحرَّر غير صالح.

    حقل لا يعرفه النظام يرفع `KeyError` وقت التوليد فيُفقد القسم — يُرفض هنا.
    وحقل ناقص يُقبل مع تنبيه في الواجهة: قد يكون حذفه مقصوداً.
    """
    if not str(text or "").strip():
        return "pm.err_empty"
    unknown = prompt_fields(text) - prompt_fields(default_prompt(key))
    if unknown:
        return "pm.err_unknown_fields"
    return None


def missing_prompt_fields(key: str, text: str) -> set:
    """حقول كانت في الافتراضي وغابت عن المحرَّر — سياق لن يصل النموذج."""
    return prompt_fields(default_prompt(key)) - prompt_fields(text)


def active_prompt(key: str, sector: str = "", language: str = "") -> str:
    """
    النص الساري: تجاوز مفعَّل إن وُجد، وإلا الافتراضي من الشيفرة.

    القراءة في كل استدعاء لا عند الإقلاع — التعديل يسري بلا إعادة تشغيل.
    وفشل القراءة (قاعدة مقفلة · جدول ناقص) يعود بالافتراضي لا بانهيار.
    """
    try:
        from utils import db

        override = db.prompt_override(key, sector, language)
    except Exception:
        override = None
    return (override or {}).get("text") or default_prompt(key)


def active_sector() -> str:
    """قطاع المنافسة المفتوحة إن حُدِّد — مفتاح اختيار البرومبت الأخص."""
    return str(st.session_state.get("project_sector", "") or "").strip()
