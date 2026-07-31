"""
utils/state.py — Centralized Session State Management
Prevents re-initialization bugs and provides typed defaults.
"""
import os

import pandas as pd
import streamlit as st

from utils.ai_engine import DEFAULT_LANGUAGE, DEFAULT_MODEL


def _env_api_key() -> str:
    """
    مفتاح Gemini من متغيّرات البيئة (Replit Secrets أو بيئة الاستضافة).

    يبقى الإدخال اليدوي من صفحة الإعدادات متاحاً ويَجُبّ هذه القيمة، فالتشغيل
    المحلي لا يحتاج متغيّر بيئة أصلاً.
    """
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""

# ─── Default DataFrames ────────────────────────────────────────────────────────
DEFAULT_COMPLIANCE_DF = pd.DataFrame({
    "المتطلب التقني": [""],
    "الالتزام": ["نعم"],
    "التبرير / الملاحظة": [""],
    "الشهادة المطلوبة": [""]
})

# ─── جدول الكميات ──────────────────────────────────────────────────────────────
# الأعمدة تتبع مخطط الاستخراج الموحّد (9 حقول) لا الشكل المختصر السابق.
BOQ_COLUMNS = [
    "رقم البند",
    "التصنيف",
    "البند",
    "الوحدة",
    "الوصف",
    "المواصفات",
    "كود البناء",
    "الكمية",
    "القائمة الإلزامية",
]

# أعمدة الشكل القديم — تُستخدم للكشف عن جداول محفوظة قبل توسيع المخطط
LEGACY_BOQ_COLUMNS = ["البند", "الوصف", "الكمية", "الوحدة", "ملاحظات"]

DEFAULT_BOQ_DF = pd.DataFrame({
    "رقم البند": [""],
    "التصنيف": [""],
    "البند": [""],
    "الوحدة": [""],
    "الوصف": [""],
    "المواصفات": [""],
    "كود البناء": [""],
    "الكمية": [1],
    "القائمة الإلزامية": [False],
})


def migrate_boq_df(df: "pd.DataFrame") -> "pd.DataFrame":
    """
    يرقّي جدول كميات محفوظاً بالشكل القديم إلى المخطط الموسّع.

    المنافسات المحفوظة قبل هذا التوسيع تحمل خمسة أعمدة فقط. بدون الترقية
    يُعرَض الجدول بأعمدة مفقودة ويفشل محرر البيانات على أعمدة لا يجدها.
    """
    if df is None or not isinstance(df, pd.DataFrame):
        return DEFAULT_BOQ_DF.copy()
    if list(df.columns) == BOQ_COLUMNS:
        return df

    out = df.copy()
    # "ملاحظات" القديمة أقرب معنى إلى "المواصفات" في المخطط الجديد
    if "ملاحظات" in out.columns and "المواصفات" not in out.columns:
        out = out.rename(columns={"ملاحظات": "المواصفات"})

    for col in BOQ_COLUMNS:
        if col not in out.columns:
            if col == "الكمية":
                out[col] = 1
            elif col == "القائمة الإلزامية":
                out[col] = False
            else:
                out[col] = ""

    return out[BOQ_COLUMNS]

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


# ─── أدوار المرفقات ────────────────────────────────────────────────────────────
# تُحلَّل كل مرفقات المنافسة معاً، لكن بعض التعليمات تحتاج تمييز الكراسة عن
# ملاحقها عن ملفات الكميات، فنحفظ نص كل دور على حدة إلى جانب النص المدموج.
ATTACHMENT_ROLES = {
    "rfp": "كراسة الشروط",
    "annex": "ملحق فني / مواصفات",
    "boq": "جدول الكميات",
    "other": "مرفق آخر",
}
DEFAULT_ROLE = "rfp"

# دلائل اسم الملف لترجيح الدور تلقائياً (يبقى قابلاً للتعديل يدوياً)
_ROLE_HINTS = {
    "boq": ["boq", "كميات", "الكميات", "bill of quant", "جدول الكمي", "أسعار", "اسعار", "pricing"],
    "annex": ["annex", "ملحق", "الملحق", "مواصفات", "specification", "spec", "sow", "نطاق"],
    "rfp": ["rfp", "كراسة", "الكراسة", "شروط", "tender", "منافسة", "itt"],
}


