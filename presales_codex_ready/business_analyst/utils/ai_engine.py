"""
utils/ai_engine.py — محرك الذكاء الاصطناعي

منذ المرحلة 11 يمرّ كل استدعاء من طبقة الموفّرين `utils/providers/`:
تعدد الموفّرين والنماذج، قياس الاستهلاك، حدّ الإنفاق، وذاكرة النتائج —
كل ذلك هناك، وهذا الملف يحفظ واجهة `ai_generate` / `ai_generate_json`
كما تعرفها الواجهات فلا يمسّها تبديل الموفّر.
"""
import json
import re
import time
import streamlit as st
from typing import Any, Callable, Optional

from utils.i18n import t
from utils import providers
from utils.providers import BudgetExceeded, ProviderError
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


# ─── اللغة ────────────────────────────────────────────────────────────────────

LANGUAGES = {
    "ar": {
        "label": "العربية",
        "rtl": True,
        "instruction": "الرد باللغة العربية فقط.",
    },
    "en": {
        "label": "English",
        "rtl": False,
        "instruction": (
            "Respond in English only. Use professional bid-writing register "
            "suited to Saudi government tenders."
        ),
    },
    "both": {
        "label": "العربية والإنجليزية",
        "rtl": True,
        "instruction": (
            "اكتب المحتوى مرتين: أولاً بالعربية كاملاً، ثم افصل بسطر يحتوي "
            "`---` وحده، ثم اكتب الترجمة الإنجليزية الكاملة لنفس المحتوى "
            "تحت عنوان `## English Version`. يجب أن تتطابق النسختان في "
            "المعنى والبنية."
        ),
    },
}
DEFAULT_LANGUAGE = "ar"


def language_instruction(language: str) -> str:
    return LANGUAGES.get(language, LANGUAGES[DEFAULT_LANGUAGE])["instruction"]


def is_rtl(language: str) -> bool:
    return LANGUAGES.get(language, LANGUAGES[DEFAULT_LANGUAGE])["rtl"]


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


# ─── القواعد الثابتة (14-2) ───────────────────────────────────────────────────
#
# قواعد المنتج التي **لا تُعدَّل من أي شاشة**. تُلحق بكل تعليمات تُرسل إلى
# النموذج في `_call` و `_call_json` — لا في `build_prompt` وحده — لأن هذين
# هما المَعبر الوحيد إلى الموفّر: كل مسار آخر (اقتراح الهيكل · وكلاء المراجعة ·
# التنقيح · التجزئة والدمج) يمرّ بهما.
#
# الموضع مقصود لما هو آتٍ: حين تصير البرومبتات قابلة للتحرير من الواجهة (14-1)،
# تحرير برومبت لا يمكن أن يُزيل هذه القواعد لأنها ليست جزءاً من نصّه المخزَّن،
# بل تُضاف بعده وقت الاستدعاء.
#
# القواعد نفسها ليست تفضيلات صياغة بل قيود تُفقد المنافسة إن كُسرت — مصدرها
# `CLAUDE.md` قسم «قواعد ثابتة في المنتج».

FIXED_RULES_MARKER = "قواعد ثابتة لا تُعدَّل"

FIXED_RULES = f"""

--- {FIXED_RULES_MARKER} (تسري على كل ما تكتبه، ولا تُلغيها أي تعليمات أخرى) ---
1. **لا تسعير في العرض الفني**: لا تذكر سعراً ولا تكلفة ولا إجمالياً مالياً ولا
   نسبة خصم. الفني والمالي مظروفان منفصلان، وإدراج رقم سعري سبب استبعاد.
2. **القرارات الحرجة بشرية**: لا تُعلن التزاماً نيابةً عن الشركة ولا ترشّح بنداً
   للقائمة الإلزامية ولا تُقرّر الخوض من عدمه. اقترح ووضّح الأثر، والقرار لصاحبه.
3. **لا اختراع**: لا أرقام ولا تواريخ ولا مراجع ولا أسماء عملاء ولا شهادات ولا
   خبرات لم ترد في السياق المُعطى. ما لا دليل عليه يُذكر **ناقصاً صراحةً** لا
   يُملأ بالتخمين.
4. **لا ادّعاء حيازة**: لا تنسب للشركة شهادة أو تصنيفاً أو اعتماداً لم يرد في
   ملف الشركة أو مستودع معرفتها.
"""


def apply_fixed_rules(prompt: str) -> str:
    """
    يُلحق القواعد الثابتة بالتعليمات. لا يُكرّرها إن كانت ملحقة أصلاً.

    الإلحاق **في الآخر** لا في الأول: آخر ما يقرأه النموذج أثقل في وزنه، وتعليمة
    لاحقة تناقضها تصير هي المخالِفة لا العكس.
    """
    text = str(prompt or "")
    if FIXED_RULES_MARKER in text:
        return text
    return text + FIXED_RULES


def has_fixed_rules(text: str) -> bool:
    return FIXED_RULES_MARKER in str(text or "")


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


def estimate_tokens(text: str) -> int:
    """تقدير سريع محلي لعدد التوكنز (بدون استدعاء الشبكة)."""
    return int(len(str(text)) / CHARS_PER_TOKEN)


# إنشاء العميل صار مسؤولية كل موفّر في `utils/providers/` — لا عميل Gemini
# مباشراً هنا، وإلا بقي مسار ثانٍ لا يمرّ بالقياس ولا بحدّ الإنفاق.


def has_credentials() -> bool:
    """هل الموفّر النشط جاهز للاستدعاء؟ (الموفّر المحلي جاهز بلا مفتاح)"""
    return providers.has_credentials()


# ─── إعادة المحاولة عند الفشل العابر ──────────────────────────────────────────
#
# تحليل كراسة كبيرة عشرات الاستدعاءات. حدّ معدّل واحد (429) أو انقطاع لحظي
# (503) كان يُسقط التحليل كله ويُجبر المستخدم على إعادته من أوله — وقد استُهلك
# التوكن مرتين. نعيد المحاولة على الأخطاء العابرة وحدها؛ مفتاح خاطئ أو طلب
# مرفوض لا يُصلحه الانتظار.

RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY = 2.0          # ثوانٍ، تتضاعف مع كل محاولة

_TRANSIENT_MARKERS = (
    "429", "500", "502", "503", "504",
    "rate limit", "resource_exhausted", "quota",
    "unavailable", "deadline", "timeout", "internal error",
    "connection", "temporarily",
)


def _is_transient(error: Exception) -> bool:
    """هل يستحق هذا الخطأ إعادة محاولة؟"""
    code = getattr(error, "code", None) or getattr(error, "status_code", None)
    if code in (429, 500, 502, 503, 504):
        return True
    text = f"{type(error).__name__} {error}".lower()
    return any(marker in text for marker in _TRANSIENT_MARKERS)


def _with_retry(call, on_progress: Optional[Callable[[str], None]] = None):
    """
    ينفّذ `call` مع إعادة محاولة تصاعدية على الأخطاء العابرة.

    يُعيد رفع الخطأ بعد استنفاد المحاولات ليعالجه المتصل كما كان يفعل.
    """
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            return call()
        except Exception as error:
            if attempt == RETRY_ATTEMPTS or not _is_transient(error):
                raise
            message = t("eng.retrying", n=attempt, total=RETRY_ATTEMPTS - 1)
            if on_progress:
                on_progress(message)
            else:
                st.warning(message)
            time.sleep(RETRY_BASE_DELAY * (2 ** (attempt - 1)))


def count_tokens_exact(text: str, model_choice: str = DEFAULT_MODEL) -> Optional[int]:
    """عدد التوكنز الفعلي من الـ API. يُرجع None إذا تعذّر الاتصال."""
    model_id = resolve_model(model_choice)
    try:
        provider = providers.get_provider(providers.provider_for_model(model_id))
        return provider.count_tokens(model_id, text)
    except Exception:
        return None


