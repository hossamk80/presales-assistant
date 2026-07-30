"""
utils/state.py — Centralized Session State Management
Prevents re-initialization bugs and provides typed defaults.
"""
import pandas as pd
import streamlit as st

from utils.ai_engine import DEFAULT_MODEL

# ─── Default DataFrames ────────────────────────────────────────────────────────
DEFAULT_COMPLIANCE_DF = pd.DataFrame({
    "المتطلب التقني": [""],
    "الالتزام": ["نعم"],
    "التبرير / الملاحظة": [""],
    "الشهادة المطلوبة": [""]
})

DEFAULT_BOQ_DF = pd.DataFrame({
    "البند": [""],
    "الوصف": [""],
    "الكمية": [1],
    "الوحدة": [""],
    "ملاحظات": [""]
})

# ─── هيكل العرض الفني ──────────────────────────────────────────────────────────
# كل قسم: key فريد · title العنوان · include هل يُدرج · kind نوع المحتوى
#   kind = "cover" خطاب التقديم · "docinfo" إشعار السرية
#        · "ai" نص يولّده الذكاء الاصطناعي
#        · "table_compliance" / "table_boq" جدول يُحقن من التبويب الثاني
# prompt_key اختياري: يستخدم قالب تعليمات متخصص بدل القالب العام.
# guidance: ما ينبغي أن يغطيه القسم — يُمرَّر للنموذج عند التوليد.
DEFAULT_SECTIONS = [
    {"key": "cover", "title": "خطاب التقديم", "kind": "cover", "include": True,
     "guidance": "خطاب رسمي موجز لتقديم العرض للجهة."},
    {"key": "docinfo", "title": "معلومات المستند وإشعار السرية", "kind": "docinfo", "include": True,
     "guidance": "إشعار سرية ومعلومات المستند."},
    {"key": "exec", "title": "الملخص التنفيذي", "kind": "ai", "include": False,
     "guidance": "ملخص تنفيذي يبرز فهم المشروع والحل المقترح وأبرز مزايا الشركة."},
    {"key": "scope", "title": "فهم النطاق والمتطلبات", "kind": "ai", "include": False,
     "prompt_key": "scope",
     "guidance": "إثبات فهم دقيق لنطاق العمل والتسليمات والافتراضات."},
    {"key": "methodology", "title": "المنهجية الفنية والحل المقترح", "kind": "ai", "include": True,
     "prompt_key": "methodology",
     "guidance": "المنهجية وأسلوب التنفيذ والحل التقني والمزايا التنافسية وضمان الجودة."},
    {"key": "gov", "title": "حوكمة المشروع ومستويات الخدمة (SLAs)", "kind": "ai", "include": False,
     "guidance": "هيكل الإشراف وآليات التصعيد ومستويات الخدمة ومؤشرات الأداء."},
    {"key": "plan", "title": "خطة المشروع والجدول الزمني", "kind": "ai", "include": True,
     "prompt_key": "project_plan",
     "guidance": "المراحل والجدول الزمني والموارد والتسليمات وإدارة المخاطر."},
    {"key": "team", "title": "هيكلة الفريق والسير الذاتية", "kind": "ai", "include": False,
     "guidance": "الهيكل التنظيمي للفريق والأدوار والخبرات المطلوبة."},
    {"key": "external", "title": "المتطلبات الخارجية والضمانات", "kind": "ai", "include": False,
     "guidance": "الضمانات والتأمينات والمتطلبات التي تقع على الجهة."},
    {"key": "compliance_table", "title": "جدول الامتثال بالمواصفات", "kind": "table_compliance", "include": True,
     "guidance": ""},
    {"key": "boq_table", "title": "جدول الكميات (BOQ)", "kind": "table_boq", "include": False,
     "guidance": ""},
]


def section_content_key(key: str) -> str:
    """مفتاح تخزين محتوى القسم في session_state."""
    return f"sec_{key}"

