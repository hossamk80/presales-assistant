"""
اختبارات نظام التصميم البصري (`components/theme.py` و `components/icons.py`).

الهوية صارت مصدراً واحداً تقرأ منه كل الشاشات، فكسرها يظهر في كل مكان دفعةً
واحدة. ما يُحرس هنا: اكتمال مجموعة الأيقونات مقابل ما تطلبه الشيفرة فعلاً،
وتهريب نصوص المستخدم قبل حقنها في HTML، وتطابق الألوان بين طبقتَي التصميم.
"""
import ast
import re
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture()
def theme(fake_streamlit):
    from components import theme as module
    return module


@pytest.fixture()
def icons():
    from components import icons as module
    return module


def _requested_icon_names() -> set[str]:
    """
    أسماء الأيقونات المطلوبة في الشيفرة: وسيط `bi_icon`، ونداءات `icon(...)`
    و `svg(...)`، وأول عنصر في صفوف البطاقات (أيقونة، عنوان، وصف)، وقيم أي
    ثابت اسمه يحمل `ICON` (خرائط الأيقونة حسب الخطورة مثلاً).
    """
    names: set[str] = set()
    for path in [APP_DIR / "app.py", *sorted((APP_DIR / "views").glob("*.py")),
                 APP_DIR / "components" / "theme.py"]:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and "ICON" in target.id
                for target in node.targets
            ):
                # القيم وحدها: مفاتيح الخريطة درجات خطورة أو مقاسات لا أيقونات
                leaves = (node.value.values if isinstance(node.value, ast.Dict)
                          else [node.value])
                for leaf in leaves:
                    if isinstance(leaf, ast.Constant) and isinstance(leaf.value, str):
                        names.add(leaf.value)
            if not isinstance(node, ast.Call):
                continue
            func = getattr(node.func, "attr", getattr(node.func, "id", ""))
            for kw in node.keywords:
                if kw.arg == "bi_icon" and isinstance(kw.value, ast.Constant):
                    if kw.value.value:
                        names.add(kw.value.value)
            if func in {"icon", "svg"} and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    names.add(first.value)
            if func in {"step_cards", "capability_cards", "kpi_row", "status_strip"}:
                for arg in node.args:
                    if not isinstance(arg, (ast.List, ast.Tuple)):
                        continue
                    for row in arg.elts:
                        if isinstance(row, ast.Tuple) and row.elts:
                            head = row.elts[0]
                            if isinstance(head, ast.Constant) and isinstance(head.value, str):
                                names.add(head.value)
    return names


def test_every_requested_icon_exists(icons):
    """
    اسم أيقونة مكتوب خطأً لا يرفع خطأً — يختفي من الشاشة صامتاً. هذا الاختبار
    هو ما يجعله مرئياً.
    """
    missing = sorted(_requested_icon_names() - set(icons.ICON_PATHS))
    assert not missing, f"أيقونات مطلوبة وغير موجودة: {missing}"


def test_icon_set_is_not_dead_weight(icons):
    """أيقونة مدمجة لا تطلبها الشيفرة وزن زائد في الملف."""
    unused = sorted(set(icons.ICON_PATHS) - _requested_icon_names())
    assert not unused, f"أيقونات مدمجة بلا استعمال: {unused}"


def test_unknown_icon_returns_empty_not_error(icons):
    assert icons.svg("no-such-icon") == ""


def test_icon_carries_the_colour_it_is_given(icons):
    assert 'fill="#123456"' in icons.svg("gear", color="#123456")


def test_every_tone_maps_to_real_tokens(theme):
    for tone in theme.TONES:
        fg, bg = theme.tone_colors(tone)
        assert fg.startswith("#") and bg.startswith("#")


def test_unknown_tone_falls_back(theme):
    assert theme.tone_colors("nope") == theme.tone_colors("info")


def test_user_text_is_escaped_before_it_reaches_html(theme):
    """
    عناوين المنافسات وملاحظات النموذج تُحقن في HTML. نص فيه `<` كان سيكسر
    البنية أو يحقن وسماً.
    """
    assert "<script>" not in theme.pill_html("<script>alert(1)</script>")
    assert "&lt;script&gt;" in theme.pill_html("<script>alert(1)</script>")


