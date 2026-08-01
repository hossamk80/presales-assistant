"""
utils/state.py — Centralized Session State Management
Prevents re-initialization bugs and provides typed defaults.
"""
import os

import pandas as pd
import streamlit as st

from utils.ai_engine import DEFAULT_LANGUAGE, DEFAULT_MODEL
from utils.i18n import DEFAULT_UI_LANGUAGE


def _env_api_key() -> str:
    """
    مفتاح Gemini من متغيّرات البيئة (Replit Secrets أو بيئة الاستضافة).

    يبقى الإدخال اليدوي من صفحة الإعدادات متاحاً ويَجُبّ هذه القيمة، فالتشغيل
    المحلي لا يحتاج متغيّر بيئة أصلاً.
    """
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""

# ─── جدول الامتثال ─────────────────────────────────────────────────────────────
# الأعمدة تتبع مخطط مصفوفة الامتثال الموحّد. عمود "الالتزام" إضافة خاصة بنا:
# قرار بشري لا يفترضه النموذج، ويبقى إلى جانب استراتيجية الاستجابة المقترحة.
COMPLIANCE_COLUMNS = [
    "المعرّف",
    "التصنيف",
    "مرجع البند",
    "المتطلب",
    "الأهمية",
    "استراتيجية الاستجابة",
    "الالتزام",
    "الشهادة المطلوبة",
    # تتبّع التغطية: أين عولج هذا المتطلب فعلاً في نص العرض.
    "التغطية",
    "القسم المغطّي",
]

# حالات التغطية. القيمة الافتراضية "غير مفحوص" لا "غير مغطّى": الفرق بين
# "فحصنا فلم نجد" و"لم نفحص بعد" فرق جوهري عند قرار التسليم.
COVERAGE_UNCHECKED = "غير مفحوص"
COVERAGE_COVERED = "مغطّى"
COVERAGE_PARTIAL = "جزئي"
COVERAGE_MISSING = "غير مغطّى"
COVERAGE_OPTIONS = [
    COVERAGE_UNCHECKED, COVERAGE_COVERED, COVERAGE_PARTIAL, COVERAGE_MISSING,
]

LEGACY_COMPLIANCE_COLUMNS = [
    "المتطلب التقني", "الالتزام", "التبرير / الملاحظة", "الشهادة المطلوبة",
]

COMPLIANCE_STATUS_OPTIONS = ["نعم", "جزئي", "لا", "بانتظار التحقق"]
CRITICALITY_OPTIONS = ["High", "Medium", "Low"]
COMPLIANCE_CATEGORY_OPTIONS = ["Technical", "Operational", "Administrative", "Legal"]

DEFAULT_COMPLIANCE_DF = pd.DataFrame({
    "المعرّف": [""],
    "التصنيف": [""],
    "مرجع البند": [""],
    "المتطلب": [""],
    "الأهمية": [""],
    "استراتيجية الاستجابة": [""],
    "الالتزام": ["بانتظار التحقق"],
    "الشهادة المطلوبة": [""],
    "التغطية": [COVERAGE_UNCHECKED],
    "القسم المغطّي": [""],
})


def migrate_compliance_df(df: "pd.DataFrame") -> "pd.DataFrame":
    """
    يرقّي جدول امتثال محفوظاً بالشكل القديم إلى مخطط المصفوفة الموسّع.

    الشكل القديم أربعة أعمدة. بدون الترقية يفشل محرر البيانات على أعمدة لا
    يجدها وتضيع صفوف المستخدم.
    """
    if df is None or not isinstance(df, pd.DataFrame):
        return DEFAULT_COMPLIANCE_DF.copy()
    if list(df.columns) == COMPLIANCE_COLUMNS:
        return df

    out = df.copy()
    # "المتطلب التقني" القديم صار "المتطلب"، و"التبرير" صار استراتيجية الاستجابة
    renames = {
        "المتطلب التقني": "المتطلب",
        "التبرير / الملاحظة": "استراتيجية الاستجابة",
    }
    for old, new in renames.items():
        if old in out.columns and new not in out.columns:
            out = out.rename(columns={old: new})

    # أعمدة القوائم المنسدلة تحتاج قيمة صالحة وإلا عرضها المحرر "None".
    # هذه قيم محايدة لصفوف مُرقّاة، لا تقييم — الجدول يُراجَع يدوياً بأي حال.
    defaults = {
        "الالتزام": "بانتظار التحقق",
        "التصنيف": "Technical",
        "الأهمية": "Medium",
        "التغطية": COVERAGE_UNCHECKED,
    }
    for col in COMPLIANCE_COLUMNS:
        if col not in out.columns:
            out[col] = defaults.get(col, "")
        elif col in defaults:
            out[col] = out[col].replace("", defaults[col]).fillna(defaults[col])

    return out[COMPLIANCE_COLUMNS]