# ─── Schema: (key, default_value) ─────────────────────────────────────────────
STATE_SCHEMA = {
    # Navigation
    "nav_selection": "dashboard",

    # API Keys
    "api_gemini": "",
    "api_openai": "",
    "api_claude": "",
    "ai_model_preference": DEFAULT_MODEL,

    # Company Profile
    "c_name": "",
    "c_cr": "",
    "c_vat": "",
    "c_phone": "",
    "c_email": "",
    "c_web": "",
    "c_address": "",
    "c_overview": "",
    "c_cover_template": "نفيدكم نحن [اسم الشركة] برغبتنا في تقديم هذا العرض الفني لتنفيذ مشروعكم الموقر...",
    "c_word_template_bytes": None,

    # RFP Analysis
    "rfp_raw_text": "",
    "rfp_file_names": [],
    "analysis_gonogo": "",
    "sum_gonogo": "",
    "evaluation_matrix": "",
    "sum_eval": "",
    "compliance_check": "",
    "sum_comp": "",
    "risk_register": "",

    # Document Sections
    "sec_cover": "",
    "sec_exec": "",
    "sec_scope": "",
    "sec_methodology": "",
    "sec_gov": "",
    "sec_plan": "",
    "sec_team": "",
    "sec_external": "",
    "sec_cover_use_template": True,

    # Proposal Outline
    "proposal_sections": DEFAULT_SECTIONS,
    "outline_source": "افتراضي",

    # Pre-submission Review
    "review_findings": [],
    "review_ran_at": "",

    # Tables
    "df_compliance": DEFAULT_COMPLIANCE_DF,
    "df_boq": DEFAULT_BOQ_DF,

    # UI State
    "ai_generating": False,
    "last_export_filename": "",
}


def get_sections() -> list:
    """هيكل العرض الحالي (نسخة قابلة للتعديل)."""
    sections = st.session_state.get("proposal_sections") or DEFAULT_SECTIONS
    return [dict(s) for s in sections]


def set_sections(sections: list, source: str = "مخصص"):
    st.session_state["proposal_sections"] = [dict(s) for s in sections]
    st.session_state["outline_source"] = source


def reset_sections():
    set_sections(DEFAULT_SECTIONS, source="افتراضي")


def init_state():
    """Initialize all session state keys with defaults (idempotent)."""
    for key, default in STATE_SCHEMA.items():
        if key not in st.session_state:
            st.session_state[key] = default


def reset_analysis():
    """Clear analysis results while keeping company profile and API keys."""
    analysis_keys = [
        "rfp_raw_text", "rfp_file_names", "analysis_gonogo", "sum_gonogo",
        "evaluation_matrix", "sum_eval", "compliance_check", "sum_comp",
        "risk_register", "sec_cover", "sec_exec", "sec_scope",
        "sec_methodology", "sec_gov", "sec_plan", "sec_team", "sec_external",
    ]
    for key in analysis_keys:
        st.session_state[key] = STATE_SCHEMA[key]

    # أقسام أضافها الذكاء الاصطناعي ديناميكياً (sec_ai_*) ليست في المخطط الثابت
    for key in [k for k in st.session_state if k.startswith("sec_ai_")]:
        del st.session_state[key]

    st.session_state["df_compliance"] = DEFAULT_COMPLIANCE_DF.copy()
    st.session_state["df_boq"] = DEFAULT_BOQ_DF.copy()
    st.session_state["review_findings"] = []
    st.session_state["review_ran_at"] = ""
    reset_sections()


def get_state_snapshot() -> dict:
    """Export serializable state (excludes bytes and DataFrames)."""
    snapshot = {}
    for key in STATE_SCHEMA:
        val = st.session_state.get(key)
        if isinstance(val, str):
            snapshot[key] = val
        elif isinstance(val, list):
            snapshot[key] = val
        elif isinstance(val, bool):
            snapshot[key] = val
        elif isinstance(val, pd.DataFrame):
            snapshot[key] = val.to_dict(orient="records")
    return snapshot


def load_state_snapshot(data: dict):
    """Import state from a saved snapshot."""
    for key, val in data.items():
        if key not in STATE_SCHEMA:
            continue
        default = STATE_SCHEMA[key]
        if isinstance(default, pd.DataFrame) and isinstance(val, list):
            try:
                st.session_state[key] = pd.DataFrame(val)
            except Exception:
                pass
        elif type(default) == type(val) or (isinstance(default, str) and isinstance(val, str)):
            st.session_state[key] = val
