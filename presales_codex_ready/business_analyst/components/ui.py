"""
components/ui.py — Reusable UI Components
"""
import inspect
import streamlit as st
from typing import Optional, Callable

from components import theme
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
    """ترويسة قسم مُجمَّعة بصرياً / A visually grouped card section header."""
    st.markdown(
        f'<div class="app-card"><div class="app-card-title">'
        f'{theme.escape(icon)} {theme.escape(title)}</div></div>',
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
    from utils.ai_engine import default_model_name, model_names

    options = model_names()
    default_model = default_model_name()
    default_index = options.index(default_model) if default_model in options else 0

    col_mod, col_btn = st.columns([3, 1])
    with col_mod:
        model = st.selectbox(
            t("common.engine"),
            options,
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
    شارة حالة صغيرة / A small inline status badge.
    status: 'ok' | 'warn' | 'error' | 'info' | 'neutral'
    """
    theme.pill(label, status)


def metric_card(title: str, value: str, subtitle: str = "", tone: str = "info"):
    """بطاقة رقم واحد بلون النغمة / A single-figure card tinted by tone."""
    fg, _ = theme.tone_colors(tone)
    esc = theme.escape
    note = (f'<div style="font-size:12px;color:{theme.TOKENS["muted_2"]};">'
            f'{esc(subtitle)}</div>') if subtitle else ""
    st.markdown(
        f'<div class="app-card" style="border-top:3px solid {fg};">'
        f'<div style="font-size:12px;color:{theme.TOKENS["muted"]};">{esc(title)}</div>'
        f'<div style="font-size:24px;font-weight:700;color:{fg};margin:4px 0;">'
        f'{esc(value)}</div>{note}</div>',
        unsafe_allow_html=True,
    )
