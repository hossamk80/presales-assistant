"""
utils/ai_engine.py — محرك الذكاء الاصطناعي (Google Gen AI SDK الموحّد)

يعتمد على حزمة `google-genai` — الحزمة القديمة `google-generativeai` مهجورة.
"""
import json
import re
import streamlit as st
from typing import Any, Callable, Optional

# ─── سجل النماذج ──────────────────────────────────────────────────────────────
# الاسم المعروض -> معرّف النموذج في الـ API
MODELS = {
    "Gemini 3.6 Flash": "gemini-3.6-flash",
    "Gemini 3.1 Pro": "gemini-3.1-pro",
    "Gemini 3.5 Flash-Lite": "gemini-3.5-flash-lite",
}
MODEL_NAMES = list(MODELS)
DEFAULT_MODEL = "Gemini 3.6 Flash"

# نافذة السياق مليون توكن. نترك هامشاً للتعليمات والرد وخطأ التقدير.
CONTEXT_TOKEN_BUDGET = 700_000

# النص العربي أكثف من الإنجليزي في التقطيع. نستخدم تقديراً متحفظاً حتى
# لا نتجاوز النافذة، ومعه `count_tokens_exact` عند الحاجة لرقم دقيق.
CHARS_PER_TOKEN = 2.5

CONTEXT_CHAR_BUDGET = int(CONTEXT_TOKEN_BUDGET * CHARS_PER_TOKEN)


def resolve_model(model_choice: str) -> str:
    """يحوّل الاسم المعروض إلى معرّف النموذج، مع تجاهل الأسماء القديمة."""
    return MODELS.get(model_choice, MODELS[DEFAULT_MODEL])


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
    """يملأ قالب تعليمات مع تعليمة اللغة المناسبة."""
    return PROMPTS[prompt_key].format(
        language_instruction=language_instruction(language), **fields
    )


def estimate_tokens(text: str) -> int:
    """تقدير سريع محلي لعدد التوكنز (بدون استدعاء الشبكة)."""
    return int(len(str(text)) / CHARS_PER_TOKEN)


@st.cache_resource(show_spinner=False)
def _get_client(api_key: str):
    """عميل genai مُخزَّن حسب المفتاح (يُعاد استخدامه بين عمليات إعادة التشغيل)."""
    from google import genai

    return genai.Client(api_key=api_key)


def get_client():
    """يُرجع عميلاً جاهزاً أو None مع رسالة خطأ واضحة."""
    api_key = st.session_state.get("api_gemini")
    if not api_key:
        st.error("⚠️ يرجى إدخال مفتاح Google Gemini API في **إعدادات النظام** أولاً.")
        return None
    try:
        return _get_client(api_key)
    except ImportError:
        st.error("❌ مكتبة google-genai غير مثبّتة. شغّل: pip install google-genai")
        return None
    except Exception as e:
        st.error(f"❌ تعذّر تهيئة عميل Gemini: {e}")
        return None


def count_tokens_exact(text: str, model_choice: str = DEFAULT_MODEL) -> Optional[int]:
    """عدد التوكنز الفعلي من الـ API. يُرجع None إذا تعذّر الاتصال."""
    client = get_client()
    if client is None:
        return None
    try:
        result = client.models.count_tokens(
            model=resolve_model(model_choice), contents=text
        )
        return result.total_tokens
    except Exception:
        return None


def _call(prompt: str, model_id: str) -> Optional[str]:
    """استدعاء واحد للنموذج."""
    client = get_client()
    if client is None:
        return None
    try:
        response = client.models.generate_content(model=model_id, contents=prompt)
        text = response.text
        if not text:
            st.warning("⚠️ رجع النموذج رداً فارغاً — قد يكون الطلب حُجب بفلاتر الأمان.")
            return None
        return text
    except Exception as e:
        st.error(f"❌ خطأ Gemini API: {e}")
        return None


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
        return _call(prompt, model_id)

    # المسار المعتاد: الكراسة كاملة في استدعاء واحد
    if len(rfp_context) <= CONTEXT_CHAR_BUDGET:
        return _call(f"{prompt}\n\n---\nنص الكراسة:\n{rfp_context}", model_id)

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
    )