def guess_attachment_role(file_name: str) -> str:
    """يرجّح دور المرفق من اسمه وامتداده."""
    name = (file_name or "").lower()
    ext = name.rsplit(".", 1)[-1] if "." in name else ""

    for role, hints in _ROLE_HINTS.items():
        if any(h in name for h in hints):
            return role

    # جداول البيانات في كراسات اعتماد شبه دائماً جداول كميات
    if ext in ("xlsx", "xls", "csv"):
        return "boq"
    return DEFAULT_ROLE


def role_text(role: str) -> str:
    """النص المدموج لكل المرفقات المصنّفة بهذا الدور."""
    texts = st.session_state.get("attachment_texts") or {}
    roles = st.session_state.get("attachment_roles") or {}
    parts = [texts[name] for name, r in roles.items() if r == role and name in texts]
    return "\n\n".join(parts).strip()

# ─── Schema: (key, default_value) ─────────────────────────────────────────────
STATE_SCHEMA = {
    # Navigation
    "nav_selection": "dashboard",

    # API Keys
    "api_gemini": _env_api_key(),
    "api_openai": "",
    "api_claude": "",
    "ai_model_preference": DEFAULT_MODEL,
    "output_language": DEFAULT_LANGUAGE,

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
    # rfp_raw_text يظل النص المدموج لكل المرفقات (يستهلكه كل التحليل).
    # النصوص المفصولة حسب الدور تُستخدم حين تحتاج التعليمات تمييز
    # الكراسة عن ملاحقها عن ملفات الكميات.
    "rfp_raw_text": "",
    "attachment_texts": {},
    "attachment_roles": {},
    "rfp_file_names": [],
    "project_context": {},
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
        "rfp_raw_text", "attachment_texts", "attachment_roles", "project_context",
        "rfp_file_names", "analysis_gonogo", "sum_gonogo",
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
        if isinstance(val, (str, list, dict, bool, int, float)):
            snapshot[key] = val
        elif isinstance(val, pd.DataFrame):
            snapshot[key] = val.to_dict(orient="records")

    # أقسام أضافها الذكاء الاصطناعي ديناميكياً ليست ضمن المخطط الثابت
    snapshot["_dynamic_sections"] = {
        k: v for k, v in st.session_state.items()
        if k.startswith("sec_ai_") and isinstance(v, str)
    }
    return snapshot


def load_state_snapshot(data: dict):
    """Import state from a saved snapshot."""
    for key, val in data.items():
        if key == "_dynamic_sections":
            continue
        if key not in STATE_SCHEMA:
            continue
        default = STATE_SCHEMA[key]
        if isinstance(default, pd.DataFrame):
            if isinstance(val, list):
                try:
                    loaded = pd.DataFrame(val)
                    # منافسات محفوظة قبل توسيع مخطط الكميات تحمل الأعمدة القديمة
                    st.session_state[key] = (
                        migrate_boq_df(loaded) if key == "df_boq" else loaded
                    )
                except Exception:
                    pass
        elif type(default) is type(val) or (isinstance(default, str) and isinstance(val, str)):
            st.session_state[key] = val

    for key, val in (data.get("_dynamic_sections") or {}).items():
        st.session_state[key] = val

    # مفاتيح المحرّرات تحمل نص الجلسة السابقة — نُبطلها ليعرض كلٌّ منها المحمَّل
    for key in [k for k in list(st.session_state) if k.startswith(("ta_", "de_", "inc_"))]:
        del st.session_state[key]


# ─── ربط الحالة بالتخزين الدائم ────────────────────────────────────────────────

# مفاتيح ملف الشركة تُحفظ مستقلة عن المنافسة لأنها ثابتة عبر كل العطاءات
COMPANY_KEYS = [
    "c_name", "c_cr", "c_vat", "c_phone", "c_email", "c_web",
    "c_address", "c_overview", "c_cover_template",
]


def get_company_snapshot() -> dict:
    return {k: st.session_state.get(k, "") for k in COMPANY_KEYS}


def load_company_snapshot(data: dict):
    for key in COMPANY_KEYS:
        if key in data and isinstance(data[key], str):
            st.session_state[key] = data[key]


def get_project_snapshot() -> dict:
    """حالة المنافسة وحدها — بلا ملف الشركة وبلا مفاتيح الـ API."""
    snapshot = get_state_snapshot()
    for key in COMPANY_KEYS:
        snapshot.pop(key, None)
    for key in list(snapshot):
        if key.startswith("api_"):
            snapshot.pop(key)
    return snapshot
