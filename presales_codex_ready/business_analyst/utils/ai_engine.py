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


def outline_prompt(language: str = DEFAULT_LANGUAGE) -> str:
    """تعليمات اقتراح الهيكل مع الأقسام الإلزامية وتعليمة اللغة."""
    return (
        EXTRACT_PROMPTS["outline"].format(
            mandatory_sections="\n".join(
                f"   - {name}" for name in MANDATORY_OUTLINE_SECTIONS
            )
        )
        + f"\n{language_instruction(language)}"
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