def _report_provider_error(error: Exception):
    """رسالة موحّدة لفشل الموفّر — مفتاح غائب أو ميزانية أو خطأ API."""
    if isinstance(error, BudgetExceeded):
        st.error(f"🛑 {error}")
    elif isinstance(error, ProviderError) and str(error) == "missing_key":
        st.error(t("eng.key_missing"))
    else:
        st.error(t("eng.api_error", error=error))


def _call(prompt: str, model_id: str,
          on_progress: Optional[Callable[[str], None]] = None,
          task: str = "write") -> Optional[str]:
    """استدعاء واحد للنموذج عبر طبقة الموفّرين، مع إعادة محاولة عابرة."""
    prompt = apply_fixed_rules(prompt)          # 14-2: لا استدعاء بلا القواعد
    try:
        result = _with_retry(
            lambda: providers.run(model_id, prompt, task=task),
            on_progress,
        )
    except (BudgetExceeded, ProviderError) as e:
        _report_provider_error(e)
        return None
    except Exception as e:
        st.error(t("eng.api_error", error=e))
        return None

    if not result.text:
        st.warning(t("eng.empty_reply"))
        return None
    return result.text


def _split_into_chunks(text: str, chunk_chars: int) -> list[str]:
    """
    تقسيم النص على حدود الفقرات قدر الإمكان حتى لا تنقطع الجمل في المنتصف.
    يقع على حدود الأسطر إن لم توجد فقرات، وعلى الحرف كحل أخير.
    """
    if len(text) <= chunk_chars:
        return [text]

    chunks: list[str] = []
    remaining = text

    while len(remaining) > chunk_chars:
        window = remaining[:chunk_chars]
        # ابحث عن أفضل نقطة قطع ضمن الربع الأخير من النافذة
        floor = int(chunk_chars * 0.75)
        cut = window.rfind("\n\n")
        if cut < floor:
            cut = window.rfind("\n")
        if cut < floor:
            cut = chunk_chars
        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].lstrip()

    if remaining.strip():
        chunks.append(remaining.strip())

    return chunks


_MERGE_PROMPT = """فيما يلي نتائج تحليل أجزاء متتابعة من كراسة شروط واحدة كبيرة.
ادمجها في تحليل واحد متماسك يتبع نفس الهيكل المطلوب أصلاً، مع حذف التكرار
وتوحيد المتناقضات وترتيب النقاط حسب الأهمية.

التعليمات الأصلية للتحليل:
{original_prompt}

نتائج الأجزاء:
{partials}

أعطِ التحليل المدموج النهائي فقط وبنفس الهيكل. {language_instruction}"""


def ai_generate(
    prompt: str,
    model_choice: str = DEFAULT_MODEL,
    rfp_context: str = "",
    on_progress: Optional[Callable[[str], None]] = None,
    extra_context: str = "",
    language: str = DEFAULT_LANGUAGE,
) -> Optional[str]:
    """
    توليد محتوى بالذكاء الاصطناعي.

    يمرّر كامل نص الكراسة ضمن نافذة السياق (مليون توكن). إذا تجاوز النص
    النافذة، ينتقل تلقائياً إلى أسلوب map-reduce: يحلّل كل جزء على حدة ثم
    يدمج النتائج.

    Args:
        prompt: التعليمات / المهمة
        model_choice: الاسم المعروض للنموذج
        rfp_context: نص الكراسة الذي يُحقن كسياق
        on_progress: دالة اختيارية تُستدعى برسالة تقدّم عند التحليل المجزّأ

    Returns:
        النص المولَّد أو None عند الفشل
    """
    model_id = resolve_model(model_choice)
    if extra_context:
        prompt = f"{prompt}\n{extra_context}"

    if not rfp_context:
        return _call(prompt, model_id, on_progress)

    # المسار المعتاد: الكراسة كاملة في استدعاء واحد
    if len(rfp_context) <= CONTEXT_CHAR_BUDGET:
        return _call(f"{prompt}\n\n---\nنص الكراسة:\n{rfp_context}", model_id, on_progress)

    # المسار الاستثنائي: كراسة أكبر من نافذة السياق
    chunks = _split_into_chunks(rfp_context, CONTEXT_CHAR_BUDGET)
    partials: list[str] = []

    for i, chunk in enumerate(chunks, start=1):
        if on_progress:
            on_progress(f"تحليل الجزء {i} من {len(chunks)}…")
        part = _call(
            f"{prompt}\n\n---\n"
            f"ملاحظة: هذا الجزء {i} من {len(chunks)} من كراسة طويلة. "
            f"حلّل ما ورد في هذا الجزء فقط ولا تفترض ما في الأجزاء الأخرى.\n\n"
            f"نص الجزء:\n{chunk}",
            model_id,
            on_progress,
        )
        if part:
            partials.append(f"### نتيجة الجزء {i}\n{part}")

    if not partials:
        return None
    if len(partials) == 1:
        return partials[0]

    if on_progress:
        on_progress("دمج نتائج الأجزاء…")
    return _call(
        _MERGE_PROMPT.format(
            original_prompt=prompt,
            partials="\n\n".join(partials),
            language_instruction=language_instruction(language),
        ),
        model_id,
        on_progress,
    )


# ─── المخرجات المُهيكلة (JSON) ────────────────────────────────────────────────


def _strip_code_fence(text: str) -> str:
    """إزالة أسوار Markdown إن أحاطت بالـ JSON."""
    stripped = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, re.DOTALL)
    return fence.group(1) if fence else stripped


def _call_json(prompt: str, model_id: str, schema: dict,
               on_progress: Optional[Callable[[str], None]] = None,
               task: str = "extract") -> Optional[Any]:
    """استدعاء يُرجع JSON مطابقاً للمخطط المحدّد، مع إعادة محاولة عابرة."""
    prompt = apply_fixed_rules(prompt)          # 14-2: لا استدعاء بلا القواعد
    try:
        result = _with_retry(
            lambda: providers.run(model_id, prompt, schema=schema, task=task),
            on_progress,
        )
    except (BudgetExceeded, ProviderError) as e:
        _report_provider_error(e)
        return None
    except Exception as e:
        st.error(t("eng.api_error", error=e))
        return None

    # المسار المفضّل: كائن مُحلَّل جاهز من الموفّر
    if isinstance(result.parsed, (dict, list)):
        return result.parsed

    raw = result.text
    if not raw:
        st.warning(t("eng.empty_reply"))
        return None

    try:
        return json.loads(_strip_code_fence(raw))
    except json.JSONDecodeError as e:
        st.error(t("eng.json_failed", error=e))
        with st.expander(t("eng.raw_reply")):
            st.code(raw[:3000])
        return None


