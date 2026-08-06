"""
components/theme.py — نظام التصميم البصري / Visual design system.

هوية واحدة لكل الشاشات: الألوان والخطوط والمسافات والمكوّنات المتكرّرة
(بطاقة، شارة، حلقة نسبة، شريط تنقّل علوي). كل ما يخصّ الشكل يعيش هنا،
فتغيير الهوية لاحقاً يمسّ ملفاً واحداً لا كل ملفات `views/`.

Design tokens and shared visual primitives. Views import the helpers below
instead of writing inline styles, so the identity stays in one place.

الأيقونات SVG مدمجة (`components/icons.py`) لا خط من شبكة توصيل: الأيقونة
جزء من بنية هذه الواجهة، وشبكة عميل تحجب النطاق كانت ستُفرغ الشاشة منها.
الأزرار وحدها بلا أيقونة، فـ`st.button` لا يعرض HTML.
"""
from __future__ import annotations

import html
from typing import Iterable, Sequence

import streamlit as st

from components.icons import svg

# ─── رموز التصميم / Design tokens ─────────────────────────────────────────────
# مستوحاة من منصات العطاءات الحكومية: كحلي داكن للهوية، أزرق ساطع للفعل.
TOKENS = {
    "primary": "#1a4980",
    "primary_hover": "#133a66",
    "secondary": "#2270c1",
    "secondary_tint": "#eaf3fb",
    "ink": "#111827",
    "slate": "#4b5563",
    "muted": "#6b7280",
    "muted_2": "#9ca3af",
    "line": "#e5e7eb",
    "line_soft": "#f3f4f6",
    "bg": "#f8fafc",
    "surface": "#ffffff",
    "green": "#059669",
    "green_tint": "#ecfdf5",
    "amber": "#d97706",
    "amber_tint": "#fffbeb",
    "red": "#dc2626",
    "red_tint": "#fef2f2",
}

FONT_STACK = "'IBM Plex Sans Arabic', 'Tajawal', 'Segoe UI', sans-serif"

# نغمات الحالة: مفتاح واحد يقود اللون في الشارات والبطاقات وحلقات النسبة.
TONES = {
    "ok": ("green", "green_tint"),
    "warn": ("amber", "amber_tint"),
    "error": ("red", "red_tint"),
    "info": ("secondary", "secondary_tint"),
    "neutral": ("slate", "line_soft"),
}


def tone_colors(tone: str) -> tuple[str, str]:
    """(لون النص، لون الخلفية) لنغمة الحالة."""
    fg, bg = TONES.get(tone, TONES["info"])
    return TOKENS[fg], TOKENS[bg]


def _esc(text) -> str:
    return html.escape(str(text), quote=False)


# ─── الأنماط العامة / Global stylesheet ───────────────────────────────────────

def _css(rtl: bool) -> str:
    direction = "rtl" if rtl else "ltr"
    side = "right" if rtl else "left"
    opposite = "left" if rtl else "right"
    v = TOKENS

    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@300;400;500;600;700&display=swap');

:root {{
  --primary: {v['primary']};
  --primary-hover: {v['primary_hover']};
  --secondary: {v['secondary']};
  --secondary-tint: {v['secondary_tint']};
  --ink: {v['ink']};
  --slate: {v['slate']};
  --muted: {v['muted']};
  --muted-2: {v['muted_2']};
  --line: {v['line']};
  --line-soft: {v['line_soft']};
  --bg: {v['bg']};
  --surface: {v['surface']};
  --green: {v['green']}; --green-tint: {v['green_tint']};
  --amber: {v['amber']}; --amber-tint: {v['amber_tint']};
  --red: {v['red']};     --red-tint: {v['red_tint']};
  --shadow-sm: 0 1px 2px 0 rgba(0,0,0,.05);
  --shadow-md: 0 4px 6px -1px rgba(0,0,0,.1), 0 2px 4px -1px rgba(0,0,0,.06);
  --shadow-lg: 0 10px 15px -3px rgba(0,0,0,.1), 0 4px 6px -2px rgba(0,0,0,.05);
}}

/* ── الخط الأساسي ── */
*, .stApp, .main, .block-container, [data-testid="stHeader"] {{
    font-family: {FONT_STACK} !important;
}}

