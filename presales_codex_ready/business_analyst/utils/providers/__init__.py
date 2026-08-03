"""
utils/providers — طبقة تجريد الموفّرين (المرحلة 11)

كل استدعاء نموذج في النظام يمرّ من هنا: اختيار الموفّر، فحص حدّ الإنفاق
(11-9)، ذاكرة نتائج الاستدعاءات (11-13)، ثم تسجيل الاستهلاك من عدّادات
الموفّر نفسه (11-7). تبديل الموفّر لا يمسّ أي ملف في `views/`.
"""
import hashlib
import json
from datetime import datetime
from typing import Optional

import streamlit as st

from utils import db
from utils.providers import catalog
from utils.providers.base import (  # noqa: F401 — تُعاد للتصدير
    BudgetExceeded, GenResult, Provider, ProviderError, Usage,
)

DEFAULT_PROVIDER = "gemini"

BUDGET_WARN_RATIO = 0.8


def get_provider(name: str) -> Provider:
    if name == "gemini":
        from utils.providers.gemini import GeminiProvider

        return GeminiProvider()
    if name == "anthropic":
        from utils.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    if name in ("openai", "compat", "local"):
        from utils.providers.openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(name)
    raise ProviderError(f"موفّر غير معروف: {name}")


def active_provider_name() -> str:
    name = st.session_state.get("ai_provider") or DEFAULT_PROVIDER
    return name if name in catalog.provider_names() else DEFAULT_PROVIDER


def provider_for_model(model_id: str) -> str:
    """الموفّر المالك للنموذج، وإلا الموفّر النشط."""
    return catalog.find_model(model_id) or active_provider_name()


def has_credentials(provider: Optional[str] = None) -> bool:
    """
    هل يملك الموفّر ما يلزم للاستدعاء؟

    الموفّر المحلي (Ollama / vLLM) جاهز بلا مفتاح، فربط الواجهات بمفتاح
    Gemini وحده كان يُعطّل ميزات لمستخدم موفّره مضبوط فعلاً.
    """
    name = provider or active_provider_name()
    info = catalog.provider_info(name)
    if not info.get("needs_key", True):
        return True
    return bool(st.session_state.get(info.get("key_state", "")))


def active_provider_label() -> str:
    """الاسم المعروض للموفّر النشط — لمؤشرات الحالة في الواجهة."""
    name = active_provider_name()
    return catalog.provider_info(name).get("label", name)


def embed_ready() -> bool:
    """هل موفّر التضمين جاهز؟ الفهرسة تستدعيه هو لا موفّر النص."""
    return has_credentials(st.session_state.get("embed_provider") or "gemini")


def resolve(label_or_id: str, task: str = "write") -> tuple[str, str]:
    """
    يحوّل اختيار المستخدم (اسم معروض أو معرّف) إلى (موفّر، معرّف نموذج).

    الترتيب: نموذج لدى الموفّر النشط ← نموذج لدى أي موفّر ← النموذج
    الافتراضي للمهمة لدى الموفّر النشط (11-5).
    """
    provider = active_provider_name()
    model_id = catalog.resolve_label(provider, label_or_id or "")
    if model_id:
        return provider, model_id

    owner = catalog.find_model(label_or_id or "")
    if owner:
        return owner, label_or_id

    return provider, task_model(task)


def task_model(task: str) -> str:
    """النموذج الافتراضي للمهمة: تجاوز المستخدم ثم مستوى المهمة المعلن."""
    provider = active_provider_name()
    overrides = st.session_state.get("task_models") or {}
    chosen = overrides.get(task)
    if chosen and catalog.model_info(provider, chosen):
        return chosen
    return catalog.task_default_model(provider, task) \
        or catalog.default_model(provider) or ""


def model_options() -> list[str]:
    """الأسماء المعروضة لنماذج الموفّر النشط — لقوائم الاختيار في الواجهة."""
    return [info.get("label", model_id)
            for model_id, info in catalog.models_of(active_provider_name()).items()]


def default_model_label() -> str:
    provider = active_provider_name()
    model_id = catalog.default_model(provider) or ""
    info = catalog.model_info(provider, model_id) or {}
    return info.get("label", model_id)


# ─── حدّ الإنفاق الشهري (11-9) ───────────────────────────────────────────────


def month_key(now: Optional[datetime] = None) -> str:
    return (now or datetime.now()).strftime("%Y-%m")


def month_spend() -> float:
    return db.usage_month_cost(month_key())