def ai_generate_json(
    prompt: str,
    schema: dict,
    model_choice: str = DEFAULT_MODEL,
    rfp_context: str = "",
    merge_key: Optional[str] = None,
    on_progress: Optional[Callable[[str], None]] = None,
) -> Optional[Any]:
    """
    توليد مخرجات مُهيكلة مطابقة لمخطط JSON.

    Args:
        prompt: التعليمات
        schema: مخطط الرد (مجموعة OpenAPI الفرعية المدعومة من Gemini)
        merge_key: اسم حقل المصفوفة الذي تُدمج عناصره عند تجزئة الكراسات
                   الكبيرة. الدمج هنا حتمي (ضمّ القوائم) ولا يمر بالنموذج.

    Returns:
        كائن Python مُحلَّل، أو None عند الفشل.
    """
    model_id = resolve_model(model_choice)

    if not rfp_context:
        return _call_json(prompt, model_id, schema, on_progress)

    if len(rfp_context) <= CONTEXT_CHAR_BUDGET:
        return _call_json(
            f"{prompt}\n\n---\nنص الكراسة:\n{rfp_context}",
            model_id, schema, on_progress,
        )

    # كراسة أكبر من نافذة السياق
    chunks = _split_into_chunks(rfp_context, CONTEXT_CHAR_BUDGET)
    results = []
    for i, chunk in enumerate(chunks, start=1):
        if on_progress:
            on_progress(f"استخراج من الجزء {i} من {len(chunks)}…")
        part = _call_json(
            f"{prompt}\n\n---\n"
            f"ملاحظة: هذا الجزء {i} من {len(chunks)} من كراسة طويلة. "
            f"استخرج ما ورد في هذا الجزء فقط.\n\nنص الجزء:\n{chunk}",
            model_id,
            schema,
            on_progress,
        )
        if part is not None:
            results.append(part)

    if not results:
        return None
    if len(results) == 1 or not merge_key:
        return results[0]

    merged: list = []
    for r in results:
        items = r.get(merge_key) if isinstance(r, dict) else r
        if isinstance(items, list):
            merged.extend(items)

    # الحقول القياسية (كدرجة الجاهزية) لا تُدمج كقوائم — نأخذها من أول نتيجة
    # حتى لا تضيع عند تجزئة الكراسات الكبيرة.
    out = {k: v for k, v in results[0].items() if k != merge_key} \
        if isinstance(results[0], dict) else {}
    out[merge_key] = merged
    return out


# ─── مخططات الاستخراج ─────────────────────────────────────────────────────────

COMPLIANCE_CATEGORIES = ["Technical", "Operational", "Administrative", "Legal"]
CRITICALITY_LEVELS = ["High", "Medium", "Low"]

COMPLIANCE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "requirements": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "req_id": {
                        "type": "STRING",
                        "description": "معرّف متسلسل بصيغة REQ-001",
                    },
                    "category": {"type": "STRING", "enum": COMPLIANCE_CATEGORIES},
                    "clause_reference": {
                        "type": "STRING",
                        "description": "رقم البند أو الصفحة في الكراسة، أو نص فارغ",
                    },
                    "requirement_summary": {
                        "type": "STRING",
                        "description": "ملخّص المتطلب كما ورد في الكراسة",
                    },
                    "criticality": {"type": "STRING", "enum": CRITICALITY_LEVELS},
                    "proposed_compliance_strategy": {
                        "type": "STRING",
                        "description": "كيف يستوفي عرضنا هذا المتطلب",
                    },
                    "mandatory": {
                        "type": "BOOLEAN",
                        "description": "هل عدم استيفائه يؤدي للاستبعاد الفوري؟",
                    },
                    "certificate": {
                        "type": "STRING",
                        "description": "الشهادة أو الوثيقة المطلوبة لإثباته، أو نص فارغ",
                    },
                },
                "required": [
                    "req_id", "category", "requirement_summary",
                    "criticality", "proposed_compliance_strategy",
                ],
            },
        }
    },
    "required": ["requirements"],
}

BOQ_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "item_number": {
                        "type": "STRING",
                        "description": "الرقم التسلسلي أو رمز البند كما ورد في المصدر",
                    },
                    "category": {
                        "type": "STRING",
                        "description": "التصنيف عالي المستوى للبند",
                    },
                    "item_name": {"type": "STRING", "description": "عنوان مختصر للبند"},
                    "unit": {
                        "type": "STRING",
                        "description": "وحدة القياس: وحدة/شهر/خدمة/مقطوعية/قطعة …",
                    },
                    "description": {"type": "STRING", "description": "الوصف الفني الكامل"},
                    "specifications": {
                        "type": "STRING",
                        "description": "المواصفات الفنية التفصيلية والمعايير",
                    },
                    "construction_code": {
                        "type": "STRING",
                        "description": "كود البناء القياسي أو المرجع الكتالوجي",
                    },
                    "quantity": {"type": "NUMBER"},
                    "mandatory_list_flag": {
                        "type": "BOOLEAN",
                        "description": (
                            "هل يقع هذا المنتج/الخدمة ضمن القائمة الإلزامية للمحتوى "
                            "المحلي السعودي؟ ضع true فقط عند ورود ما يدل على ذلك "
                            "في مستندات المنافسة أو في القائمة المرجعية المرفقة."
                        ),
                    },
                },
                "required": ["item_name", "unit", "quantity", "mandatory_list_flag"],
            },
        }
    },
    "required": ["items"],
}

PROJECT_CONTEXT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "project_title": {"type": "STRING"},
        "issuing_entity": {"type": "STRING", "description": "الجهة الحكومية أو الخاصة المصدِرة"},
        "submission_deadline": {"type": "STRING"},
        # مدة العقد سقفٌ يُقاس عليه الجدول الزمني: خطة تتجاوزها غير قابلة
        # للتنفيذ مهما حسُنت، ولجنة الفحص تردّها.
        "contract_duration": {
            "type": "STRING",
            "description": (
                "مدة تنفيذ العقد كما وردت نصاً (مثال: «اثنا عشر شهراً» أو "
                "«365 يوماً»). اكتب «غير محدد في المرفقات» إن لم ترد."
            ),
        },
        # سريان العرض والضمان الابتدائي موعدان يُغفَلان فيسقط العرض شكلياً
        # وهو مكتمل فنياً.
        "offer_validity": {
            "type": "STRING",
            "description": "مدة سريان العرض المطلوبة كما وردت، أو «غير محدد في المرفقات»",
        },
        "bid_bond": {
            "type": "STRING",
            "description": (
                "شرط الضمان الابتدائي كما ورد: نسبته ومدة سريانه وصيغته. "
                "لا تكتب مبلغاً مقدَّراً من عندك."
            ),
        },
        "scope_summary": {"type": "STRING"},
        "key_deliverables": {"type": "ARRAY", "items": {"type": "STRING"}},
        "technical_constraints": {"type": "ARRAY", "items": {"type": "STRING"}},
        "contractual_penalties": {"type": "ARRAY", "items": {"type": "STRING"}},
        "required_certifications": {"type": "ARRAY", "items": {"type": "STRING"}},
        "local_content_requirements": {"type": "STRING"},
    },
    "required": [
        "project_title", "issuing_entity", "submission_deadline", "scope_summary",
        "key_deliverables", "technical_constraints", "contractual_penalties",
        "required_certifications", "local_content_requirements",
    ],
}

# الجدول الزمني — قسم إلزامي كان يخرج نصاً حراً بلا مراحل ولا اعتماديات ولا
# معالم قابلة للتحقق، فلا يُقاس على مدة العقد ولا يُرسم.
#
# `payment_milestone` علامة **لا مبلغ**: تخدم الفريق التجاري داخل النظام،
# و**تُستبعد من المخرَج الفني** — الفني والمالي مظروفان منفصلان.
TIMELINE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "contract_duration_weeks": {
            "type": "INTEGER",
            "description": (
                "مدة العقد بالأسابيع كما تفهمها من الكراسة. ضع 0 إن لم تُذكر — "
                "لا تُقدّرها من عندك."
            ),
        },
        "phases": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "phase_number": {"type": "INTEGER", "description": "ترتيب المرحلة بدءاً من 1"},
                    "phase_name": {"type": "STRING"},
                    "start_week": {
                        "type": "INTEGER",
                        "description": "أسبوع البداية نسبةً إلى بدء العقد (الأسبوع 1 = أول أسبوع)",
                    },
                    "duration_weeks": {"type": "INTEGER", "description": "مدة المرحلة بالأسابيع"},
                    "depends_on": {
                        "type": "STRING",
                        "description": "أرقام المراحل السابقة التي تعتمد عليها، مفصولة بفاصلة. فارغ إن لا اعتمادية.",
                    },
                    "deliverables": {
                        "type": "STRING",
                        "description": "تسليمات هذه المرحلة كما تشترطها الكراسة",
                    },
                    "payment_milestone": {
                        "type": "BOOLEAN",
                        "description": "هل تنتهي المرحلة بمعلم دفع؟ علامة فقط بلا أي مبلغ أو نسبة.",
                    },
                    "weight_percent": {
                        "type": "NUMBER",
                        "description": "وزن **الإنجاز** لهذه المرحلة من 100 — نسبة تقدّم لا نسبة دفع.",
                    },
                },
                "required": ["phase_number", "phase_name", "start_week", "duration_weeks"],
            },
        },
    },
    "required": ["phases"],
}