/* ── أيقونات Material داخل عناصر Streamlit ──
   القاعدة أعلاه تستهدف كل العناصر وتفرض خط الواجهة على الأيقونة، والأيقونة
   محرف ارتباط (ligature) في خط Material: بخط بلا ارتباطات يظهر اسمها نصاً
   خاماً. نعيد لها خطها هنا، ومُحدِّد السمة أعلى أولوية فيغلب. */
span[data-testid="stIconMaterial"],
[data-testid="stIconMaterial"],
.material-icons, .material-icons-outlined,
.material-symbols-rounded, .material-symbols-outlined,
span[class*="material-symbols"] {{
    font-family: 'Material Symbols Rounded', 'Material Symbols Outlined',
                 'Material Icons' !important;
    font-weight: normal !important;
    font-style: normal !important;
    letter-spacing: normal !important;
    text-transform: none !important;
    direction: ltr !important;
    white-space: nowrap !important;
    word-wrap: normal !important;
    font-feature-settings: 'liga' !important;
    -webkit-font-feature-settings: 'liga' !important;
    font-variant-ligatures: common-ligatures !important;
    -webkit-font-smoothing: antialiased;
}}

/* الأيقونات المدمجة: SVG يرث المقاس واللون من موضعه */
.app-icon {{ display: inline-flex; align-items: center; justify-content: center; }}

.stApp, body {{
    background-color: var(--bg) !important;
    color: var(--ink) !important;
    font-size: 14px;
}}

.block-container {{
    padding-top: 1rem !important;
    padding-bottom: 4rem !important;
    max-width: 1400px;
}}

/* ترويسة Streamlit تفسح المكان للشريط العلوي الخاص بنا */
[data-testid="stHeader"] {{ background: transparent !important; height: 0 !important; }}
[data-testid="stToolbar"] {{ display: none !important; }}
[data-testid="stDecoration"] {{ display: none !important; }}

/* الشريط الجانبي مستبدَل بالشريط العلوي */
[data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] {{ display: none !important; }}

/* ── الاتجاه ── */
.stApp, .main, .block-container,
.stTextInput, .stTextArea, .stSelectbox, .stRadio, .stCheckbox,
.stExpander, .stDataFrame, .stMarkdown,
.stTextInput input, .stTextArea textarea,
.stSelectbox [data-baseweb="select"] {{
    direction: {direction};
    text-align: {side};
}}

/* ── الشريط العلوي / Top navigation ── */
.st-key-topnav {{
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 12px;
    box-shadow: var(--shadow-sm);
    padding: 10px 18px;
    margin-bottom: 24px;
}}
.st-key-topnav [data-testid="stHorizontalBlock"] {{ align-items: center; gap: 6px; }}

.tn-brand {{ display: flex; align-items: center; gap: 12px; }}
.tn-mark {{
    width: 40px; height: 40px; border-radius: 8px;
    background: var(--secondary-tint);
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
}}
.tn-mark .app-icon {{ line-height: 0; }}
.tn-brand-text {{ font-weight: 700; font-size: 15px; color: var(--primary); line-height: 1.2; }}
.tn-brand-sub {{ font-size: 11px; color: var(--muted); margin-top: 2px; }}

.tn-user {{ display: flex; align-items: center; gap: 10px; justify-content: flex-end; }}
.tn-user-name {{ font-size: 12px; font-weight: 600; color: var(--ink); line-height: 1.3; }}
.tn-user-role {{ font-size: 11px; color: var(--muted); }}
.tn-avatar {{
    width: 36px; height: 36px; border-radius: 50%;
    background: var(--primary); color: #fff; font-size: 12px; font-weight: 700;
    display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}}

/* عناصر التنقّل: زر Streamlit عادي مُعاد تشكيله. النشط ثانوي اللون (primary).
   `div.` زيادة أولوية مقصودة: قواعد الأزرار العامة تأتي لاحقاً في هذا الملف
   وتساوي هذا المُحدِّد وزناً، فكانت تغلبه بترتيب الورود. */
div.st-key-topnav .stButton > button {{
    width: 100%;
    white-space: nowrap;
    min-height: 40px;
    border: 1px solid transparent !important;
    background: transparent !important;
    color: var(--slate) !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    padding: 9px 10px !important;
    border-radius: 8px !important;
    box-shadow: none !important;
    transition: all .2s ease;
}}
div.st-key-topnav .stButton > button:hover {{
    background: var(--line-soft) !important;
    color: var(--primary) !important;
    transform: none;
}}
div.st-key-topnav .stButton > button[kind="primary"],
div.st-key-topnav .stButton > button[kind="primary"]:hover {{
    background: var(--secondary-tint) !important;
    color: var(--secondary) !important;
    border-color: #dbeafe !important;
}}

