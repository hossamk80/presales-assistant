"""
utils/ai_engine.py — محرك الذكاء الاصطناعي (Google Gen AI SDK الموحّد)

يعتمد على حزمة `google-genai` — الحزمة القديمة `google-generativeai` مهجورة.
"""
import streamlit as st
from typing import Callable, Optional

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

أعطِ التحليل المدموج النهائي فقط، بنفس الهيكل، وباللغة العربية."""


def ai_generate(
    prompt: str,
    model_choice: str = DEFAULT_MODEL,
    rfp_context: str = "",
    on_progress: Optional[Callable[[str], None]] = None,
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
            original_prompt=prompt, partials="\n\n".join(partials)
        ),
        model_id,
    )


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

الرد باللغة العربية فقط.""",

    "eval_matrix": """أنت محلل عطاءات. استخرج من الكراسة التالية مصفوفة معايير التقييم والأوزان.

الهيكل المطلوب:
## مصفوفة التقييم

| المعيار | الوزن % | المتطلبات الرئيسية | أولوية التركيز |
|---------|---------|-------------------|----------------|

### 📌 ملاحظات استراتيجية
- (توصيات لتعظيم الدرجة في كل معيار)

الرد باللغة العربية فقط.""",

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

الرد باللغة العربية فقط.""",

    "scope": """أنت مهندس حلول. اكتب قسم "فهمنا للنطاق والمتطلبات" في عرض فني، مستنداً إلى كراسة الشروط المرفقة.

الهيكل المطلوب:
## فهم النطاق والمتطلبات

### 1. الهدف من المشروع كما تفهمه الجهة
### 2. نطاق الأعمال والتسليمات المطلوبة
### 3. المتطلبات الوظيفية وغير الوظيفية الرئيسية
### 4. الافتراضات والحدود (ما يقع خارج النطاق)
### 5. عوامل النجاح الحرجة

اكتبه بصيغة عرض مقدَّم للجهة (نحن نفهم أن...) لا بصيغة تقرير داخلي.
الرد باللغة العربية فقط.""",

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

الرد باللغة العربية فقط.""",

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

الرد باللغة العربية فقط.""",
}
