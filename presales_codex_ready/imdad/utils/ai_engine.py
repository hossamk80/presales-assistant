"""
utils/ai_engine.py — Multi-Provider AI Engine
Supports Gemini, with clean abstraction for future OpenAI/Claude support.
"""
import streamlit as st
from typing import Optional


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return max(0, len(str(text)) // 4)


def _call_gemini(prompt: str, model_name: str) -> Optional[str]:
    try:
        import google.generativeai as genai
        genai.configure(api_key=st.session_state["api_gemini"])
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return response.text
    except ImportError:
        st.error("❌ مكتبة google-generativeai غير مثبّتة. شغّل: pip install google-generativeai")
        return None
    except Exception as e:
        st.error(f"❌ خطأ Gemini API: {e}")
        return None


def ai_generate(
    prompt: str,
    model_choice: str = "Gemini 1.5 Flash",
    rfp_context: str = "",
    max_context_chars: int = 20000,
) -> Optional[str]:
    """
    Generate AI content. Automatically truncates RFP context to avoid token limits.
    
    Args:
        prompt: The instruction/task
        model_choice: Display name of the model
        rfp_context: Optional RFP text to inject as context
        max_context_chars: Max chars from RFP to include
    
    Returns:
        Generated text or None on failure
    """
    # Validate API key exists
    if "gemini" in model_choice.lower() or not model_choice:
        if not st.session_state.get("api_gemini"):
            st.error("⚠️ يرجى إدخال مفتاح Google Gemini API في **إعدادات النظام** أولاً.")
            return None
        
        # Inject truncated RFP context if provided
        if rfp_context:
            truncated = rfp_context[:max_context_chars]
            if len(rfp_context) > max_context_chars:
                truncated += "\n\n[... تم اختصار النص للحفاظ على حدود التوكنز ...]"
            full_prompt = f"{prompt}\n\n---\nنص الكراسة:\n{truncated}"
        else:
            full_prompt = prompt

        gemini_model = "gemini-1.5-pro" if "Pro" in model_choice else "gemini-1.5-flash"
        return _call_gemini(full_prompt, gemini_model)

    # Placeholder for future providers
    elif "openai" in model_choice.lower():
        st.info("🔜 دعم OpenAI قريباً.")
        return None
    elif "claude" in model_choice.lower():
        st.info("🔜 دعم Claude قريباً.")
        return None
    else:
        st.error(f"❌ نموذج غير معروف: {model_choice}")
        return None


# ─── Specialized Prompt Templates ─────────────────────────────────────────────

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