/* ── العناوين ── */
.page-title {{
    font-size: 22px; font-weight: 700; color: var(--primary);
    display: flex; align-items: center; gap: 12px; margin-bottom: 6px;
}}
.page-desc {{ font-size: 14px; color: var(--muted); margin-bottom: 20px; }}
.block-title {{
    font-size: 16px; font-weight: 700; color: var(--primary);
    display: flex; align-items: center; gap: 10px; margin: 8px 0 14px;
}}

h1 {{ color: var(--primary) !important; font-size: 22px !important; font-weight: 700 !important; }}
h2, h3 {{ color: var(--primary) !important; font-weight: 700 !important; }}
hr {{ border-color: var(--line) !important; }}

/* ── البطاقات والشبكات ── */
.app-card {{
    background: var(--surface); border: 1px solid var(--line);
    border-radius: 12px; box-shadow: var(--shadow-sm);
    padding: 20px 22px; margin-bottom: 12px;
    transition: box-shadow .2s ease;
}}
.app-card:hover {{ box-shadow: var(--shadow-md); }}
.app-card-title {{ font-size: 15px; font-weight: 700; color: var(--primary); }}

.grid {{ display: grid; gap: 16px; }}
.grid-2 {{ grid-template-columns: repeat(2, 1fr); }}
.grid-3 {{ grid-template-columns: repeat(3, 1fr); }}
.grid-4 {{ grid-template-columns: repeat(4, 1fr); }}
.grid-5 {{ grid-template-columns: repeat(5, 1fr); }}
@media (max-width: 1100px) {{
  .grid-4, .grid-5 {{ grid-template-columns: repeat(2, 1fr); }}
  .grid-3 {{ grid-template-columns: repeat(2, 1fr); }}
}}
@media (max-width: 640px) {{
  .grid-2, .grid-3, .grid-4, .grid-5 {{ grid-template-columns: 1fr; }}
}}

/* مربّع أيقونة شفاف */
.isq {{ display: flex; align-items: center; justify-content: center; flex-shrink: 0; }}
.isq-lg {{ width: 48px; height: 48px; }}
.isq-md {{ width: 40px; height: 40px; }}
.isq-sm {{ width: 32px; height: 32px; }}

/* مؤشّر (KPI) */
.kpi {{
    background: var(--surface); border: 1px solid var(--line); border-radius: 12px;
    box-shadow: var(--shadow-sm); padding: 18px 20px;
    display: flex; align-items: center; gap: 14px;
}}
.kpi .l {{ font-size: 12px; color: var(--muted); }}
.kpi .v {{ font-size: 17px; font-weight: 700; color: var(--primary); margin-top: 4px; }}

/* لوحة رقم كبير */
.stat-tile {{
    background: var(--surface); border: 1px solid var(--line);
    border-radius: 12px; padding: 18px; text-align: center;
}}
.stat-tile .v {{ font-size: 22px; font-weight: 700; color: var(--primary); }}
.stat-tile .l {{ font-size: 12px; color: var(--slate); margin-top: 4px; }}

/* خطوة سير عمل */
.step-card {{
    background: var(--surface); border: 1px solid var(--line); border-radius: 12px;
    box-shadow: var(--shadow-sm); padding: 22px 16px; text-align: center;
    transition: border-color .2s ease;
}}
.step-card:hover {{ border-color: var(--secondary-tint); }}
.step-card .isq-lg {{ margin: 0 auto 14px; }}
.step-title {{ font-size: 14px; font-weight: 700; color: var(--primary); margin-bottom: 8px; }}
.step-desc {{ font-size: 12px; color: var(--slate); line-height: 1.6; }}

/* قدرة المنصّة */
.cap-card {{
    background: var(--surface); border: 1px solid var(--line); border-radius: 12px;
    box-shadow: var(--shadow-sm); padding: 20px;
    display: flex; gap: 14px; align-items: flex-start;
}}
.cap-title {{ font-size: 15px; font-weight: 700; color: var(--primary); margin-bottom: 6px; }}
.cap-desc {{ font-size: 13px; color: var(--slate); line-height: 1.6; }}