# الأقسام الإلزامية وفق معايير الشراء الحكومي السعودي (اعتماد).
#
# المنهجية منفصلة عن الجدول الزمني عمداً: خلطهما يُنتج قسماً يصف "كيف" و"متى"
# معاً فيضعف الاثنان، بينما تُقيّمهما لجان اعتماد بمعيارين مستقلين.
#
# المحتوى المحلي ليس ضمن الستة القياسية لكنه إلزامي في المنافسات السعودية وله
# وزن في التقييم — حذفه يُفقد درجات لا يعوّضها حسن الصياغة.
MANDATORY_OUTLINE_SECTIONS = [
    "الملخص التنفيذي",
    "ملف الشركة والخبرات ذات الصلة",
    "المنهجية الفنية المقترحة وخطة التنفيذ",
    "الجدول الزمني ومعالم التسليم",
    "الهيكل التنظيمي والكوادر الرئيسية",
    "ضمان الجودة وإدارة مستويات الخدمة",
    "الالتزام بالمحتوى المحلي",
]

OUTLINE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "proposal_title": {
            "type": "STRING",
            "description": "عنوان العرض الفني المقترح لهذه المنافسة",
        },
        "outline": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "section_id": {
                        "type": "INTEGER",
                        "description": "ترتيب القسم في المستند، بدءاً من 1",
                    },
                    "section_title": {"type": "STRING", "description": "عنوان القسم"},
                    "purpose": {
                        "type": "STRING",
                        "description": "وصف موجز لما يجب أن يغطيه هذا القسم",
                    },
                    "key_points_to_address": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"},
                        "description": "النقاط الجوهرية الواجب تناولها في هذا القسم",
                    },
                    "priority": {"type": "STRING", "enum": ["عالية", "متوسطة", "منخفضة"]},
                },
                "required": [
                    "section_id", "section_title", "purpose", "key_points_to_address",
                ],
            },
        },
    },
    "required": ["proposal_title", "outline"],
}

# مستندات المظروف: ما يجب إرفاقه حتى يُقبل العرض شكلياً.
SUBMISSION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "documents": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "document": {
                        "type": "STRING",
                        "description": "اسم المستند كما تسمّيه الكراسة",
                    },
                    "clause_reference": {
                        "type": "STRING",
                        "description": "رقم البند الذي اشترطه، أو فارغ إن لم يُذكر",
                    },
                    "mandatory": {
                        "type": "BOOLEAN",
                        "description": (
                            "true إذا كان غيابه سبب استبعاد، false إن كان مُحسِّناً "
                            "أو مطلوباً عند الترسية فقط."
                        ),
                    },
                    "notes": {
                        "type": "STRING",
                        "description": (
                            "شرط خاص بالمستند: مدة سريان، جهة إصدار، صيغة، "
                            "نسبة، تصديق."
                        ),
                    },
                },
                "required": ["document", "mandatory"],
            },
        },
    },
    "required": ["documents"],
}

# مصفوفة التتبّع: ربط كل متطلب بالقسم الذي عالجه فعلاً في نص العرض.
TRACEABILITY_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "coverage": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "req_id": {
                        "type": "STRING",
                        "description": "معرّف المتطلب كما ورد حرفياً في المصفوفة",
                    },
                    "status": {
                        "type": "STRING",
                        "enum": ["مغطّى", "جزئي", "غير مغطّى"],
                        "description": (
                            "مغطّى: عولج المتطلب صراحةً وبما يكفي. "
                            "جزئي: ذُكر دون استيفاء. "
                            "غير مغطّى: لا أثر له في نص العرض."
                        ),
                    },
                    "sections": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"},
                        "description": (
                            "عناوين الأقسام التي عالجته حرفياً كما وردت في "
                            "قائمة الأقسام. فارغة إن كان غير مغطّى."
                        ),
                    },
                    "evidence": {
                        "type": "STRING",
                        "description": (
                            "اقتباس قصير من نص العرض يُثبت التغطية. "
                            "لا تكتب اقتباساً غير موجود حرفياً في النص."
                        ),
                    },
                    "gap": {
                        "type": "STRING",
                        "description": (
                            "ما الناقص تحديداً في حالتَي جزئي وغير مغطّى. "
                            "اتركه فارغاً إن كان مغطّى."
                        ),
                    },
                },
                "required": ["req_id", "status", "sections"],
            },
        },
    },
    "required": ["coverage"],
}

# مصفوفة الكوادر الرئيسية (12-2): دور تشترطه الكراسة ← المرشّح من سجل
# الكوادر ← دليل المطابقة ← الفجوة. الدور بلا مرشّح فجوة صريحة لا صمت.
KEY_PERSONNEL_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "roles": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "required_role": {
                        "type": "STRING",
                        "description": "الدور كما تشترطه الكراسة حرفياً",
                    },
                    "clause_reference": {
                        "type": "STRING",
                        "description": "رقم البند الذي اشترط الدور، أو نص فارغ",
                    },
                    "requirements": {
                        "type": "STRING",
                        "description": (
                            "ما تشترطه الكراسة في شاغل الدور: سنوات الخبرة، "
                            "الشهادات، اللغة، التفرّغ."
                        ),
                    },
                    "candidate": {
                        "type": "STRING",
                        "description": (
                            "اسم المرشّح من سجل كوادر الشركة حرفياً كما ورد "
                            "فيه. اتركه فارغاً إن لم يوجد في السجل من يطابق — "
                            "**لا تخترع اسماً ولا تقترح توظيفاً**."
                        ),
                    },
                    "evidence": {
                        "type": "STRING",
                        "description": (
                            "ما في صف المرشّح يُثبت المطابقة: سنوات خبرته "
                            "وشهاداته كما وردت في السجل. فارغ إن لا مرشّح."
                        ),
                    },
                    "gap": {
                        "type": "STRING",
                        "description": (
                            "الفجوة تحديداً: لا مرشّح، أو سنوات أقل، أو شهادة "
                            "ناقصة أو منتهية، أو إتاحة غير كافية. "
                            "اتركه فارغاً عند المطابقة التامة."
                        ),
                    },
                },
                "required": ["required_role", "requirements"],
            },
        },
    },
    "required": ["roles"],
}

