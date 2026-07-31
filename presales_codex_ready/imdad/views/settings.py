"""
pages/settings.py — System Settings: API Keys + Data Management
"""
import json
import os

import streamlit as st

from utils.i18n import DEFAULT_UI_LANGUAGE, UI_LANGUAGES, t
from utils.state import get_state_snapshot, load_state_snapshot
from utils.ai_engine import (
    DEFAULT_LANGUAGE,
    DEFAULT_MODEL,
    LANGUAGES,
    MODEL_NAMES,
    resolve_model,
)


def render_settings():
    st.markdown(t("st.title"))

    with st.expander(t("st.keys"), expanded=True):
        st.markdown(
            f"""<div style="background:#FEF3C7;padding:12px 16px;border-radius:8px;
                        margin-bottom:12px;font-family:Tajawal,sans-serif;font-size:14px;
                        color:#92400E;">{t("st.key_warning")}</div>""",
            unsafe_allow_html=True,
        )

        if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            st.info(t("st.key_from_env"))

        st.session_state["api_gemini"] = st.text_input(
            "🔑 Google Gemini API Key",
            value=st.session_state.get("api_gemini", ""),
            type="password",
            placeholder="AIza...",
            help="احصل على مفتاحك من: https://aistudio.google.com/app/apikey",
        )

        c1, c2 = st.columns(2)
        with c1:
            st.session_state["api_openai"] = st.text_input(
                "🔑 OpenAI API Key",
                value=st.session_state.get("api_openai", ""),
                type="password",
                placeholder="sk-...",
                disabled=True,
            )
        with c2:
            st.session_state["api_claude"] = st.text_input(
                "🔑 Claude API Key",
                value=st.session_state.get("api_claude", ""),
                type="password",
                placeholder="sk-ant-...",
                disabled=True,
            )

        # Connectivity Check
        if st.button(t("st.test_conn"), type="primary"):
            if not st.session_state.get("api_gemini"):
                st.error(t("st.key_first"))
            else:
                with st.spinner(t("st.testing")):
                    try:
                        from google import genai
                        client = genai.Client(api_key=st.session_state["api_gemini"])
                        response = client.models.generate_content(
                            model=resolve_model(DEFAULT_MODEL),
                            contents="Reply with the two words: connection works",
                        )
                        st.success(t("st.conn_ok", reply=response.text.strip()[:80]))
                    except Exception as e:
                        st.error(t("st.conn_failed", error=e))

    with st.expander(t("st.model_pref")):
        st.radio(
            t("st.model_label"),
            MODEL_NAMES,
            key="ai_model_preference",
            help=t("st.model_help"),
        )

    with st.expander(t("st.out_lang"), expanded=False):
        st.caption(t("st.out_lang_caption"))
        st.radio(
            t("st.lang_label"),
            list(LANGUAGES),
            format_func=lambda c: LANGUAGES[c]["label"],
            key="output_language",
        )

    with st.expander(t("st.ui_lang"), expanded=False):
        st.caption(t("st.ui_lang_caption"))
        st.radio(
            t("st.lang_label"),
            list(UI_LANGUAGES),
            format_func=lambda c: UI_LANGUAGES[c],
            key="ui_language",
        )


def render_data():
    st.markdown(t("dm.title"))

    with st.expander(t("dm.export"), expanded=True):
        st.markdown(t("dm.export_hint"))

        snapshot = get_state_snapshot()
        # Remove API keys from export for security
        export_data = {k: v for k, v in snapshot.items() if "api_" not in k}

        json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
        st.download_button(
            t("dm.download"),
            data=json_str.encode("utf-8"),
            file_name="imdad_workspace.json",
            mime="application/json",
        )
        st.caption(t("dm.size", kb=len(json_str) // 1024))

    with st.expander(t("dm.import")):
        uploaded_json = st.file_uploader(t("dm.import_upload"), type=["json"], key="workspace_import")
        if uploaded_json:
            try:
                data = json.loads(uploaded_json.getvalue().decode("utf-8"))
                if st.button(t("dm.import_btn"), type="primary"):
                    load_state_snapshot(data)
                    st.success(t("dm.import_ok"))
                    st.rerun()
            except Exception as e:
                st.error(t("dm.import_failed", error=e))

    with st.expander(t("dm.clear")):
        st.warning(t("dm.clear_warn"))
        c1, c2 = st.columns(2)
        with c1:
            if st.button(t("dm.clear_analysis"), width="stretch"):
                from utils.state import reset_analysis
                reset_analysis()
                st.success(t("dm.cleared"))
                st.rerun()
        with c2:
            confirm = st.checkbox(t("dm.clear_confirm"))
            if st.button(t("dm.clear_all"), width="stretch", disabled=not confirm):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
