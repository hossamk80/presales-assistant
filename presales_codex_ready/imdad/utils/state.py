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

    # Tables
    "df_compliance": DEFAULT_COMPLIANCE_DF,
    "df_boq": DEFAULT_BOQ_DF,

    # UI State
    "ai_generating": False,
    "last_export_filename": "",
}


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
    st.session_state["df_compliance"] = DEFAULT_COMPLIANCE_DF.copy()
    st.session_state["df_boq"] = DEFAULT_BOQ_DF.copy()


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