REVIEW_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "readiness_score": {
            "type": "INTEGER",
            "description": (
                "درجة جاهزية العرض من زاويتك من 0 إلى 100. "
                "دون 60 يعني غير جاهز للتسليم."
            ),
        },
        "assessment": {
            "type": "STRING",
            "description": "تقييم موجز في سطرين لحالة العرض من زاويتك",
        },
        "strengths": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": (
                "نقاط القوة الفعلية في العرض من زاويتك. "
                "لا تُدرج مجاملات عامة — كل نقطة تشير إلى شيء مكتوب في العرض."
            ),
        },
        "recommendations": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "توصيات قابلة للتنفيذ مرتّبة حسب الأثر",
        },
        "findings": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "section": {
                        "type": "STRING",
                        "description": "اسم القسم الذي تنطبق عليه الملاحظة",
                    },
                    "severity": {"type": "STRING", "enum": ["حرجة", "متوسطة", "طفيفة"]},
                    "issue": {"type": "STRING", "description": "وصف المشكلة"},
                    "impact": {
                        "type": "STRING",
                        "description": "أثرها على تقييم العرض أو قبوله",
                    },
                    "suggested_text": {
                        "type": "STRING",
                        "description": (
                            "الصياغة أو الإضافة المقترحة لمعالجة الملاحظة. "
                            "اتركه فارغاً إن كانت المعالجة تتطلب قراراً بشرياً "
                            "أو معلومة لا تملكها."
                        ),
                    },
                },
                "required": ["section", "severity", "issue", "impact"],
            },
        }
    },
    "required": [
        "readiness_score", "assessment", "strengths", "recommendations", "findings",
    ],
}


# ─── قوالب التعليمات المتخصصة ─────────────────────────────────────────────────

PROMPTS = {
    "gonogo": """أنت خبير في إدارة العطاءات الحكومية السعودية. حلّل كراسة الشروط
التالية وأعطِ توصية Go/No-Go **لهذه الشركة تحديداً** لا للمنافسة في المطلق.

قواعد الحكم:
1. قارن متطلبات التأهيل في الكراسة بما يثبته **سجلات أدلة الشركة** (الكوادر،
   سابقة الأعمال، الشهادات والتصنيفات، الموردون) ثم ملفها ومستودع معرفتها.
   **الصف في السجل أقوى من أي نص حر**: إن وُجد صف يطابق المتطلب فاذكره
   بمعرّفه (اسم الشخص أو العميل أو رقم الشهادة) في عمود المستند/الدليل.
2. **ما لا يوجد له إثبات في المعطيات يُعامَل ناقصاً لا متوفراً.** افتراض
   امتلاك شهادة لأن الشركة "تبدو مؤهلة" هو ما يُنتج قرار خوض خاطئ.
   وغياب الصف يُكتب "غير معلوم" لا "لا" — الفرق أن الأول يُراجَع والثاني يُبنى عليه.
3. ميّز بين ما **يمنع التأهل** (شرط إلزامي غير مستوفى) وما **يُضعف التنافسية**
   (نقص يخصم درجات). الأول وحده سبب NO-GO.
4. التوصية اقتراح لا حكم: القرار النهائي بشري، فاذكر ما يقلبه.

الهيكل المطلوب:
## توصية الملاءمة: [GO ✅ / NO-GO ❌]
(اذكر بعدها سبباً واحداً حاسماً في سطر)

### 🎯 مطابقة قدرات الشركة
| متطلب التأهيل في الكراسة | لدى الشركة؟ | المستند/الدليل |
|---|---|---|
(صف لكل متطلب تأهيل. "غير معلوم" حين لا دليل — لا تكتب "نعم" بلا سند.)

### 🚧 فجوات التأهيل
- (ما ينقص الشركة للتأهل، وهل يمكن سدّه قبل الموعد النهائي أم لا)
- (اكتب "لا فجوات ظاهرة في المعطيات" إن لم تجد)

### ✅ نقاط القوة (Opportunities)
- (ما يجعل هذه الشركة تحديداً مرشحاً قوياً)

### ⚠️ المخاطر الرئيسية (Risks)
- (قائمة مختصرة مع مستوى الخطورة: عالي/متوسط/منخفض)

### 📋 الشروط الحاكمة الحرجة
- (المتطلبات الإلزامية فقط)

### 💡 التوصية النهائية
(فقرة مختصرة تذكر: ما الذي يجب التحقق منه بشرياً قبل اعتماد القرار)

{language_instruction}""",

    "eval_matrix": """أنت محلل عطاءات. استخرج من الكراسة التالية مصفوفة معايير التقييم والأوزان.

الهيكل المطلوب:
## مصفوفة التقييم

| المعيار | الوزن % | المتطلبات الرئيسية | أولوية التركيز |
|---------|---------|-------------------|----------------|

### 📌 ملاحظات استراتيجية
- (توصيات لتعظيم الدرجة في كل معيار)

{language_instruction}""",

    "compliance": """أنت مستشار امتثال. استخرج من الكراسة جميع الشروط الإلزامية القانونية والتقنية.

الهيكل المطلوب:
## الشروط الحاكمة الإلزامية

### 🔴 متطلبات التأهيل (Pass/Fail)
- (الشروط التي يؤدي عدم استيفائها إلى الاستبعاد الفوري)

### 🟡 متطلبات الامتثال التقني
- (المواصفات والمعايير المطلوبة)

### 🟢 الشهادات والاعتمادات المطلوبة
- (قائمة الشهادات مع جهة الإصدار)

### ⚡ فجوات الامتثال المحتملة
- (مناطق الخطر التي تحتاج معالجة)

{language_instruction}""",

    "scope": """أنت مهندس حلول. اكتب قسم "فهمنا للنطاق والمتطلبات" في عرض فني، مستنداً إلى كراسة الشروط المرفقة.

الهيكل المطلوب:
## فهم النطاق والمتطلبات

### 1. الهدف من المشروع كما تفهمه الجهة
### 2. نطاق الأعمال والتسليمات المطلوبة
### 3. المتطلبات الوظيفية وغير الوظيفية الرئيسية
### 4. الافتراضات والحدود (ما يقع خارج النطاق)
### 5. عوامل النجاح الحرجة

اكتبه بصيغة عرض مقدَّم للجهة (نحن نفهم أن...) لا بصيغة تقرير داخلي.
{language_instruction}""",

    "methodology": """أنت مهندس حلول متخصص في مشاريع تقنية المعلومات الحكومية السعودية.
اكتب منهجية فنية احترافية للعرض.

بيانات الشركة: {company_overview}
معايير التقييم والأوزان: {eval_weights}
الشروط الحاكمة: {compliance_summary}

الهيكل المطلوب:
## المنهجية الفنية والحل المقترح

### 1. فهمنا للمشروع
### 2. نهجنا وأسلوب التنفيذ
### 3. الحل التقني المقترح
### 4. مزايانا التنافسية
### 5. ضمان الجودة وإدارة المخاطر

{language_instruction}""",

    "section": """أنت كاتب عروض فنية خبير متخصص في المنافسات الحكومية
والمؤسسية السعودية. اكتب القسم المحدّد من العرض الفني بلغة رسمية مُقنعة.

بيانات القسم:
- العنوان: {title}
- الغرض: {purpose}
- النقاط الجوهرية الواجب تناولها:
{guidance}

سياق الشركة: {company_overview}
معايير التقييم والأوزان المعتمدة: {eval_weights}
الشروط الحاكمة المعتمدة: {compliance_summary}

توجيهات المستخدم الخاصة بهذا القسم:
{user_steering}

معايير الكتابة:
1. **النبرة**: موثوقة، بمستوى تنفيذي، مهنية، ومتوافقة مع معايير الشراء الحكومي
   السعودي. وإن كانت المخرجات بالعربية فبالفصحى المعتمدة في المراسلات
   الرسمية — لا عامية ولا ترجمة حرفية عن الإنجليزية.
2. **عمق المحتوى**: قدّم منهجية ملموسة وأطر عمل واضحة وتدفّقات تشغيلية وأدلة
   متخصصة بالمجال، لا عبارات عامة عالية المستوى.
3. **البنية**: استخدم عناوين واضحة ونقاطاً وقوائم مرقّمة وجداول حيثما يفيد.
4. **الفصل الصارم**: **لا تذكر أي تسعير أو أرقام أو قيم مالية** في هذا القسم
   الفني إطلاقاً.
5. **السياق المحلي**: أبرز التوافق مع المعايير الوطنية وأهداف المحتوى المحلي
   والأطر التنظيمية السعودية حيثما كان ذا صلة.
6. لا تخترع أرقاماً ولا أسماء عملاء ولا مراجع مشاريع. إن لزمت معلومة لا
   تملكها فضعها بين أقواس مربعة [ ] ليعبّئها الفريق.
7. اكتب محتوى القسم مباشرةً بلا مقدمات ولا تعليق وصفي على ما تفعله.

{language_instruction}""",

    "ask": """أنت مستشار عروض فنية. المستخدم يسألك عن قسم يكتبه في عرض فني
لمنافسة حكومية سعودية. **أجب عن سؤاله فقط ولا تُعِد كتابة القسم.**

نص القسم الحالي:
{content}

سؤال المستخدم:
{question}

تعليمات:
1. أجب بإيجاز ومباشرة، مستنداً إلى نص القسم وسياق المنافسة المرفق.
2. إن كان الجواب غير موجود في المعطيات فقل ذلك صراحةً ولا تُخمّن. عدم المعرفة
   جواب صحيح؛ التخمين هنا يُبنى عليه قرار خاطئ.
3. إن كانت التغطية ناقصة فبيّن **ما الناقص تحديداً** وأين موضعه من القسم.
4. لا تُخرج نصاً بديلاً للقسم ولا فقرات جاهزة للصق. إن أراد المستخدم تعديلاً
   فذكّره باستخدام زر تطبيق التعديل.
5. لا تذكر أي تسعير أو أرقام مالية.

{language_instruction}""",

    "refine": """أنت محرّر عروض فنية آني. نقّح نص القسم التالي وفق طلب التعديل
الصريح من المستخدم.

نص القسم الحالي:
{content}

طلب التعديل:
{edit_request}

تعليمات:
1. طبّق تعديل المستخدم بدقة مع الإبقاء على الحقائق الفنية الجوهرية والنبرة
   المهنية.
2. لا تُدخل أي تسعير أو أرقام مالية — القسم فني بحت.
3. لا تخترع معلومة جديدة لتلبية الطلب؛ إن لزمت معلومة لا تملكها فضعها بين
   أقواس مربعة [ ].
4. أخرج نص القسم المنقّح مباشرةً بلا عبارات تمهيدية من نوع "إليك النسخة
   المنقّحة".

{language_instruction}""",

    "project_plan": """أنت مدير مشاريع معتمد PMP. اكتب خطة مشروع عالية المستوى لمشروع تقنية معلومات حكومي.

بيانات الشركة: {company_name}
سياق المشروع: {project_context}

الهيكل المطلوب:
## خطة المشروع والجدول الزمني

### 1. مراحل المشروع الرئيسية (Milestones)
### 2. جدول زمني تقديري (Gantt مبسط بالأشهر)
### 3. الموارد البشرية المطلوبة
### 4. نقاط التحكم والتسليمات الرئيسية
### 5. إدارة المخاطر والطوارئ

{language_instruction}""",
}


