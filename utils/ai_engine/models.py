"""
utils/ai_engine/models.py — سجل النماذج وميزانية السياق.

ورقةٌ لا تعتمد على شيء في الحزمة — وعليها تقوم البقيّة.
"""

import streamlit as st

from utils import providers
from utils.providers import catalog as _catalog


# ─── سجل النماذج ──────────────────────────────────────────────────────────────
# أسماء Gemini المعروضة تاريخياً — محفوظة للتوافق مع منافسات مخزّنة تحمل
# هذه الأسماء. القائمة الفعلية المعروضة تأتي من سجل الموفّر النشط.
MODELS = {
    "Gemini 3.6 Flash": "gemini-3.6-flash",
    "Gemini 3.1 Pro": "gemini-3.1-pro",
    "Gemini 3.5 Flash-Lite": "gemini-3.5-flash-lite",
}


MODEL_NAMES = list(MODELS)


DEFAULT_MODEL = "Gemini 3.6 Flash"


def model_names() -> list[str]:
    """نماذج الموفّر النشط للعرض في قوائم الاختيار — تتبدل مع الموفّر."""
    options = providers.model_options()
    return options or MODEL_NAMES


def default_model_name() -> str:
    preferred = st.session_state.get("ai_model_preference", "")
    options = model_names()
    return preferred if preferred in options else (options[0] if options else DEFAULT_MODEL)


# نافذة السياق مليون توكن. نترك هامشاً للتعليمات والرد وخطأ التقدير.
CONTEXT_TOKEN_BUDGET = 700_000


# النص العربي أكثف من الإنجليزي في التقطيع. نستخدم تقديراً متحفظاً حتى
# لا نتجاوز النافذة، ومعه `count_tokens_exact` عند الحاجة لرقم دقيق.
CHARS_PER_TOKEN = 2.5


CONTEXT_CHAR_BUDGET = int(CONTEXT_TOKEN_BUDGET * CHARS_PER_TOKEN)


def resolve_model(model_choice: str) -> str:
    """
    يحوّل الاسم المعروض إلى معرّف النموذج.

    الترتيب: أسماء Gemini التاريخية ← سجل الموفّر النشط (اسم أو معرّف) ←
    النموذج الافتراضي للموفّر النشط ← الافتراضي التاريخي.
    """
    if model_choice in MODELS:
        return MODELS[model_choice]

    active = providers.active_provider_name()
    resolved = _catalog.resolve_label(active, model_choice or "")
    if resolved:
        return resolved
    if model_choice and _catalog.find_model(model_choice):
        return model_choice

    if active != providers.DEFAULT_PROVIDER:
        fallback = _catalog.default_model(active)
        if fallback:
            return fallback
    return MODELS[DEFAULT_MODEL]


def estimate_tokens(text: str) -> int:
    """تقدير سريع محلي لعدد التوكنز (بدون استدعاء الشبكة)."""
    return int(len(str(text)) / CHARS_PER_TOKEN)