def test_donut_clamps_out_of_range_values(theme):
    """درجة الجاهزية قد تعود خارج المدى من النموذج."""
    assert "150%" not in theme.donut_html(150)
    assert "100%" in theme.donut_html(150)
    assert "0%" in theme.donut_html(-20)


def test_initials_handle_arabic_and_single_names(theme):
    assert theme._initials("حسام الدوسري") == "حا"
    assert theme._initials("Sara") == "Sa"
    assert theme._initials("   ") == "؟"


def test_streamlit_theme_matches_the_design_tokens(theme):
    """
    الألوان مكتوبة مرتين بالضرورة: مرة لِما نرسمه، ومرة في `config.toml`
    لِما ترسمه Streamlit نفسها. تباعدهما يعني زرّ نموذج بلون غريب وسط الهوية.
    """
    config = (APP_DIR / ".streamlit" / "config.toml").read_text()
    expected = {
        "primaryColor": theme.TOKENS["secondary"],
        "backgroundColor": theme.TOKENS["bg"],
        "secondaryBackgroundColor": theme.TOKENS["surface"],
        "textColor": theme.TOKENS["ink"],
    }
    for key, value in expected.items():
        assert re.search(rf'{key}\s*=\s*"{value}"', config), \
            f"{key} في config.toml لا يطابق رموز التصميم ({value})"


def test_stylesheet_pulls_no_icon_font_from_a_cdn(theme):
    """
    الأيقونات مدمجة عمداً. عودة خط أيقونات من شبكة توصيل تعيد العيب الذي
    أُصلح: شاشة بلا أيقونات خلف شبكة تحجب النطاق.
    """
    css = theme._css(rtl=True)
    assert "bootstrap-icons" not in css
    assert "cdn.jsdelivr.net" not in css


def test_views_do_not_write_raw_colours(theme):
    """
    الهوية تتغيّر من `theme.py` وحده. لون سداسي مكتوب داخل `views/` يفلت من
    ذلك ويبقى على اللون القديم بعد أي تغيير.
    """
    hex_colour = re.compile(r"#[0-9a-fA-F]{6}\b")
    offenders = []
    for path in sorted((APP_DIR / "views").glob("*.py")):
        for i, line in enumerate(path.read_text().splitlines(), start=1):
            if line.lstrip().startswith("#"):
                continue
            if hex_colour.search(line):
                offenders.append(f"{path.name}:{i} {line.strip()[:60]}")
    assert not offenders, "لون مكتوب خارج نظام التصميم:\n" + "\n".join(offenders)


# ─── الخط مُضمَّن لا مُستدعى (ب-1) ─────────────────────────────────────────────
#
# كان `components/theme.py` يستدعي `fonts.googleapis.com` حيّاً في كل فتح صفحة.
# عيبان: التركيب المعزول عن الإنترنت — الشائع في الجهات الحكومية — يفقد الخطّ
# فتتشوّه الواجهة العربية؛ وطلبٌ إلى طرف ثالث يغادر من جهاز يعمل على كرّاسات
# عطاءات.


def test_the_stylesheet_asks_no_third_party_for_anything(theme):
    """
    **الحارس الأساسي**: لا مورد بعيد في الأنماط أصلاً — لا خطاً ولا غيره.
    الأيقونات مدمجة SVG أصلاً، والخطّ صار مُضمَّناً، فبقي أن يُمنع رجوعهما.
    """
    css = theme._css(rtl=True)

    assert "googleapis" not in css
    assert "gstatic" not in css
    assert "http://" not in css
    assert "https://" not in css