# ─── تعليمات الاستخراج المُهيكل ───────────────────────────────────────────────

EXTRACT_PROMPTS = {
    "compliance_items": """أنت مسؤول امتثال ما قبل البيع. ابنِ مصفوفة امتثال صارمة
تربط **كل** متطلب في كراسة الشروط باستراتيجية استجابة مقترحة.

قواعد:
1. أدرج كل المتطلبات الصريحة والضمنية الواردة في سياق المنافسة.
2. req_id: معرّف متسلسل بصيغة REQ-001، REQ-002 … بلا فجوات.
3. category: صنّف كل متطلب إلى Technical أو Operational أو Administrative
   أو Legal (بالإنجليزية حرفياً كما هي).
4. criticality: High أو Medium أو Low (بالإنجليزية حرفياً).
   High لما يؤدي عدم استيفائه للاستبعاد أو لخسارة درجات جوهرية.
5. clause_reference: رقم البند أو الصفحة في الكراسة إن توفّر، وإلا نص فارغ.
6. requirement_summary: بصياغة الكراسة نفسها قدر الإمكان لا بإعادة صياغة عامة.
7. proposed_compliance_strategy: كيف يستوفي عرضنا هذا المتطلب عملياً.
   إن لزمت معلومة لا تملكها فضعها بين أقواس مربعة [ ] ليعبّئها الفريق.
8. mandatory = true فقط لما يؤدي عدم استيفائه للاستبعاد الفوري.
9. لا تخترع متطلبات غير واردة في النص.""",

    "boq_items": """أنت أخصائي بيانات مشتريات خبير في منافسات القطاع العام السعودي
(اعتماد وفرصة). مهمتك استخراج بيانات جدول الكميات (BOQ) الخام وهيكلتها
وتنقيتها في مخطط موحّد.

قواعد:
1. حلّل كل بند سطراً سطراً بدقة.
2. الدقة المطلقة مطلوبة — لا تُسقط أي بند ولا تُقرّب أي قيمة رقمية.
3. item_number: الرقم التسلسلي أو رمز البند كما ورد في المصدر حرفياً.
4. quantity رقم. إن لم تُذكر كمية صراحةً فاستخدم 1.
5. specifications و construction_code: انقلهما كما وردا؛ اترك الحقل فارغاً
   إن لم يردا بدل اختراعهما.
6. mandatory_list_flag: ضع true فقط إذا دلّت مستندات المنافسة أو القائمة
   المرجعية المرفقة على أن البند ضمن القائمة الإلزامية للمحتوى المحلي.
   عند الشك ضع false — سيراجعها فريق المشتريات يدوياً.
7. لا تضع أسعاراً — التسعير مسؤولية الفريق المالي.
8. إن لم يرد جدول كميات صريح، استنتج البنود القابلة للتسعير من نطاق العمل.""",

    "project_context": """أنت محلل سياق كراسات أول. حلّل ودمج جميع مرفقات
المنافسة المرفوعة (كراسة الشروط، الملاحق الفنية، المواصفات) في سياق معرفي
واحد مُهيكل للمشروع.

قواعد:
1. استخرج عنوان المشروع، الجهة المصدِرة (حكومية أو خاصة)، الموعد النهائي
   للتقديم، والشروط القانونية والتعاقدية.
2. حدّد ركائز النطاق الأساسية، والتسليمات الفنية، ومتطلبات مستوى الخدمة،
   وبنود الغرامات.
3. تحقّق صراحةً من قيود الامتثال: قواعد المحتوى المحلي، الضمانات البنكية
   المطلوبة، والشهادات الإلزامية.
4. لا تخترع معلومة غير واردة في المرفقات. إن لم يرد الموعد النهائي أو أي
   حقل آخر، اكتب "غير محدد في المرفقات".""",

    "submission_docs": """أنت مسؤول تأهيل في منافسة حكومية سعودية. استخرج من
الكراسة **كل مستند يجب إرفاقه** مع العرض حتى يُقبل شكلياً.

قواعد:
1. استخرج ما تشترطه **هذه الكراسة** نصاً. لا تنسخ قائمة عامة محفوظة، والمستند
   الذي لا أثر له في الكراسة لا يُدرَج.
2. غطِّ ما يُغفَل عادةً إن اشترطته الكراسة: السجل التجاري · شهادة الزكاة
   والضريبة · التأمينات الاجتماعية · شهادة السعودة (نطاقات) · تصنيف المقاولين ·
   الضمان الابتدائي · نماذج العرض الموقّعة والمختومة · إقرار عدم تعارض المصالح ·
   شهادة تسجيل ضريبة القيمة المضافة · وثائق المحتوى المحلي.
3. mandatory = true فقط إذا كان غيابه **سبب استبعاد**. المطلوب عند الترسية لا
   عند التقديم يُدرَج بـ false مع بيان ذلك في notes.
4. notes: اذكر شرط المستند إن وُجد — مدة السريان، جهة الإصدار، الصيغة، النسبة
   المطلوبة، الحاجة إلى تصديق.
5. لا تحكم على ما إذا كانت الشركة تملك المستند؛ لا علم لك بذلك.""",

    "timeline_items": """أنت مدير مشاريع معتمد PMP يبني الجدول الزمني لعرض فني
في منافسة حكومية سعودية. استخرج من الكراسة خطة زمنية **مُهيكلة** بمراحل
واعتماديات وتسليمات.

قواعد:
1. اشتقّ المراحل من **نطاق العمل والتسليمات في هذه الكراسة**، لا من قائمة
   عامة محفوظة. مرحلة لا تخدم تسليماً أو شرطاً لا تُدرَج.
2. contract_duration_weeks: مدة العقد بالأسابيع كما وردت في الكراسة. إن لم
   تُذكر ضع 0 — **لا تُقدّرها**، فالخطة تُقاس عليها ورقم مختلَق يُبطل القياس.
3. start_week و duration_weeks بالأسابيع نسبةً إلى بدء العقد؛ الأسبوع 1 هو
   أول أسبوع. لا تستعمل تواريخ ميلادية — تاريخ الترسية غير معلوم بعد.
4. مجموع المدة من أول مرحلة إلى آخرها **يجب ألّا يتجاوز مدة العقد** إن ذُكرت.
5. depends_on: أرقام المراحل السابقة اللازم إنجازها أولاً. لا تجعل مرحلة تبدأ
   قبل انتهاء ما تعتمد عليه — التداخل بلا مبرر يُقرأ خطةً غير واقعية.
6. deliverables: تسليمات المرحلة كما تشترطها الكراسة. **كل تسليم رئيسي في
   الكراسة يجب أن يقع في مرحلة**.
7. weight_percent: وزن **الإنجاز** لا الدفع، ومجموع الأوزان 100.
8. payment_milestone: علامة فقط. **لا تكتب أي مبلغ ولا نسبة دفع ولا قيمة
   مالية في أي حقل** — هذا جدول عرض فني.""",

    "traceability": """أنت مدقّق تتبّع متطلبات في عرض فني لمنافسة حكومية سعودية.
مهمتك ربط كل متطلب في مصفوفة الامتثال بالقسم الذي عالجه فعلاً في نص العرض.

قواعد:
1. احكم على **ما هو مكتوب فعلاً** لا على ما يُفترض أن يُكتب. عنوان قسم يوحي
   بالتغطية لا يكفي؛ المطلوب معالجة صريحة في المتن.
2. "مغطّى" تعني أن قارئ لجنة الفحص سيجد جواب المتطلب دون اجتهاد. إن احتاج
   استنتاجاً فهو "جزئي".
3. evidence اقتباس **حرفي قصير** من نص العرض. لا تُعِد صياغته ولا تخترعه؛
   الاقتباس المُختلق يجعل المدقّق يثق بتغطية غير موجودة.
4. sections: عناوين من قائمة الأقسام المعطاة حرفياً لا عناوين من عندك.
5. gap: في "جزئي" و"غير مغطّى" حدّد **ما الناقص** بجملة قابلة للتنفيذ.
6. غطِّ كل معرّف في المصفوفة ولا تُسقط أياً منه. المتطلب الذي لا تجده يُسجَّل
   "غير مغطّى" لا يُحذف.
7. لا تقترح تسعيراً ولا تُعلّق على الجانب المالي.

مصفوفة الامتثال:
{requirements}

أقسام العرض ونصوصها:
{sections}""",

    "key_personnel": """أنت مسؤول تأهيل كوادر في منافسة حكومية سعودية. استخرج من
الكراسة **كل دور وظيفي تشترطه**، وطابقه بسجل كوادر الشركة المرفق.

قواعد:
1. استخرج الأدوار التي **تشترطها هذه الكراسة** نصاً (مدير مشروع · مهندس شبكات ·
   مسؤول أمن معلومات …) بشروطها: سنوات الخبرة، الشهادات، اللغة، التفرّغ.
   دور لا أثر له في الكراسة لا يُدرَج.
2. candidate: اسم من **سجل الكوادر المرفق حرفياً**. إن لم يوجد فيه من يطابق
   الدور فاترك الحقل فارغاً واكتب الفجوة. **لا تخترع اسماً، ولا تقترح
   توظيفاً، ولا تسمِّ شخصاً غير موجود في السجل** — الاسم المُختلق يمرّ إلى
   العرض فيُكتشف عند التحقق ويُسقط المنافسة.
3. evidence: ما في صف المرشّح يُثبت المطابقة (سنوات خبرته وشهاداته كما وردت).
   لا تنسب إليه شهادة ليست في صفه.
4. gap: حدّد النقص بدقّة — لا مرشّح · سنوات أقل من المشترط · شهادة ناقصة ·
   شهادة منتهية قبل الموعد · إتاحة غير كافية.
5. **كل دور تشترطه الكراسة يجب أن يكون له صف**، ولو بلا مرشّح. الدور الذي
   يُحذف لأنه بلا مرشّح هو الفجوة التي ستُكتشف في لجنة الفحص.
6. لا تذكر رواتب ولا أي قيمة مالية.

سجل كوادر الشركة:
{people}""",

    "outline": """أنت مهندس حلول أول لما قبل البيع في المشتريات الحكومية السعودية.
بناءً على سياق المنافسة ونطاق جدول الكميات، اقترح هيكل عرض فني مُهيكلاً ورابحاً
مُفصَّلاً **لهذه المنافسة تحديداً**.

قواعد:
1. صمّم هيكلاً منطقياً قسماً بقسم يلتزم بمعايير الشراء الحكومي السعودي
   (إرشادات اعتماد)، بتسلسل يبني الإقناع: من فهم حاجة الجهة، إلى إثبات القدرة
   على تلبيتها، إلى كيفية التنفيذ، إلى ضمان النتيجة.
2. **افصل الجانب الفني عن التسعير فصلاً تاماً** — لا تُدرج أي قيمة مالية أو
   سعر أو تكلفة في العرض الفني، ولا قسماً غرضه التسعير. جدول الكميات مُعطى
   لتعرف **نطاق العمل** لا لتسعّره.
3. الأقسام الإلزامية التي يجب أن يتضمنها الهيكل:
{mandatory_sections}
4. المنهجية والجدول الزمني **قسمان منفصلان**: الأول يصف كيف يُنفَّذ العمل،
   والثاني متى — بمراحل ومعالم تسليم مرتبطة بمدة العقد في الكراسة.
   ويجب أن تتضمن نقاط قسم المنهجية **استراتيجية إدارة المخاطر والحد منها**؛
   عرض بلا معالجة للمخاطر يبدو غير واقعي أمام لجنة الفحص. ولا تُدرج ضمان
   الجودة ومستويات الخدمة داخل المنهجية — لها قسمها الإلزامي المستقل.
5. section_id: ترتيب القسم في المستند بدءاً من 1 بلا فجوات.
6. purpose: وصف موجز لما يجب أن يغطيه القسم في هذه المنافسة بالذات.
7. key_points_to_address: النقاط الجوهرية الواجب تناولها — اشتقّها من معايير
   التقييم ومتطلبات الكراسة وبنود جدول الكميات، لا من قائمة عامة محفوظة.
8. اجعل كل قسم مبنياً على ما يكسب درجات في هذه المنافسة: اربطه بمعيار تقييم أو
   متطلب صريح في الكراسة. لا تضف قسماً لا يخدم درجة أو شرطاً.
9. إن نصّت الكراسة على أقسام أو ترتيب معيّن للعرض الفني فالتزم به حرفياً
   وأضف الأقسام الإلزامية أعلاه إن لم تتعارض معه.
10. priority = "عالية" للأقسام ذات الوزن الأكبر في التقييم.
11. proposal_title: عنوان مناسب للعرض الفني لهذه المنافسة.""",
}


