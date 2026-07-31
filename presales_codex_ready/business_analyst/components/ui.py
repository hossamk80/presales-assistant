"""
components/ui.py — Reusable UI Components
"""
import inspect
import streamlit as st
from typing import Optional, Callable

from utils.i18n import t


def _accepts_two_args(fn: Callable) -> bool:
    """هل تقبل دالة التوليد معامل تقدّم إضافي إلى جانب اسم النموذج؟"""
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False
    return len([
        p for p in params.values()
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]) >= 2


def section_card(title: str, icon: str = ""):
    """Context manager for a visually grouped card section."""
    st.markdown(
        f"""<div class="app-card">
            <div class="app-card-title">{icon} {title}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def ai_generate_button(
    label: str,
    key: str,
    model_key: str,
    on_generate: Callable,
    result_state_key: str,
    summary_state_key: Optional[str] = None,
    summary_label: Optional[str] = None,
    height: int = 200,
    result_style: str = "info",  # info / success / warning
):
    """
    Reusable AI generation widget: model selector + generate button + result + editable summary.
    Eliminates the repeated col_mod/col_btn pattern.
    """
    from utils.ai_engine import DEFAULT_MODEL, MODEL_NAMES

    default_model = st.session_state.get("ai_model_preference", DEFAULT_MODEL)
    default_index = MODEL_NAMES.index(default_model) if default_model in MODEL_NAMES else 0

    col_mod, col_btn = st.columns([3, 1])
    with col_mod:
        model = st.selectbox(
            t("common.engine"),
            MODEL_NAMES,
            index=default_index,
            key=f"model_{key}",
            label_visibility="collapsed",
        )
    with col_btn:
        generate = st.button(f"⚡ {label}", key=f"btn_{key}", type="primary", width="stretch")

    if generate:
        status = st.empty()
        with st.spinner(t("common.generating")):
            # يُمرَّر للمحرك ليعرض تقدّم التحليل المجزّأ للكراسات الكبيرة
            def report(message: str):
                status.caption(f"⏳ {message}")

            if _accepts_two_args(on_generate):
                result = on_generate(model, report)
            else:
                result = on_generate(model)
            status.empty()
            if result:
                st.session_state[result_state_key] = result
                if summary_state_key and not st.session_state.get(summary_state_key):
                    st.session_state[summary_state_key] = result

    current_result = st.session_state.get(result_state_key, "")
    if current_result:
        if result_style == "success":
            st.success(current_result)
        elif result_style == "warning":
            st.warning(current_result)
        else:
            st.info(current_result)

        if summary_state_key is not None:
            st.session_state[summary_state_key] = st.text_area(
                summary_label or t("common.your_notes"),
                value=st.session_state.get(summary_state_key, current_result),
                height=height,
                key=f"summary_{key}",
            )


def placeholder_warning(text: str) -> bool:
    """Returns True if text contains unfilled placeholders like [اسم الشركة]."""
    import re
    pattern = r'\[.+?\]'
    return bool(re.search(pattern, text))


def status_badge(label: str, status: str):
    """
    Render a small inline badge.
    status: 'ok' | 'warn' | 'error' | 'info'
    """
    colors = {
        "ok": ("#D1FAE5", "#065F46"),
        "warn": ("#FEF3C7", "#92400E"),
        "error": ("#FEE2E2", "#991B1B"),
        "info": ("#DBEAFE", "#1E40AF"),
    }
    bg, fg = colors.get(status, colors["info"])
    st.markdown(
        f'<span style="background:{bg};color:{fg};padding:3px 10px;border-radius:20px;'
        f'font-size:12px;font-weight:600;font-family:Tajawal,sans-serif;">{label}</span>',
        unsafe_allow_html=True,
    )


def metric_card(title: str, value: str, subtitle: str = "", color: str = "#0F172A"):
    st.markdown(
        f"""
        <div style="background:#fff;border:1px solid #E2E8F0;border-radius:10px;
                    padding:18px 20px;margin-bottom:8px;border-top:3px solid {color};">
            <div style="font-size:12px;color:#64748B;font-family:Tajawal,sans-serif;">{title}</div>
            <div style="font-size:26px;font-weight:700;color:{color};font-family:Tajawal,sans-serif;margin:4px 0;">{value}</div>
            <div style="font-size:12px;color:#94A3B8;font-family:Tajawal,sans-serif;">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
