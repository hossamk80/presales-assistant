"""اختبارات ثنائية لغة الواجهة."""
import re

import pytest


@pytest.fixture()
def i18n():
    from utils import i18n
    return i18n


def test_every_string_has_both_languages(i18n):
    """
    التعليمات الدائمة تلزم بوجود العربية والإنجليزية لكل نص واجهة. مفتاح
    ناقص إحدى اللغتين يعني ظهور لغة واحدة لمستخدم اختار الأخرى.
    """
    missing = [
        key for key, entry in i18n.UI_STRINGS.items()
        if not entry.get("ar", "").strip() or not entry.get("en", "").strip()
    ]
    assert not missing, f"مفاتيح تنقصها ترجمة: {missing}"


def test_english_strings_contain_no_arabic(i18n):
    """نص إنجليزي فيه حروف عربية يعني ترجمة منسية."""
    arabic = re.compile(r"[\u0600-\u06FF]")
    leaked = [
        key for key, entry in i18n.UI_STRINGS.items()
        if arabic.search(entry.get("en", ""))
    ]
    assert not leaked, f"نص إنجليزي يحوي عربية: {leaked}"


def test_format_placeholders_match_across_languages(i18n):
    """
    اختلاف حقول التنسيق بين اللغتين يرفع KeyError وقت العرض — أي انهيار
    للواجهة عند تبديل اللغة فقط.
    """
    field = re.compile(r"\{(\w+)\}")
    mismatched = [
        key for key, entry in i18n.UI_STRINGS.items()
        if set(field.findall(entry.get("ar", ""))) != set(field.findall(entry.get("en", "")))
    ]
    assert not mismatched, f"حقول تنسيق غير متطابقة: {mismatched}"


def test_t_returns_selected_language(i18n, fake_streamlit):
    fake_streamlit.session_state["ui_language"] = "ar"
    assert i18n.t("nav.dashboard") == "لوحة التحكم"
    fake_streamlit.session_state["ui_language"] = "en"
    assert i18n.t("nav.dashboard") == "Dashboard"


def test_both_mode_shows_two_languages(i18n, fake_streamlit):
    fake_streamlit.session_state["ui_language"] = "both"
    out = i18n.t("nav.dashboard")
    assert "لوحة التحكم" in out and "Dashboard" in out


def test_unknown_key_returns_key(i18n, fake_streamlit):
    fake_streamlit.session_state["ui_language"] = "en"
    assert i18n.t("no.such.key") == "no.such.key"


def test_unknown_language_falls_back(i18n, fake_streamlit):
    fake_streamlit.session_state["ui_language"] = "zz"
    assert i18n.t("nav.dashboard") == "لوحة التحكم"


def test_formatting_applies(i18n, fake_streamlit):
    fake_streamlit.session_state["ui_language"] = "en"
    assert "5" in i18n.t("proj.count", n=5)


def test_direction_follows_ui_language(i18n, fake_streamlit):
    for lang, rtl in (("ar", True), ("both", True), ("en", False)):
        fake_streamlit.session_state["ui_language"] = lang
        assert i18n.ui_is_rtl() is rtl


def test_ui_language_is_independent_of_output_language(i18n, fake_streamlit):
    """واجهة إنجليزية مع مخرجات عربية وضع مشروع، لا خطأ."""
    from utils import ai_engine

    fake_streamlit.session_state["ui_language"] = "en"
    fake_streamlit.session_state["output_language"] = "ar"
    assert i18n.t("nav.dashboard") == "Dashboard"
    assert ai_engine.is_rtl("ar") is True


def test_views_have_no_hardcoded_arabic_ui_text(app_dir):
    """
    حارس التعليمات الدائمة: نصوص الواجهة تمر من i18n لا مكتوبة مباشرةً.
    التعليقات ونصوص الأمثلة (placeholder) وبيانات المجال مستثناة.
    """
    import ast

    arabic = re.compile(r"[\u0600-\u06FF]")
    allowed_kwargs = {"placeholder", "help", "text"}
    offenders = []

    for path in sorted((app_dir / "views").glob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = getattr(func, "attr", getattr(func, "id", ""))
            # نتجاهل النداءات التي لا ترسم واجهة
            if name not in {
                "markdown", "caption", "info", "warning", "error", "success",
                "button", "checkbox", "radio", "selectbox", "text_input",
                "text_area", "metric", "expander", "form_submit_button", "title",
            }:
                continue
            skip = {kw.arg for kw in node.keywords} & allowed_kwargs
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    if arabic.search(arg.value) and not skip:
                        offenders.append(f"{path.name}:{arg.lineno} {arg.value[:40]}")

    assert not offenders, "نص واجهة عربي خارج i18n:\n" + "\n".join(offenders)