# ─── لجنة المراجعة قبل التسليم: ثلاثة وكلاء ──────────────────────────────────
#
# كل وكيل عضو في لجنة مراجعة أولى لعرض مقدَّم على منصة اعتماد. الوكلاء يعملون
# باستقلال متعمَّد: تشغيل كل زاوية باستدعاء منفصل يمنع الوكيل الفني من تبرير
# ثغرة قانونية والعكس، ويُبقي درجة كل زاوية معبّرة عن زاويتها وحدها.

_PANEL_PREAMBLE = """أنت عضو في لجنة من ثلاثة مراجعين أوّلين لمرحلة ما قبل البيع،
تُقيّم مسودة عرض مكتملة قبل تقديمها على منصة اعتماد / فرصة السعودية.

راجع بصرامة. لا تجامل: درجة مرتفعة بلا سند تُضلّل فريق العطاء وتكلّفه المنافسة.
احتفظ بزاويتك وحدها ولا تُراجع زوايا زملائك."""

_PANEL_OUTPUT_RULES = """
المخرجات المطلوبة منك:
- readiness_score: درجة جاهزية العرض من زاويتك من 0 إلى 100. دون 60 = غير جاهز للتسليم.
- assessment: تقييم موجز في سطرين.
- strengths: نقاط القوة الفعلية المكتوبة في العرض — لا مجاملات عامة.
- recommendations: توصيات عالية الأولوية قابلة للتنفيذ ترفع احتمال الفوز، مرتّبة حسب الأثر.
- findings: الثغرات المرصودة، كل ثغرة مربوطة بالقسم الذي تنطبق عليه وبخطورتها.
  ضع نصاً بديلاً جاهزاً في suggested_text حيثما أمكن، واتركه فارغاً إذا كانت
  المعالجة تتطلب قراراً بشرياً أو معلومة لا تملكها (رقم، اسم، مرجع مشروع سابق)."""