# ─── مستندات التسليم ───────────────────────────────────────────────────────────
# أكثر أسباب الاستبعاد شيوعاً ليست ضعف العرض الفني بل مستند ناقص في المظروف.
SUBMISSION_COLUMNS = [
    "المستند",
    "مرجع البند",
    "إلزامي",
    "لدينا",
    "تاريخ الانتهاء",
    "مرفق في المظروف",
    "ملاحظات",
]

# "لدينا" و"مرفق" قراران بشريان: النموذج يقرأ الكراسة لا خزانة مستنداتك.
SUBMISSION_HAVE_OPTIONS = ["بانتظار التحقق", "نعم", "لا", "لا ينطبق"]

DEFAULT_SUBMISSION_DF = pd.DataFrame({
    "المستند": [""],
    "مرجع البند": [""],
    "إلزامي": [True],
    "لدينا": ["بانتظار التحقق"],
    "تاريخ الانتهاء": [""],
    "مرفق في المظروف": [False],
    "ملاحظات": [""],
})


def migrate_submission_df(df) -> "pd.DataFrame":
    """يضمن أن جدول المستندات يحمل كل الأعمدة مهما كان مصدره."""
    if df is None or not isinstance(df, pd.DataFrame):
        return DEFAULT_SUBMISSION_DF.copy()
    if list(df.columns) == SUBMISSION_COLUMNS:
        return df

    out = df.copy()
    defaults = {"إلزامي": True, "لدينا": "بانتظار التحقق", "مرفق في المظروف": False}
    for col in SUBMISSION_COLUMNS:
        if col not in out.columns:
            out[col] = defaults.get(col, "")
    return out[SUBMISSION_COLUMNS]


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
     "guidance": "المنهجية وأسلوب التنفيذ والحل التقني والمزايا التنافسية "
                 "واستراتيجية إدارة المخاطر والحد منها."},
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


def boq_scope_block(limit: int = 60) -> str:
    """
    نطاق العمل من جدول الكميات — بلا كميات ولا أي عمود قد يحمل قيمة مالية.

    مُهندس الهيكل يحتاج أن يعرف **ما الذي سيُنفَّذ** ليبني عليه الأقسام، وتمرير
    الكميات معه يفتح باب تسرّب أرقام إلى العرض الفني بلا فائدة تُذكر.
    """
    df = st.session_state.get("df_boq")
    if df is None or getattr(df, "empty", True):
        return ""

    wanted = [c for c in ("التصنيف", "البند", "الوصف", "المواصفات")
              if c in df.columns]
    if not wanted:
        return ""

    lines = []
    for row in df[wanted].head(limit).itertuples(index=False):
        parts = [str(v).strip() for v in row if str(v).strip() and str(v) != "nan"]
        if parts:
            lines.append("- " + " · ".join(parts))

    if not lines:
        return ""

    more = len(df) - limit
    tail = f"\n(و {more} بنداً آخر)" if more > 0 else ""
    return "\n\n--- نطاق العمل من جدول الكميات ---\n" + "\n".join(lines) + tail


def company_block() -> str:
    """
    ملف الشركة كنص جاهز للحقن في التعليمات.

    قرار الخوض من عدمه يقارن **متطلبات الكراسة بقدرات هذه الشركة** تحديداً؛
    بدون هذا المقطع يحكم النموذج على المنافسة في المطلق ويُخرج "GO" لعطاء لا
    تتأهل له الشركة أصلاً.
    """
    lines = []
    for label, key in (
        ("اسم الشركة", "c_name"),
        ("السجل التجاري", "c_cr"),
        ("العنوان", "c_address"),
        ("نبذة عن الشركة وخبراتها", "c_overview"),
    ):
        value = str(st.session_state.get(key, "")).strip()
        if value:
            lines.append(f"{label}: {value}")

    if not lines:
        return ""
    return "\n\n--- ملف الشركة المقدِّمة ---\n" + "\n".join(lines)


