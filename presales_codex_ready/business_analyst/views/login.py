"""
views/login.py — شاشة الدخول وتهيئة أول حساب (13-2)

الشاشة الوحيدة التي تُرسم قبل المصادقة. `app.py` يستدعيها ثم يوقف بقية
السكربت، فلا تُرسم أي شاشة أخرى ولا يُقرأ أي مشروع قبل الدخول.

قاعدة بلا مستخدم فعّال تعرض تهيئة أول حساب بدل الدخول — تركيب جديد أو ترقية
تثبيت قديم لا يجدان أنفسهما مقفلين خارج نظامهما.
"""
import streamlit as st

from utils import auth
from utils.i18n import UI_LANGUAGES, t


def _shell(title: str, subtitle: str):
    st.markdown(
        f"""<div style="text-align:center;padding:24px 0 8px 0;
                    font-family:Tajawal,sans-serif;">
            <div style="font-size:44px;">🏢</div>
            <div style="font-size:22px;font-weight:800;color:#0F172A;">{title}</div>
            <div style="font-size:13px;color:#64748B;margin-top:4px;">{subtitle}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def _language_picker():
    """لغة الواجهة قبل الدخول — وإلا واجه المستخدم الإنجليزي شاشةً عربية."""
    st.radio(
        t("st.lang_label"),
        list(UI_LANGUAGES),
        format_func=lambda c: UI_LANGUAGES[c],
        key="ui_language",
        horizontal=True,
        label_visibility="collapsed",
    )


def _setup_form():
    _shell(t("au.setup_title"), t("au.setup_subtitle"))
    st.info(t("au.setup_hint"))

    with st.form("auth_setup"):
        username = st.text_input(t("au.username"), key="setup_username")
        display_name = st.text_input(t("au.display_name"), key="setup_display_name")
        password = st.text_input(t("au.password"), type="password", key="setup_password")
        confirm = st.text_input(t("au.password_confirm"), type="password",
                                key="setup_confirm")
        submitted = st.form_submit_button(t("au.setup_btn"), type="primary",
                                          width="stretch")

    if not submitted:
        return

    problem = auth.password_problem(password, confirm) or auth.create_first_admin(
        username, password, display_name
    )
    if problem:
        st.error(t(problem))
        return
    st.rerun()


def _login_form():
    _shell(t("au.login_title"), t("au.login_subtitle"))

    with st.form("auth_login"):
        username = st.text_input(t("au.username"), key="login_username")
        password = st.text_input(t("au.password"), type="password", key="login_password")
        submitted = st.form_submit_button(t("au.login_btn"), type="primary",
                                          width="stretch")

    remaining = auth.cooldown_remaining()
    if remaining:
        st.warning(t("au.cooldown_wait", seconds=remaining))

    if not submitted:
        return

    problem = auth.login(username, password)
    if problem:
        # النص المكتوب يبقى: الحقول محفوظة بمفاتيحها، والخطأ لا يمسحها
        st.error(t(problem))
        return
    st.rerun()


def render():
    middle = st.columns([1, 2, 1])[1]
    with middle:
        if auth.needs_setup():
            _setup_form()
        else:
            _login_form()
        st.divider()
        _language_picker()