/* صف بيانات */
.data-row {{
    display: flex; justify-content: space-between; gap: 16px;
    padding: 11px 0; border-bottom: 1px solid var(--line-soft); font-size: 13px;
}}
.data-row:last-child {{ border-bottom: none; }}
.data-row .k {{ color: var(--slate); font-weight: 500; }}
.data-row .v {{ font-weight: 600; color: var(--ink); }}

/* شارات ورقائق */
.pill {{
    display: inline-flex; align-items: center; gap: 6px;
    font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 6px;
}}
.tag-list {{ display: flex; flex-wrap: wrap; gap: 8px; }}
.tag-chip {{
    background: var(--secondary-tint); color: var(--secondary);
    border-radius: 20px; padding: 6px 14px; font-size: 12px; font-weight: 600;
}}

/* حلقة نسبة — بلا رسوم خارجية، تدرّج مخروطي خالص */
.ring {{ display: flex; align-items: center; gap: 18px; }}
.ring-dial {{
    position: relative; border-radius: 50%; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
}}
.ring-hole {{
    position: absolute; inset: 10px; background: var(--surface);
    border-radius: 50%; display: flex; flex-direction: column;
    align-items: center; justify-content: center;
}}
.ring-hole .v {{ font-size: 22px; font-weight: 700; color: var(--primary); line-height: 1.1; }}
.ring-hole .l {{ font-size: 10px; color: var(--slate); }}

/* بطاقة ملاحظة مراجعة */
.finding-card {{
    border: 1px solid var(--line); border-radius: 8px; padding: 14px 18px;
    margin-bottom: 10px; background: var(--surface);
}}
.finding-title {{ font-size: 14px; font-weight: 600; display: flex; align-items: center; gap: 8px; }}
.finding-body {{ font-size: 13px; color: var(--slate); line-height: 1.7; margin-top: 8px; }}
.finding-body b {{ color: var(--ink); }}

/* شريط تقدّم */
.progress-track {{
    height: 10px; background: var(--line-soft); border-radius: 20px;
    overflow: hidden; margin-top: 8px;
}}
.progress-fill {{ height: 100%; background: var(--secondary); }}

/* ── عناصر Streamlit ── */
.stTextInput input, .stTextArea textarea {{
    background: var(--surface) !important;
    border: 1px solid var(--line) !important;
    border-radius: 8px !important;
    font-size: 13px !important;
    color: var(--ink) !important;
    transition: border-color .2s;
}}
.stTextInput input:focus, .stTextArea textarea:focus {{
    border-color: var(--secondary) !important;
    box-shadow: 0 0 0 3px var(--secondary-tint) !important;
}}

.stButton > button {{
    font-weight: 600 !important;
    font-size: 13px !important;
    border-radius: 8px !important;
    transition: all .2s ease !important;
}}
.stButton > button[kind="primary"] {{
    background: var(--secondary) !important;
    color: #fff !important;
    border: none !important;
    box-shadow: var(--shadow-sm) !important;
}}
.stButton > button[kind="primary"]:hover {{ background: var(--primary) !important; }}
.stButton > button[kind="secondary"] {{
    background: var(--surface) !important;
    color: var(--secondary) !important;
    border: 1px solid var(--secondary) !important;
}}
.stButton > button[kind="secondary"]:hover {{ background: var(--secondary-tint) !important; }}
.stButton > button:disabled {{ opacity: .5 !important; }}

/* أزرار النماذج تُبنى بعنصر آخر فلا تلتقط قواعد .stButton أعلاه */
[data-testid="stFormSubmitButton"] > button {{
    font-weight: 600 !important; font-size: 13px !important;
    border-radius: 8px !important;
}}
[data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"] {{
    background: var(--secondary) !important; color: #fff !important; border: none !important;
}}
[data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"]:hover {{
    background: var(--primary) !important;
}}

.stTabs [data-baseweb="tab-list"] {{
    gap: 8px; background: transparent;
    border-bottom: 1px solid var(--line); padding: 0;
}}
.stTabs [data-baseweb="tab"] {{
    font-weight: 600 !important; font-size: 14px !important;
    color: var(--slate) !important;
    border-bottom: 3px solid transparent !important;
    padding: 10px 18px !important;
}}
.stTabs [aria-selected="true"] {{
    color: var(--secondary) !important;
    border-bottom-color: var(--secondary) !important;
    background: transparent !important;
}}
.stTabs [data-baseweb="tab-highlight"] {{ background-color: var(--secondary) !important; }}

