"""
utils/providers/catalog.py — سجل الموفّرين والنماذج (11-3)

سجل واحد يصف كل موفّر ونماذجه: نافذة السياق، دعم JSON المُهيكل، والسعر لكل
مليون توكن. **قابل للتحديث بلا تعديل شيفرة**: ملف `data/models.json` (أو
المسار في `ANALYST_MODELS_PATH`) يُدمج فوق هذا السجل فيضيف نماذج أو يعدّل
أسعاراً دون لمس هذا الملف.

الأسعار بالدولار لكل مليون توكن، وهي قيم افتراضية تُراجَع من فاتورة المزوّد
وتُصحَّح في `models.json` عند الحاجة.
"""
import json
import os
from typing import Any, Optional

APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS_PATH = os.environ.get("ANALYST_MODELS_PATH") or os.path.join(
    APP_DIR, "data", "models.json"
)

# tier: "light" للاستخراج والتصنيف · "strong" للهيكل والمراجعة (11-5)
CATALOG: dict[str, dict[str, Any]] = {
    "gemini": {
        "label": "Google Gemini",
        "key_state": "api_gemini",
        "key_hint": "AIza...",
        "needs_base_url": False,
        "models": {
            "gemini-3.6-flash": {
                "label": "Gemini 3.6 Flash", "context": 1_000_000, "json": True,
                "in": 0.50, "cached": 0.125, "out": 3.00, "tier": "strong",
            },
            "gemini-3.1-pro": {
                "label": "Gemini 3.1 Pro", "context": 1_000_000, "json": True,
                "in": 2.50, "cached": 0.625, "out": 15.00, "tier": "",
            },
            "gemini-3.5-flash-lite": {
                "label": "Gemini 3.5 Flash-Lite", "context": 1_000_000, "json": True,
                "in": 0.10, "cached": 0.025, "out": 0.40, "tier": "light",
            },
        },
        "embed_models": {
            "gemini-embedding-001": {"label": "Gemini Embedding 001", "in": 0.15},
        },
    },
    "anthropic": {
        "label": "Anthropic Claude",
        "key_state": "api_claude",
        "key_hint": "sk-ant-...",
        "needs_base_url": False,
        "models": {
            "claude-opus-5": {
                "label": "Claude Opus 5", "context": 1_000_000, "json": True,
                "in": 5.00, "cached": 0.50, "out": 25.00, "tier": "",
            },
            "claude-sonnet-5": {
                "label": "Claude Sonnet 5", "context": 1_000_000, "json": True,
                "in": 3.00, "cached": 0.30, "out": 15.00, "tier": "strong",
            },
            "claude-haiku-4-5": {
                "label": "Claude Haiku 4.5", "context": 200_000, "json": True,
                "in": 1.00, "cached": 0.10, "out": 5.00, "tier": "light",
            },
        },
        "embed_models": {},
    },
    "openai": {
        "label": "OpenAI",
        "key_state": "api_openai",
        "key_hint": "sk-...",
        "needs_base_url": False,
        "base_url": "https://api.openai.com/v1",
        "models": {
            "gpt-5.1": {
                "label": "GPT-5.1", "context": 400_000, "json": True,
                "in": 1.25, "cached": 0.125, "out": 10.00, "tier": "strong",
            },
            "gpt-5.1-mini": {
                "label": "GPT-5.1 mini", "context": 400_000, "json": True,
                "in": 0.25, "cached": 0.025, "out": 2.00, "tier": "light",
            },
        },
        "embed_models": {
            "text-embedding-3-small": {"label": "Text Embedding 3 Small", "in": 0.02},
            "text-embedding-3-large": {"label": "Text Embedding 3 Large", "in": 0.13},
        },
    },
    # أي نقطة متوافقة مع OpenAI: ‏OpenRouter · Azure OpenAI · Groq · Mistral ·
    # DeepSeek · Together — الفرق الوحيد هو الرابط والمفتاح واسم النموذج.
    "compat": {
        "label": "OpenAI-compatible (OpenRouter / Groq / …)",
        "key_state": "api_compat",
        "key_hint": "sk-or-...",
        "needs_base_url": True,
        "base_url": "https://openrouter.ai/api/v1",
        "models": {
            "openrouter/auto": {
                "label": "OpenRouter Auto", "context": 200_000, "json": False,
                "in": 0.0, "cached": 0.0, "out": 0.0, "tier": "strong",
            },
        },
        "embed_models": {},
    },
    # محلي (Ollama / vLLM): بلا مفتاح وبلا كلفة لكل توكن.
    "local": {
        "label": "محلي / Local (Ollama · vLLM)",
        "key_state": "api_local",
        "key_hint": "",
        "needs_key": False,
        "needs_base_url": True,
        "base_url": "http://localhost:11434/v1",
        "models": {
            "llama3.1": {
                "label": "Llama 3.1 (Ollama)", "context": 128_000, "json": False,
                "in": 0.0, "cached": 0.0, "out": 0.0, "tier": "strong",
            },
        },
        "embed_models": {},
    },
}