def test_no_ui_module_pulls_a_remote_asset():
    """
    والحارس نفسه على كل ملفات الواجهة: استدعاء بعيد يُضاف لاحقاً في أي شاشة
    يُعيد العطب نفسه، ويسقط هنا بدل أن يُكتشف في تركيب معزول عند عميل.
    """
    offenders = []
    for path in list((APP_DIR / "components").glob("*.py")) + \
            list((APP_DIR / "views").glob("*.py")) + [APP_DIR / "app.py"]:
        # الشيفرة وحدها لا التعليقات: تعليقٌ يشرح **ما أُزيل** ليس استدعاءً،
        # وفحص النصّ الخام يجعل توثيق الإصلاح يُسقط اختبار الإصلاح نفسه.
        # `ast.unparse` يُسقط التعليقات ويُبقي السلاسل — وهي ما يهمّنا.
        code = ast.unparse(ast.parse(path.read_text(encoding="utf-8")))
        for marker in ("fonts.googleapis.com", "fonts.gstatic.com",
                       "cdn.jsdelivr.net", "unpkg.com", "cdnjs.cloudflare.com"):
            if marker in code:
                offenders.append(f"{path.name}: {marker}")

    assert not offenders, f"موارد بعيدة في الواجهة: {offenders}"


def test_the_font_is_bundled_for_every_weight_the_css_uses(theme):
    """
    الأوزان الأربعة المستعملة في الأنماط موجودة على القرص. وزنٌ ناقص يسقط
    صامتاً إلى أقرب متوفّر فيتغيّر ثقل العناوين بلا سبب ظاهر.
    """
    assert theme.bundled_font_weights() == [400, 500, 600, 700]

    css = theme._css(rtl=True)
    for weight in (400, 500, 600, 700):
        assert f"font-weight:{weight}" in css, weight


def test_the_font_files_are_real_woff2(theme):
    """ملفٌّ فارغ أو تالف يُقدَّم بنجاح ويعطي واجهة بلا خط — التوقيع يُفحص."""
    for weight, style in theme._FONT_WEIGHTS.items():
        path = theme._FONT_DIR / f"IBMPlexSansArabic-{style}.woff2"
        head = path.read_bytes()[:4]
        assert head == b"wOF2", (style, head)
        assert path.stat().st_size > 20_000, style


def test_the_font_licence_ships_with_the_font(theme):
    """
    الخطّ تحت OFL-1.1 — وإعادة التوزيع مشروطة بمرافقة نصّ الترخيص. غيابه
    مخالفة ترخيص في منتج يُباع.
    """
    licence = theme._FONT_DIR / "LICENSE.txt"

    assert licence.is_file()
    assert "SIL Open Font License" in licence.read_text(encoding="utf-8")


def test_a_missing_font_file_degrades_instead_of_breaking(theme, tmp_path,
                                                          monkeypatch):
    """
    مسار مكسور يجعل المتصفّح ينتظر طلباً فاشلاً في كل تحميل. الأنظف أن تُحذف
    القاعدة ويسقط النص إلى خط النظام — ولهذا تبقى البدائل في `FONT_STACK`.
    """
    monkeypatch.setattr(theme, "_FONT_DIR", tmp_path)
    theme._font_face_css.cache_clear()
    try:
        assert theme._font_face_css() == ""
        assert theme.bundled_font_weights() == []
        # والسلسلة تبقى فيها بدائل النظام فلا تخرج الواجهة بلا خط
        assert "sans-serif" in theme.FONT_STACK
        assert "Segoe UI" in theme.FONT_STACK
    finally:
        theme._font_face_css.cache_clear()


def test_static_serving_is_enabled_where_the_app_runs():
    """
    الخطّ يُقدَّم من `static/` عبر خدمة الملفات الساكنة. `run.sh` يشغّل من جذر
    المستودع، فالإعداد هناك هو الفاعل — ونسخة مجلد التطبيق لمن يشغّل من داخله.
    """
    for config in (APP_DIR.parent.parent / ".streamlit" / "config.toml",
                   APP_DIR / ".streamlit" / "config.toml"):
        assert "enableStaticServing = true" in config.read_text(encoding="utf-8"), config


def test_the_font_lives_next_to_the_app_script(theme):
    """خدمة الملفات الساكنة تقرأ `static/` بجوار السكربت الرئيسي لا سواه."""
    assert theme._FONT_DIR.parent.name == "static"
    assert (theme._FONT_DIR.parent.parent / "app.py").is_file()