# ─── المخرجات المُهيكلة (JSON) ────────────────────────────────────────────────


def _strip_code_fence(text: str) -> str:
    """إزالة أسوار Markdown إن أحاطت بالـ JSON."""
    stripped = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, re.DOTALL)
    return fence.group(1) if fence else stripped


def _call_json(prompt: str, model_id: str, schema: dict) -> Optional[Any]:
    """استدعاء يُرجع JSON مطابقاً للمخطط المحدّد."""
    client = get_client()
    if client is None:
        return None
    try:
        from google.genai import types

        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
    except Exception as e:
        st.error(f"❌ خطأ Gemini API: {e}")
        return None

    # المسار المفضّل: كائن مُحلَّل جاهز من الـ SDK
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, (dict, list)):
        return parsed

    raw = getattr(response, "text", None)
    if not raw:
        st.warning("⚠️ رجع النموذج رداً فارغاً — قد يكون الطلب حُجب بفلاتر الأمان.")
        return None

    try:
        return json.loads(_strip_code_fence(raw))
    except json.JSONDecodeError as e:
        st.error(f"❌ تعذّر تحليل رد النموذج كـ JSON: {e}")
        with st.expander("عرض الرد الخام"):
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
        return _call_json(prompt, model_id, schema)

    if len(rfp_context) <= CONTEXT_CHAR_BUDGET:
        return _call_json(f"{prompt}\n\n---\nنص الكراسة:\n{rfp_context}", model_id, schema)

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
    return {merge_key: merged}


# ─── مخططات الاستخراج ─────────────────────────────────────────────────────────

COMPLIANCE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "requirements": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "requirement": {
                        "type": "STRING",
                        "description": "نص المتطلب التقني أو الإداري كما ورد في الكراسة",
                    },
                    "category": {
                        "type": "STRING",
                        "enum": ["تأهيل", "فني", "إداري", "مالي"],
                    },
                    "mandatory": {
                        "type": "BOOLEAN",
                        "description": "هل عدم استيفائه يؤدي للاستبعاد؟",
                    },
                    "certificate": {
                        "type": "STRING",
                        "description": "الشهادة أو الوثيقة المطلوبة لإثباته، أو نص فارغ",
                    },
                    "source_ref": {
                        "type": "STRING",
                        "description": "رقم البند أو الصفحة في الكراسة إن توفّر",
                    },
                },
                "required": ["requirement", "category", "mandatory"],
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
                    "item": {"type": "STRING", "description": "اسم البند أو الخدمة"},
                    "description": {"type": "STRING", "description": "الوصف التفصيلي"},
                    "quantity": {"type": "NUMBER"},
                    "unit": {
                        "type": "STRING",
                        "description": "وحدة القياس: شهر/سنة/قطعة/ترخيص/مستخدم/نقطة/مشروع",
                    },
                    "notes": {"type": "STRING"},
                },
                "required": ["item", "quantity", "unit"],
            },
        }
    },
    "required": ["items"],
}

OUTLINE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "sections": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "title": {"type": "STRING", "description": "عنوان القسم في العرض الفني"},
                    "rationale": {
                        "type": "STRING",
                        "description": "لماذا يلزم هذا القسم لهذه المنافسة تحديداً",
                    },
                    "priority": {"type": "STRING", "enum": ["عالية", "متوسطة", "منخفضة"]},
                    "guidance": {
                        "type": "STRING",
                        "description": "ما الذي ينبغي أن يغطيه هذا القسم في هذه المنافسة",
                    },
                },
                "required": ["title", "rationale", "priority", "guidance"],
            },
        }
    },
    "required": ["sections"],
}