def project_context_block() -> str:
    """
    السياق الموحّد للمشروع (الجهة، الموعد، التسليمات، الغرامات، المحتوى المحلي).

    مشترك بين كاتب الأقسام ولجنة المراجعة: كلاهما يحتاج قيود المنافسة الفعلية
    بدل استنتاجها من نص الكراسة الخام في كل استدعاء.
    """
    ctx = st.session_state.get("project_context") or {}
    if not ctx:
        return ""

    lines = []
    for label, key in (
        ("المشروع", "project_title"),
        ("الجهة المصدِرة", "issuing_entity"),
        ("الموعد النهائي", "submission_deadline"),
        ("ملخص النطاق", "scope_summary"),
        ("متطلبات المحتوى المحلي", "local_content_requirements"),
    ):
        value = str(ctx.get(key, "")).strip()
        if value:
            lines.append(f"{label}: {value}")

    for label, key in (
        ("التسليمات الرئيسية", "key_deliverables"),
        ("القيود الفنية", "technical_constraints"),
        ("الغرامات التعاقدية", "contractual_penalties"),
        ("الشهادات المطلوبة", "required_certifications"),
    ):
        values = ctx.get(key) or []
        if values:
            lines.append(f"{label}: " + " · ".join(str(v) for v in values))

    if not lines:
        return ""
    return "\n\n--- سياق المشروع الموحّد ---\n" + "\n".join(lines)


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
    "ui_language": DEFAULT_UI_LANGUAGE,

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
    # الهوية البصرية للمستندات المصدَّرة (لون العناوين وخط النص).
    "c_brand_color": "",
    "c_doc_font": "",

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
    "outline_source": "default",
    "proposal_title": "",

    # Pre-submission Review
    "review_findings": [],
    "review_scores": {},
    "review_ran_at": "",

    # Tables
    "df_compliance": DEFAULT_COMPLIANCE_DF,
    "df_boq": DEFAULT_BOQ_DF,
    "df_submission": DEFAULT_SUBMISSION_DF,

    # UI State
    "ai_generating": False,
    "last_export_filename": "",
}


def get_sections() -> list:
    """هيكل العرض الحالي (نسخة قابلة للتعديل)."""
    sections = st.session_state.get("proposal_sections") or DEFAULT_SECTIONS
    return [dict(s) for s in sections]


def set_sections(sections: list, source: str = "custom"):
    st.session_state["proposal_sections"] = [dict(s) for s in sections]
    st.session_state["outline_source"] = source


def reset_sections():
    set_sections(DEFAULT_SECTIONS, source="default")


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
    st.session_state["df_submission"] = DEFAULT_SUBMISSION_DF.copy()
    st.session_state["review_findings"] = []
    st.session_state["review_scores"] = {}
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

    # مفاتيح ديناميكية خارج المخطط الثابت: أقسام أضافها النموذج (sec_ai_*)
    # وتوجيهات الكتابة لكل قسم (steer_*). بدونها يضيع التوجيه بتبديل المنافسة.
    snapshot["_dynamic_sections"] = {
        k: v for k, v in st.session_state.items()
        if k.startswith(("sec_ai_", "steer_")) and isinstance(v, str)
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
                    if key == "df_boq":
                        st.session_state[key] = migrate_boq_df(loaded)
                    elif key == "df_compliance":
                        st.session_state[key] = migrate_compliance_df(loaded)
                    elif key == "df_submission":
                        st.session_state[key] = migrate_submission_df(loaded)
                    else:
                        st.session_state[key] = loaded
                except Exception:
                    pass
        elif type(default) is type(val) or (isinstance(default, str) and isinstance(val, str)):
            st.session_state[key] = val

    for key, val in (data.get("_dynamic_sections") or {}).items():
        st.session_state[key] = val

    # مفاتيح المحرّرات تحمل نص الجلسة السابقة — نُبطلها ليعرض كلٌّ منها المحمَّل
    # مفاتيح المحرّرات تحمل نص الجلسة السابقة. توجيهات الكتابة (steer_*)
    # مستثناة لأنها حُمِّلت للتوّ من اللقطة أعلاه.
    for key in [k for k in list(st.session_state) if k.startswith(("ta_", "de_", "inc_"))]:
        del st.session_state[key]


# ─── ربط الحالة بالتخزين الدائم ────────────────────────────────────────────────

# مفاتيح ملف الشركة تُحفظ مستقلة عن المنافسة لأنها ثابتة عبر كل العطاءات
COMPANY_KEYS = [
    "c_name", "c_cr", "c_vat", "c_phone", "c_email", "c_web",
    "c_address", "c_overview", "c_cover_template",
    "c_brand_color", "c_doc_font",
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