REVIEW_LENSES = {
    "technical": {
        "label": "فنية",
        "icon": "🛠️",
        "prompt": f"""{_PANEL_PREAMBLE}

دورك: **الوكيل الفني**. قيّم الجدوى الفنية، وتغطية المنهجية، وواقعية الجدول
الزمني لخطة العمل، وقدرات الفريق، والالتزام بمستويات الخدمة (SLA).

ابحث عن:
- متطلبات فنية في الكراسة لم يغطها العرض إطلاقاً (أخطر نوع من الملاحظات).
- منهجية غير قابلة للتنفيذ أو لا تتناسب مع المدة المطروحة — مدد غير واقعية،
  مراحل متداخلة بلا مبرر، تسليمات بلا مهام تسبقها.
- هيكل فريق لا يغطي التخصصات المطلوبة، أو أدوار بلا إسناد، أو سير ذاتية
  لا تطابق المتطلبات.
- مستويات خدمة غائبة أو غير قابلة للقياس (بلا مؤشر، بلا مدة استجابة، بلا آلية قياس).
- ادعاءات عامة بلا إثبات ("خبرة واسعة"، "أحدث التقنيات") تُفقد درجات التقييم.
- تناقضات بين أقسام العرض، أو نص نائب لم يُعبَّأ بين أقواس [ ].
{_PANEL_OUTPUT_RULES}""",
    },
    "commercial": {
        "label": "تجارية",
        "icon": "💰",
        "prompt": f"""{_PANEL_PREAMBLE}

دورك: **الوكيل التجاري**. قيّم اتساق العرض مع جدول الكميات، ووضوح هيكل
التسعير، وعوامل مخاطر الكلفة، والالتزام بجدول الدفعات.

**الفصل المالي عن الفني شرط استبعاد لا ملاحظة تحسين**: العرض الفني يجب أن
يخلو من أي رقم سعري أو إشارة إلى قيمة مالية. إن وجدت أي تسعير داخل نص العرض
الفني فسجّله ملاحظة **حرجة** فوراً واخفض الدرجة بوضوح.

ابحث عن:
- بنود في نطاق العمل بلا ما يقابلها في جدول الكميات، أو العكس — أي اختلال
  بين ما وُعد به فنياً وما هو مُسعَّر.
- **حدود المسؤولية بين التوريد والتركيب والتشغيل والصيانة**: أيّها على المورّد
  وأيّها على الجهة؟ الغموض هنا يُقرأ لصالح الجهة عند التنفيذ فتتحمّل الشركة
  عملاً لم تُسعّره.
- غموض في هيكل التسعير أو الوحدات أو الكميات يفتح باب النزاع عند التنفيذ.
- عوامل مخاطر كلفة غير مسوّرة: نطاق مفتوح، تقلّب أسعار مواد، اعتماد على طرف
  ثالث بلا سقف، التزامات ممتدة بلا مقابل.
- عدم توافق مع جدول الدفعات ودفعات الإنجاز المطلوبة في الكراسة.
- ضعف ربط العرض بمعايير التقييم وأوزانها — أين تُهدر درجات؟
- غياب عناصر التمايز عن المنافسين، أو قيمة مضافة ممكنة بلا كلفة إضافية.
{_PANEL_OUTPUT_RULES}""",
    },
    "legal": {
        "label": "قانونية",
        "icon": "⚖️",
        "prompt": f"""{_PANEL_PREAMBLE}

دورك: **وكيل الالتزام القانوني**. قيّم الالتزام بنظام المنافسات والمشتريات
الحكومية السعودية ولائحته التنفيذية، والتزامات المحتوى المحلي والقائمة
الإلزامية، والضمانات بأنواعها، ومعالجة الغرامات التعاقدية.

ابحث عن:
- مخالفة أو تعارض مع نظام المنافسات والمشتريات الحكومية أو مع الشروط الحاكمة
  في الكراسة.
- تحفّظات أو استثناءات مكتوبة في العرض قد تُعدّ تحفظاً جوهرياً يستوجب الاستبعاد.
- التزامات المحتوى المحلي: نسبة غير معلنة، أو بنود القائمة الإلزامية بلا التزام
  صريح، أو وعد لا تسنده وثيقة.
- الضمان الابتدائي: قيمته ومدة سريانه وصيغته ومصدره البنكي — أي نقص هنا سبب
  استبعاد شكلي مباشر.
- الضمان النهائي: هل أقرّ العرض بتقديمه عند الترسية بالنسبة النظامية؟ غيابه
  يُقرأ تحفظاً على شرط جوهري.
- **فترة الضمان والكفالة على المُورَّد**: مدتها، وما تشمله وما تستثنيه، وزمن
  الاستجابة خلالها. عرض توريد بلا تعهد ضمان صريح ناقص أمام لجنة الفحص مهما
  حَسُنت منهجيته.
- الغرامات التعاقدية: هل عالجها العرض بخطة تخفيف واقعية أم تجاهلها؟
- التزامات قانونية مطلقة أو غير مسوّرة (تعويض غير محدود، ضمانات مطلقة).
- متطلبات نظامية مطلوبة ولم يُشَر إليها (السعودة، حماية البيانات، الملكية الفكرية،
  السرية، تعارض المصالح).
{_PANEL_OUTPUT_RULES}""",
    },
}