REVIEW_SCHEMA = {
    "type": "OBJECT",
    "properties": {
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
    "required": ["findings"],
}


# ─── قوالب التعليمات المتخصصة ─────────────────────────────────────────────────

PROMPTS = {
    "gonogo": """أنت خبير في إدارة العطاءات الحكومية السعودية. حلّل كراسة الشروط التالية وأعطِ قرار Go/No-Go.

الهيكل المطلوب:
## قرار الملاءمة: [GO ✅ / NO-GO ❌]

### ✅ نقاط القوة (Opportunities)
- (قائمة مختصرة)

### ⚠️ المخاطر الرئيسية (Risks)
- (قائمة مختصرة مع مستوى الخطورة: عالي/متوسط/منخفض)

### 📋 الشروط الحاكمة الحرجة
- (المتطلبات الإلزامية فقط)

### 💡 التوصية النهائية
(فقرة مختصرة)

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

    "section": """أنت مهندس حلول متخصص في إعداد العروض الفنية للمنافسات الحكومية السعودية.
اكتب قسم **"{title}"** من العرض الفني.

ما ينبغي أن يغطيه هذا القسم:
{guidance}

بيانات الشركة: {company_overview}
معايير التقييم والأوزان المعتمدة: {eval_weights}
الشروط الحاكمة المعتمدة: {compliance_summary}

قواعد الكتابة:
- اكتبه بصيغة عرض مقدَّم للجهة، بلغة مهنية مباشرة.
- استند إلى كراسة الشروط المرفقة، ولا تخترع أرقاماً أو مراجع مشاريع أو أسماء عملاء.
- إن لزمت معلومة لا تملكها، ضعها بين أقواس مربعة [ ] ليعبّئها الفريق لاحقاً.
- ابدأ بعنوان القسم كترويسة من المستوى الثاني (##) ثم قسّمه لعناوين فرعية.

{language_instruction}""",

    "apply_finding": """أنت محرّر عروض فنية. أعد كتابة القسم التالي من العرض الفني
بحيث تعالج الملاحظة المرصودة، مع الإبقاء على كل المحتوى السليم كما هو.

عنوان القسم: {title}

الملاحظة ({lens} — خطورة {severity}):
{issue}

أثرها: {impact}
الصياغة المقترحة من المراجع: {suggestion}

قواعد صارمة:
- أعد **القسم كاملاً** بعد التعديل، لا المقطع المعدَّل وحده.
- لا تحذف معلومات صحيحة موجودة أصلاً، ولا تغيّر بنية العناوين الفرعية بلا داعٍ.
- لا تخترع أرقاماً أو أسماء عملاء أو مراجع مشاريع. إن لزمت معلومة لا تملكها
  فضعها بين أقواس مربعة [ ] ليعبّئها الفريق.
- أعد النص فقط بلا مقدمات ولا شرح لما غيّرته.

{language_instruction}

نص القسم الحالي:
{content}""",

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
    "compliance_items": """أنت مستشار امتثال في العطاءات الحكومية السعودية.
استخرج من كراسة الشروط المرفقة **كل** متطلب يجب على مقدّم العرض إثبات التزامه به.

قواعد:
- بنداً واحداً لكل متطلب، بصياغة الكراسة نفسها قدر الإمكان لا بإعادة صياغة عامة.
- صنّف كل متطلب: "تأهيل" (شرط استبعاد)، "فني"، "إداري"، "مالي".
- ضع mandatory = true فقط لما يؤدي عدم استيفائه للاستبعاد.
- إن ذُكرت شهادة أو وثيقة لإثبات المتطلب فاذكرها في certificate، وإلا اتركه فارغاً.
- لا تخترع متطلبات غير واردة في النص.""",

    "boq_items": """أنت محلل تكاليف عطاءات.
استخرج من المستند المرفق بنود جدول الكميات (BOQ) — الأصناف والخدمات المطلوب تسعيرها.

قواعد:
- استخرج البنود كما وردت في جدول الكميات أو جدول الأسعار إن وُجد.
- إن لم يرد جدول كميات صريح، استنتج البنود القابلة للتسعير من نطاق العمل.
- quantity رقم. إن لم تُذكر كمية فاستخدم 1.
- unit من: شهر، سنة، قطعة، ترخيص، مستخدم، نقطة، مشروع.
- لا تضع أسعاراً — التسعير مسؤولية الفريق المالي.""",

    "outline": """أنت خبير في إعداد العروض الفنية للمنافسات الحكومية السعودية.
اقترح هيكل العرض الفني المناسب **لهذه المنافسة تحديداً** بناءً على كراسة الشروط المرفقة.

قواعد:
- رتّب الأقسام بالترتيب الذي ستظهر به في المستند النهائي.
- اشتقّ الأقسام من معايير التقييم ومتطلبات الكراسة، لا من قائمة عامة محفوظة.
- إن نصّت الكراسة على أقسام أو ترتيب معيّن للعرض الفني فالتزم به حرفياً.
- priority = "عالية" للأقسام ذات الوزن الأكبر في التقييم.
- guidance: ما الذي يجب أن يغطيه القسم في هذه المنافسة بالذات.
- بين 6 و 12 قسماً.""",
}


# ─── مراجعة ما قبل التسليم: ثلاث زوايا ────────────────────────────────────────

REVIEW_LENSES = {
    "technical": {
        "label": "فنية",
        "icon": "🛠️",
        "prompt": """أنت مراجع فني مستقل لعرض فني مقدَّم لمنافسة حكومية سعودية.
راجع العرض المرفق من الزاوية الفنية فقط.

ابحث عن:
- متطلبات فنية في الكراسة لم يغطها العرض إطلاقاً (أخطر نوع من الملاحظات).
- ادعاءات عامة بلا إثبات أو تفصيل ("خبرة واسعة"، "أحدث التقنيات") تُفقد درجات التقييم.
- تناقضات بين أقسام العرض.
- نص نائب لم يُعبَّأ بين أقواس [ ].
- منهجية غير قابلة للتنفيذ أو لا تتناسب مع الجدول الزمني المطروح.

لكل ملاحظة، إن أمكن اقتراح نص بديل جاهز فضعه في suggested_text.
اترك suggested_text فارغاً إذا كانت المعالجة تتطلب معلومة لا تملكها (رقم، اسم، مرجع مشروع سابق).""",
    },
    "commercial": {
        "label": "تجارية",
        "icon": "💰",
        "prompt": """أنت مراجع تجاري لعرض فني مقدَّم لمنافسة حكومية سعودية.
راجع العرض المرفق من الزاوية التجارية والتنافسية فقط.

ابحث عن:
- ضعف ربط العرض بمعايير التقييم وأوزانها — أين تُهدر درجات؟
- غياب عناصر التمايز عن المنافسين.
- التزامات مفتوحة أو غير محدّدة قد تُكلّف الشركة لاحقاً (نطاق غير مسوّر، ضمانات مطلقة).
- اختلال بين ما وُعد به فنياً وما يمكن تنفيذه ضمن نطاق العقد.
- فرص لتعزيز القيمة المضافة المذكورة بلا كلفة إضافية.

ضع نصاً بديلاً في suggested_text حيثما أمكن.""",
    },
    "legal": {
        "label": "قانونية",
        "icon": "⚖️",
        "prompt": """أنت مستشار قانوني يراجع عرضاً فنياً مقدَّماً لمنافسة حكومية سعودية.
راجع العرض المرفق من الزاوية القانونية والامتثالية فقط.

ابحث عن:
- مخالفة أو تعارض مع الشروط الحاكمة في كراسة الشروط.
- تحفّظات أو استثناءات مكتوبة في العرض قد تُعدّ تحفظاً جوهرياً يستوجب الاستبعاد.
- التزامات قانونية مطلقة أو غير مسوّرة (تعويض غير محدود، ضمانات مطلقة).
- متطلبات نظامية مطلوبة ولم يُشَر إليها (سعودة، محتوى محلي، حماية البيانات، ملكية فكرية).
- تعارض بين نصوص العرض ونصوص العقد المرفق بالكراسة.

ضع نصاً بديلاً في suggested_text حيثما أمكن.""",
    },
}