def check_budget():
    """
    إنذار عند 80٪ وإيقاف عند 100٪. الإيقاف يرفع BudgetExceeded برسالة صريحة
    — لا فشل صامت ولا استدعاء يُنفق فوق الحدّ.
    """
    from utils.i18n import t

    budget = float(st.session_state.get("ai_month_budget") or 0.0)
    if budget <= 0:
        return
    spent = month_spend()
    if spent >= budget:
        raise BudgetExceeded(
            t("eng.budget_stop", spent=f"{spent:.2f}", budget=f"{budget:.2f}")
        )
    if spent >= budget * BUDGET_WARN_RATIO and \
            not st.session_state.get("_budget_warned"):
        st.session_state["_budget_warned"] = True
        st.warning(t("eng.budget_warn", spent=f"{spent:.2f}", budget=f"{budget:.2f}"))


# ─── ذاكرة نتائج الاستدعاءات (11-13) ─────────────────────────────────────────


def fingerprint(provider: str, model_id: str, prompt: str,
                schema: Optional[dict], temperature) -> str:
    """بصمة (تعليمات + سياق + نموذج) — تطابقها يعني نتيجة قابلة لإعادة الاستخدام."""
    payload = json.dumps(
        [provider, model_id, prompt, schema, temperature],
        ensure_ascii=False, sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ─── التنفيذ الموحّد: ذاكرة ← ميزانية ← استدعاء ← تسجيل ─────────────────────


def _log(result: GenResult, task: str, status: str):
    cost = catalog.cost_of(
        result.provider, result.model,
        result.usage.input_tokens, result.usage.cached_tokens,
        result.usage.output_tokens,
    ) if status == "ok" else 0.0
    db.log_ai_usage(
        project_id=st.session_state.get("_project_id"),
        project_name=st.session_state.get("_project_name") or "",
        task=task or "other",
        provider=result.provider,
        model=result.model,
        input_tokens=result.usage.input_tokens,
        cached_tokens=result.usage.cached_tokens,
        output_tokens=result.usage.output_tokens,
        cost=cost,
        elapsed_ms=result.elapsed_ms,
        status=status,
        month=month_key(),
    )


def run(model_id: str, prompt: str, schema: Optional[dict] = None,
        task: str = "write") -> GenResult:
    """
    استدعاء واحد عبر الموفّر المالك للنموذج.

    يرفع ProviderError / BudgetExceeded عند الفشل — التعامل مع العرض في
    `ai_engine` حفاظاً على سلوك الواجهات كما هو.
    """
    provider_name = provider_for_model(model_id)
    temperature = st.session_state.get("ai_temperature") \
        if st.session_state.get("ai_temperature_enabled") else None
    max_tokens = st.session_state.get("ai_max_tokens") or None

    cache_on = bool(st.session_state.get("ai_cache_enabled", True))
    fp = fingerprint(provider_name, model_id, prompt, schema, temperature)
    if cache_on:
        cached = db.ai_cache_get(fp)
        if cached is not None:
            result = GenResult(provider=provider_name, model=model_id)
            if schema is None:
                result.text = cached
            else:
                try:
                    result.parsed = json.loads(cached)
                    result.text = cached
                except ValueError:
                    result.text = cached
            _log(result, task, status="cache")
            return result

    check_budget()

    provider = get_provider(provider_name)
    if schema is None:
        result = provider.generate(model_id, prompt,
                                   temperature=temperature, max_tokens=max_tokens)
        payload = result.text
    else:
        result = provider.generate_json(model_id, prompt, schema,
                                        temperature=temperature, max_tokens=max_tokens)
        payload = json.dumps(result.parsed, ensure_ascii=False) \
            if result.parsed is not None else result.text

    _log(result, task, status="ok")

    if cache_on and payload:
        db.ai_cache_put(fp, provider_name, model_id, payload)
    return result


def embed(texts: list, task_type: str, dims: int) -> tuple[list, Usage, str]:
    """
    تضمين عبر موفّر التضمين **المنفصل** عن موفّر النص (11-6).
    يُرجع (المتجهات، الاستهلاك، اسم نموذج التضمين).
    """
    provider_name = st.session_state.get("embed_provider") or "gemini"
    model_id = st.session_state.get("embed_model") or "gemini-embedding-001"
    check_budget()
    vectors, usage = get_provider(provider_name).embed(
        model_id, texts, task_type, dims,
    )
    db.log_ai_usage(
        project_id=st.session_state.get("_project_id"),
        project_name=st.session_state.get("_project_name") or "",
        task="embed", provider=provider_name, model=model_id,
        input_tokens=usage.input_tokens, cached_tokens=0, output_tokens=0,
        cost=catalog.embed_cost_of(provider_name, model_id, usage.input_tokens),
        elapsed_ms=0, status="ok", month=month_key(),
    )
    return vectors, usage, f"{provider_name}/{model_id}"


def active_embed_signature() -> str:
    provider_name = st.session_state.get("embed_provider") or "gemini"
    model_id = st.session_state.get("embed_model") or "gemini-embedding-001"
    return f"{provider_name}/{model_id}"
