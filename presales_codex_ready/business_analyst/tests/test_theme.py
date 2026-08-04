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