# المهام المعلنة ومستوياتها الافتراضية (11-5): الأخف للاستخراج والتصنيف،
# والأقوى للهيكل والكتابة والمراجعة.
TASK_TIERS = {
    "extract": "light",
    "classify": "light",
    "write": "strong",
    "review": "strong",
    "chat": "light",
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


_cached_catalog: Optional[dict] = None
_cached_mtime: Optional[float] = None


def load_catalog() -> dict:
    """السجل بعد دمج تجاوزات `models.json` إن وُجد الملف."""
    global _cached_catalog, _cached_mtime
    try:
        mtime = os.path.getmtime(MODELS_PATH)
    except OSError:
        mtime = None
    if _cached_catalog is not None and mtime == _cached_mtime:
        return _cached_catalog

    catalog = CATALOG
    if mtime is not None:
        try:
            with open(MODELS_PATH, encoding="utf-8") as fh:
                catalog = _deep_merge(CATALOG, json.load(fh))
        except (OSError, ValueError):
            catalog = CATALOG

    _cached_catalog = catalog
    _cached_mtime = mtime
    return catalog


def provider_names() -> list[str]:
    return list(load_catalog())


def provider_info(provider: str) -> dict:
    catalog = load_catalog()
    return catalog.get(provider) or catalog["gemini"]


def models_of(provider: str) -> dict:
    return provider_info(provider).get("models") or {}


def embed_models_of(provider: str) -> dict:
    return provider_info(provider).get("embed_models") or {}


def model_info(provider: str, model_id: str) -> Optional[dict]:
    return models_of(provider).get(model_id)


def find_model(model_id: str) -> Optional[str]:
    """أي موفّر يملك هذا النموذج؟ يُرجع اسم الموفّر أو None."""
    for name, info in load_catalog().items():
        if model_id in (info.get("models") or {}):
            return name
    return None


def resolve_label(provider: str, label_or_id: str) -> Optional[str]:
    """يحوّل الاسم المعروض أو المعرّف إلى معرّف نموذج لدى الموفّر."""
    models = models_of(provider)
    if label_or_id in models:
        return label_or_id
    for model_id, info in models.items():
        if info.get("label") == label_or_id:
            return model_id
    return None


def default_model(provider: str, tier: str = "strong") -> Optional[str]:
    """نموذج المستوى المطلوب، وإلا أول نموذج لدى الموفّر."""
    models = models_of(provider)
    for model_id, info in models.items():
        if info.get("tier") == tier:
            return model_id
    return next(iter(models), None)


def task_default_model(provider: str, task: str) -> Optional[str]:
    return default_model(provider, TASK_TIERS.get(task, "strong"))


def cost_of(provider: str, model_id: str, input_tokens: int,
            cached_tokens: int, output_tokens: int) -> float:
    """كلفة استدعاء بالدولار من عدّادات الموفّر (11-7)."""
    info = model_info(provider, model_id)
    if not info:
        return 0.0
    fresh = max(0, input_tokens - cached_tokens)
    return (
        fresh * float(info.get("in", 0.0))
        + cached_tokens * float(info.get("cached", 0.0))
        + output_tokens * float(info.get("out", 0.0))
    ) / 1_000_000


def embed_cost_of(provider: str, model_id: str, input_tokens: int) -> float:
    info = embed_models_of(provider).get(model_id) or {}
    return input_tokens * float(info.get("in", 0.0)) / 1_000_000