[data-testid="stExpander"] details {{
    background: var(--surface) !important;
    border: 1px solid var(--line) !important;
    border-radius: 10px !important;
}}
[data-testid="stExpander"] summary {{ font-weight: 700 !important; color: var(--primary) !important; }}

div[data-testid="stMetric"] {{
    background: var(--surface); border: 1px solid var(--line);
    border-radius: 12px; padding: 14px 18px; box-shadow: var(--shadow-sm);
}}
div[data-testid="stMetricLabel"] p {{ font-size: 12px !important; color: var(--muted) !important; }}
div[data-testid="stMetricValue"] {{ font-size: 18px !important; color: var(--primary) !important; }}

.stAlert {{ border-radius: 8px !important; }}
.stDataFrame, [data-testid="stDataFrame"] {{ direction: {direction}; }}
[data-testid="stFileUploaderDropzone"] {{
    background: var(--bg) !important;
    border: 2px dashed var(--line) !important;
    border-radius: 12px !important;
}}
[data-testid="stFileUploaderDropzone"]:hover {{
    border-color: var(--secondary) !important;
    background: var(--secondary-tint) !important;
}}

/* شارة التوكنز في الشريط العلوي */
.token-badge {{
    display: inline-flex; align-items: center; gap: 6px;
    background: var(--secondary-tint); color: var(--secondary);
    padding: 5px 12px; border-radius: 20px; font-size: 12px; font-weight: 600;
}}

