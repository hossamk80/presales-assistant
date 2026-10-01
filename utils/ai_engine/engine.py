"""
utils/ai_engine/engine.py — الاستدعاء نفسه: إعادة المحاولة على الفشل العابر · التجزئة والدمج
للكراسات الكبيرة · المخرجات المُهيكلة · تجربة برومبت قبل اعتماده (14-3).

هنا وحده يُستدعى `utils/providers`، وهنا تُلحق القواعد الثابتة.
"""

import json
import re
import streamlit as st
import time

from typing import Any, Callable, Optional
from utils import providers
from utils.i18n import t
from utils.providers import BudgetExceeded, ProviderError

from .language import DEFAULT_LANGUAGE, language_instruction
from .models import CONTEXT_CHAR_BUDGET, DEFAULT_MODEL, estimate_tokens, resolve_model
from .prompts import active_prompt, default_prompt, prompt_fields, prompt_problem
from .rules import apply_fixed_rules
from .schemas import MANDATORY_OUTLINE_SECTIONS


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
          task: str = "write",
          on_chunk: Optional[Callable[[str], None]] = None) -> Optional[str]:
    """
    استدعاء واحد للنموذج عبر طبقة الموفّرين، مع إعادة محاولة عابرة.

    `on_chunk` (ب-2): تُستدعى بالنصّ **المتراكم** كلّما وصل مقطع، فتعرض الواجهة
    القسم وهو يُكتب. بدونها يبقى السلوك كما كان — استدعاء واحد ونتيجة واحدة.

    والنصّ الناقص **لا يُعاد** عند الفشل: `_with_retry` يرفع، فتعود `None`
    وتُبقي الواجهةُ نصَّ المستخدم كما هو (قاعدة ثابتة في المنتج). ما عُرض أثناء
    البثّ مؤقّت، وما يُكتب في القسم هو الناتج التامّ وحده.
    """
    prompt = apply_fixed_rules(prompt)          # 14-2: لا استدعاء بلا القواعد
    try:
        result = _with_retry(
            lambda: (providers.run_stream(model_id, prompt, task=task,
                                          on_chunk=on_chunk)
                     if on_chunk else
                     providers.run(model_id, prompt, task=task)),
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
    on_chunk: Optional[Callable[[str], None]] = None,
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
        return _call(prompt, model_id, on_progress, on_chunk=on_chunk)

    # المسار المعتاد: الكراسة كاملة في استدعاء واحد
    if len(rfp_context) <= CONTEXT_CHAR_BUDGET:
        return _call(f"{prompt}\n\n---\nنص الكراسة:\n{rfp_context}", model_id,
                     on_progress, on_chunk=on_chunk)

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


# ─── تجربة برومبت قبل اعتماده (14-3) ──────────────────────────────────────────
#
# تحرير التعليمات (14-1) بلا تجربة قمار: النص الجديد يسري على كل عرض تالٍ،
# وأثره لا يُعرف إلا في مخرَج عرض حقيقي. فالتجربة تُشغّل النصّين — الساري
# والمحرَّر — على **المنافسة المفتوحة نفسها** وتعرض الناتجين جنباً إلى جنب،
# **قبل أي حفظ**: النص المحرَّر يُمرَّر إلى النموذج مباشرةً ولا يلمس القاعدة.
#
# استدعاءان لا واحد: المقارنة بمخرَج محفوظ من تشغيل سابق تخلط أثر النص بأثر
# تغيّر السياق بينهما.

# قيم تُملأ تلقائياً لحقول القوالب من حالة الجلسة — ما يعرفه النظام يُملأ،
# وما لا يعرفه يتركه للمجرِّب.
def trial_field_defaults(key: str) -> dict:
    """قيم مبدئية لحقول القالب من المنافسة المفتوحة وملف الشركة."""
    from utils import state

    known = {
        "company_name": st.session_state.get("c_name", ""),
        "company_overview": (st.session_state.get("c_overview")
                             or st.session_state.get("c_name", "")),
        "eval_weights": st.session_state.get("sum_eval", ""),
        "compliance_summary": st.session_state.get("sum_comp", ""),
        "project_context": state.project_context_block(),
        "mandatory_sections": "\n".join(
            f"   - {name}" for name in MANDATORY_OUTLINE_SECTIONS
        ),
    }
    return {
        name: str(known.get(name, "") or "")
        for name in sorted(prompt_fields(default_prompt(key)) - {"language_instruction"})
    }


def trial_prompt(key: str, edited_text: str, model_choice: str = DEFAULT_MODEL,
                 fields: Optional[dict] = None, language: str = DEFAULT_LANGUAGE,
                 sector: str = "", rfp_context: str = "",
                 on_progress: Optional[Callable[[str], None]] = None) -> dict:
    """
    يشغّل النص الساري والنص المحرَّر على السياق نفسه ويعيد الناتجين.

    يعيد `{"current": …, "edited": …, "problem": …}` — و `problem` مفتاح i18n
    إن رُفضت التجربة قبل إنفاق أي توكن.
    """
    problem = prompt_problem(key, edited_text)
    if problem:
        return {"current": None, "edited": None, "problem": problem}

    values = {"language_instruction": language_instruction(language),
              **{k: str(v or "") for k, v in (fields or {}).items()}}
    current_text = active_prompt(key, sector, language)

    outputs = {}
    for label, template in (("current", current_text), ("edited", edited_text)):
        try:
            filled = template.format(**values)
        except (KeyError, IndexError, ValueError):
            # النص الساري قد يكون قديماً بحقول لم تعد تُملأ — لا تُسقط التجربة
            outputs[label] = None
            continue
        if on_progress:
            on_progress(label)
        outputs[label] = ai_generate(
            filled, model_choice=model_choice, rfp_context=rfp_context,
            language=language,
        )

    return {"current": outputs.get("current"), "edited": outputs.get("edited"),
            "problem": None}


def trial_cost_estimate(key: str, edited_text: str, fields: Optional[dict] = None,
                        rfp_context: str = "", sector: str = "") -> int:
    """تقدير توكنات المُدخل للتجربة كاملةً — استدعاءان لا واحد."""
    values = " ".join(str(v or "") for v in (fields or {}).values())
    both = active_prompt(key, sector) + str(edited_text or "")
    return estimate_tokens(both + values + (rfp_context or "") * 2)


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