.footnote {{
    text-align: {opposite}; font-size: 12px; color: var(--muted-2);
    padding: 24px 0 8px;
}}
</style>
"""


def inject(rtl: bool = True) -> None:
    """يحقن الهوية البصرية كاملة. يُستدعى مرة واحدة في أعلى `app.py`."""
    st.markdown(_css(rtl), unsafe_allow_html=True)


# ─── مكوّنات معروضة / Rendered primitives ─────────────────────────────────────

_ICON_PX = {"lg": 28, "md": 24, "sm": 18}


def icon(name: str, size: str = "md", color: str | None = None) -> str:
    """أيقونة داخل مربّع شفاف — HTML خام للتركيب داخل بطاقة."""
    glyph = svg(name, _ICON_PX.get(size, 24), color or TOKENS["secondary"])
    return f'<div class="isq isq-{size} app-icon">{glyph}</div>'


def page_header(title: str, description: str = "", bi_icon: str = "") -> None:
    glyph = svg(bi_icon, 26, TOKENS["primary"]) if bi_icon else ""
    desc = f'<div class="page-desc">{_esc(description)}</div>' if description else ""
    st.markdown(
        f'<div class="page-title">{glyph}<span>{_esc(title)}</span></div>{desc}',
        unsafe_allow_html=True,
    )


def block_title(title: str, bi_icon: str = "") -> None:
    glyph = svg(bi_icon, 20, TOKENS["primary"]) if bi_icon else ""
    st.markdown(
        f'<div class="block-title">{glyph}<span>{_esc(title)}</span></div>',
        unsafe_allow_html=True,
    )


def pill_html(label: str, tone: str = "info") -> str:
    fg, bg = tone_colors(tone)
    return f'<span class="pill" style="background:{bg};color:{fg};">{_esc(label)}</span>'


def pill(label: str, tone: str = "info") -> None:
    st.markdown(pill_html(label, tone), unsafe_allow_html=True)


def kpi_row(items: Sequence[tuple[str, str, str]], tones: Sequence[str] | None = None) -> None:
    """
    صف مؤشّرات: كل عنصر (أيقونة، عنوان، قيمة).
    `tones` اختيارية بطول القائمة نفسها لتلوين القيمة.
    """
    cells = []
    for i, (glyph, label, value) in enumerate(items):
        color = ""
        if tones and i < len(tones) and tones[i]:
            color = f'style="color:{tone_colors(tones[i])[0]};"'
        cells.append(
            f'<div class="kpi">{icon(glyph, "md")}'
            f'<div><div class="l">{_esc(label)}</div>'
            f'<div class="v" {color}>{_esc(value)}</div></div></div>'
        )
    columns = min(len(cells), 4) or 1
    st.markdown(
        f'<div class="grid grid-{columns}">{"".join(cells)}</div>',
        unsafe_allow_html=True,
    )


def stat_tiles(items: Sequence[tuple[str, str]], tones: Sequence[str] | None = None) -> None:
    """لوحات رقم كبير: كل عنصر (القيمة، الوصف)."""
    cells = []
    for i, (value, label) in enumerate(items):
        color = ""
        if tones and i < len(tones) and tones[i]:
            color = f'style="color:{tone_colors(tones[i])[0]};"'
        cells.append(
            f'<div class="stat-tile"><div class="v" {color}>{_esc(value)}</div>'
            f'<div class="l">{_esc(label)}</div></div>'
        )
    columns = min(len(cells), 4) or 1
    st.markdown(
        f'<div class="grid grid-{columns}">{"".join(cells)}</div>',
        unsafe_allow_html=True,
    )


def step_cards(items: Sequence[tuple[str, str, str]]) -> None:
    """خطوات سير العمل: (أيقونة، عنوان، وصف)."""
    cells = [
        f'<div class="step-card">{icon(glyph, "lg")}'
        f'<div class="step-title">{_esc(title)}</div>'
        f'<div class="step-desc">{_esc(desc)}</div></div>'
        for glyph, title, desc in items
    ]
    columns = min(len(cells), 5) or 1
    st.markdown(
        f'<div class="grid grid-{columns}">{"".join(cells)}</div>',
        unsafe_allow_html=True,
    )


def capability_cards(items: Sequence[tuple[str, str, str]]) -> None:
    """بطاقات القدرات: (أيقونة، عنوان، وصف)."""
    cells = [
        f'<div class="cap-card">{icon(glyph, "md")}'
        f'<div><div class="cap-title">{_esc(title)}</div>'
        f'<div class="cap-desc">{_esc(desc)}</div></div></div>'
        for glyph, title, desc in items
    ]
    columns = min(len(cells), 3) or 1
    st.markdown(
        f'<div class="grid grid-{columns}">{"".join(cells)}</div>',
        unsafe_allow_html=True,
    )


def tag_chips(labels: Iterable[str]) -> None:
    chips = "".join(f'<span class="tag-chip">{_esc(x)}</span>' for x in labels)
    if chips:
        st.markdown(f'<div class="tag-list">{chips}</div>', unsafe_allow_html=True)


def donut_html(value: int, label: str = "", size: int = 120, tone: str = "info") -> str:
    """
    حلقة نسبة بتدرّج مخروطي — لا Chart.js ولا صورة، فتعمل داخل Streamlit
    الذي يجرّد النصوص البرمجية من HTML المحقون.
    """
    value = max(0, min(100, int(value)))
    fg, _ = tone_colors(tone)
    return (
        f'<div class="ring-dial" style="width:{size}px;height:{size}px;'
        f'background:conic-gradient({fg} {value}%, {TOKENS["line"]} 0);">'
        f'<div class="ring-hole"><div class="v">{value}%</div>'
        f'<div class="l">{_esc(label)}</div></div></div>'
    )


def readiness_ring(value: int, title: str, description: str,
                   label: str = "", tone: str = "info") -> None:
    st.markdown(
        f'<div class="app-card"><div class="ring">{donut_html(value, label, tone=tone)}'
        f'<div><div class="app-card-title" style="margin-bottom:6px;">{_esc(title)}</div>'
        f'<div class="cap-desc">{_esc(description)}</div></div></div></div>',
        unsafe_allow_html=True,
    )


def progress_bar(label: str, percent: int, caption: str = "") -> None:
    percent = max(0, min(100, int(percent)))
    note = f'<div class="data-row" style="border:none;padding:0 0 8px;">' \
           f'<span class="k">{_esc(caption or label)}</span>' \
           f'<span class="v">{percent}%</span></div>'
    st.markdown(
        f'<div class="app-card">{note}'
        f'<div class="progress-track"><div class="progress-fill" '
        f'style="width:{percent}%;"></div></div></div>',
        unsafe_allow_html=True,
    )


def data_rows(rows: Sequence[tuple[str, str]], tones: Sequence[str] | None = None) -> None:
    body = []
    for i, (key, value) in enumerate(rows):
        color = ""
        if tones and i < len(tones) and tones[i]:
            color = f'style="color:{tone_colors(tones[i])[0]};"'
        body.append(
            f'<div class="data-row"><span class="k">{_esc(key)}</span>'
            f'<span class="v" {color}>{_esc(value)}</span></div>'
        )
    st.markdown(f'<div class="app-card">{"".join(body)}</div>', unsafe_allow_html=True)


def finding_card(title: str, body_html: str, tone: str = "warn",
                 bi_icon: str = "") -> None:
    """
    ملاحظة مراجعة. `body_html` يُمرَّر كما هو ليسمح بـ<b> و<br> — على المُنادي
    أن يهرّب ما يأتي من النموذج أو المستخدم.
    """
    fg, _ = tone_colors(tone)
    glyph = svg(bi_icon, 16, fg) if bi_icon else ""
    st.markdown(
        f'<div class="finding-card" style="border-inline-start:4px solid {fg};">'
        f'<div class="finding-title" style="color:{fg};">{glyph}{_esc(title)}</div>'
        f'<div class="finding-body">{body_html}</div></div>',
        unsafe_allow_html=True,
    )


def escape(text) -> str:
    """تهريب نص لإدراجه داخل HTML مبنيّ في الواجهة."""
    return _esc(text)


# ─── الشريط العلوي / Top navigation bar ───────────────────────────────────────

def _initials(name: str) -> str:
    """أول حرفين من أول كلمتين — يعملان للعربية والإنجليزية معاً."""
    parts = [p for p in str(name).split() if p]
    if not parts:
        return "؟"
    if len(parts) == 1:
        return parts[0][:2]
    return parts[0][:1] + parts[1][:1]


def nav_bar(
    items: Sequence[tuple[str, str]],
    current: str,
    brand: str,
    tagline: str,
    user_name: str,
    user_role: str,
    logout_label: str,
    state_key: str = "nav_selection",
) -> bool:
    """
    يرسم شريط التنقّل العلوي ويُرجع: هل ضُغط زر الخروج.

    كل عنصر: (مفتاح الصفحة، التسمية الظاهرة).

    الصفحة المطلوبة تُكتب في `state_key` من ردّ نداء `on_click` لا من قيمة
    الزر: ردّ النداء يسبق إعادة تشغيل السكربت، فيُرسم الشريط والصفحة معاً على
    الحالة الجديدة. لو قُرئ الضغط بعد الرسم لتأخّر إبراز العنصر دورة كاملة —
    عنصر مُبرز لصفحة أخرى غير المعروضة.
    """
    def _select(page: str) -> None:
        st.session_state[state_key] = page

    with st.container(key="topnav"):
        widths = [2.4] + [1.0] * len(items) + [1.5, 0.9]
        cols = st.columns(widths, vertical_alignment="center")

        cols[0].markdown(
            f'<div class="tn-brand"><div class="tn-mark app-icon">'
            f'{svg("briefcase-fill", 22, TOKENS["secondary"])}</div>'
            f'<div><div class="tn-brand-text">{_esc(brand)}</div>'
            f'<div class="tn-brand-sub">{_esc(tagline)}</div></div></div>',
            unsafe_allow_html=True,
        )

        for col, (key, label) in zip(cols[1:], items):
            col.button(
                label,
                key=f"nav_{key}",
                type="primary" if key == current else "secondary",
                width="stretch",
                on_click=_select,
                args=(key,),
            )

        cols[-2].markdown(
            f'<div class="tn-user"><div style="text-align:end;">'
            f'<div class="tn-user-name">{_esc(user_name)}</div>'
            f'<div class="tn-user-role">{_esc(user_role)}</div></div>'
            f'<div class="tn-avatar">{_esc(_initials(user_name))}</div></div>',
            unsafe_allow_html=True,
        )
        logout = cols[-1].button(
            logout_label,
            key="logout_btn",
            width="stretch",
        )

    return logout


def status_strip(items: Sequence[tuple[str, str, str]]) -> None:
    """
    شريط حالة مضغوط تحت التنقّل: (أيقونة، تسمية، نغمة اللون).
    يحمل ما كان في الشريط الجانبي — الموفّر، الشركة، الكراسة، المنافسة.
    """
    cells = []
    for glyph, label, tone in items:
        fg, bg = tone_colors(tone)
        cells.append(
            f'<span class="pill" style="background:{bg};color:{fg};">'
            f'{svg(glyph, 14, fg)}{_esc(label)}</span>'
        )
    st.markdown(
        f'<div class="tag-list" style="margin-bottom:20px;">{"".join(cells)}</div>',
        unsafe_allow_html=True,
    )
