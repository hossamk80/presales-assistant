"""
app.py — محلل متطلبات الأعمال الذكي / Smart Business Requirements Analyst
Refactored: modular architecture, bug fixes, professional UI.

Run with: streamlit run app.py
"""
import streamlit as st

# ─── Must be FIRST Streamlit call ─────────────────────────────────────────────
st.set_page_config(
    page_title="محلل متطلبات الأعمال الذكي",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Imports (after page config) ──────────────────────────────────────────────
from components import theme
from utils.state import init_state
from utils.ai_engine import estimate_tokens
from utils import auth, companies, providers
from utils.i18n import t, ui_is_rtl

# ─── Initialize Session State ─────────────────────────────────────────────────
init_state()

# ب-7: الشركة الفاعلة تُقرأ من الجلسة لا من متغيّر عام تتنازعه الجلسات.
# التركيب قبل أي استدعاء لـ `db.load_company`.
companies.install()

# ─── الهوية البصرية ───────────────────────────────────────────────────────────
# كل الأنماط في `components/theme.py`. الاتجاه يتبع لغة الواجهة: عربي/كليهما
# من اليمين، إنجليزي من اليسار.
theme.inject(rtl=ui_is_rtl())


# ─── حارس الدخول (13-2) ───────────────────────────────────────────────────────
# لا شاشة قبل الدخول. الشرط هنا لا في كل صفحة: نقطة واحدة تُفحص فيُغلق الباب
# كله، ولا تُنسى شاشة عند إضافة صفحة جديدة. الحارس يعيد القراءة من القاعدة كل
# دورة، فحساب عُطِّل يخرج من جلسته فوراً.
if not auth.is_authenticated():
    from views import login
    login.render()
    st.stop()

# ب-7: ملف الشركة يُحمَّل **بعد** الدخول لا قبله — الشركة الفاعلة تتبع
# المستخدم، ولا تُعرف قبل أن يُعرف هو.
if not st.session_state.get("_company_loaded"):
    companies.load_into_session()


# ─── سجل الصفحات ──────────────────────────────────────────────────────────────
# المفتاح ثابت لا يتغيّر مع اللغة؛ التسمية تأتي من i18n وقت الرسم.
NAV_PAGES = ["dashboard", "tenders", "workspace", "company", "settings", "data"]


# ─── الشريط العلوي ────────────────────────────────────────────────────────────
# حلّ محلّ الشريط الجانبي: التنقّل والهوية والخروج في سطر واحد، والمساحة
# الكاملة للعمل نفسه.
_user = auth.current_user()
_current = st.session_state.get("nav_selection", "dashboard")

_logout = theme.nav_bar(
    items=[(key, t(f"nav.{key}")) for key in NAV_PAGES],
    current=_current,
    brand=t("side.brand"),
    tagline=t("side.tagline"),
    user_name=_user.get("display_name") or _user["username"],
    user_role=t("role." + auth.role_of(_user)),
    logout_label=t("au.logout"),
)

if _logout:
    auth.logout()
    st.rerun()

# ─── شريط الحالة ──────────────────────────────────────────────────────────────
# ما كان في الشريط الجانبي: الموفّر والشركة والكراسة والمنافسة المفتوحة.
# الحالة تتبع الموفّر المختار لا Gemini وحده — والموفّر المحلي جاهز بلا مفتاح.
_api_ok = providers.has_credentials()
_company = st.session_state.get("c_name")
_rfp_text = st.session_state.get("rfp_raw_text", "")
_project_name = st.session_state.get("_project_name")

_status = [
    ("folder2-open", f'{t("side.tender")}: {_project_name or t("side.tender_none")}',
     "info" if _project_name else "neutral"),
    ("shield-check",
     f'{providers.active_provider_label()}: '
     f'{t("side.api_connected") if _api_ok else t("side.api_missing")}',
     "ok" if _api_ok else "error"),
    ("building", f'{t("side.company")}: {_company or t("common.not_set")}',
     "ok" if _company else "warn"),
    ("file-earmark-text",
     f'{t("side.rfp")}: '
     f'{t("side.rfp_loaded") if _rfp_text else t("side.rfp_missing")}',
     "ok" if _rfp_text else "neutral"),
]
if _rfp_text:
    _status.append(
        ("cpu", f'{t("side.tokens")} {estimate_tokens(_rfp_text):,}', "info")
    )
theme.status_strip(_status)


# ─── Page Routing ─────────────────────────────────────────────────────────────
nav = st.session_state.get("nav_selection", "dashboard")

# ── Dashboard ─────────────────────────────────────────────────────────────────
if nav == "dashboard":
    theme.page_header(t("dash.title"), t("dash.welcome"), bi_icon="grid")

    # ── مؤشّرات الحالة ──
    from utils.state import get_sections, section_content_key

    _included = [s for s in get_sections() if s.get("include") and s["kind"] == "ai"]
    _done = sum(
        1 for s in _included
        if str(st.session_state.get(section_content_key(s["key"]), "")).strip()
    )
    _ready_pct = round(100 * _done / len(_included)) if _included else 0

    theme.kpi_row(
        [
            ("shield-check", providers.active_provider_label(),
             t("side.api_connected") if _api_ok else t("side.api_missing")),
            ("building", t("dash.company_name"), _company or t("common.none")),
            ("file-earmark-text", t("side.rfp"),
             f"{estimate_tokens(_rfp_text):,} {t('dash.tokens_unit')}" if _rfp_text
             else t("dash.not_loaded")),
            ("list-check", t("dash.sections_done"),
             f"{_ready_pct}% ({_done} / {len(_included)})"),
        ],
        tones=["ok" if _api_ok else "error", None, None, None],
    )

    # ── مؤشرات الأداء (14-7) ──
    #
    # هنا كانت بطاقات «القدرات» تقول ما يفعله النظام. من فتح اللوحة مئة مرة لا
    # يحتاج التعريف — يحتاج أن يعرف كيف يبلي قسم العطاءات. وخطوات البدء تبقى
    # لمن لا منافسة عنده بعد: اللوحة تعرض **قياساً حين يوجد قياس، وإرشاداً حين
    # لا يوجد** — لا صفراً في كل خانة يوهم بأداء سيّئ بدل تركيب جديد.
    from views.dashboard import render_performance

    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
    if not render_performance():
        theme.block_title(t("dash.workflow"), bi_icon="signpost-split")
        theme.step_cards([
            ("gear", t("dash.step1"), t("dash.step1d")),
            ("cloud-arrow-up", t("dash.step2"), t("dash.step2d")),
            ("cpu", t("dash.step3"), t("dash.step3d")),
            ("file-earmark-plus", t("dash.step4"), t("dash.step4d")),
            ("check2-all", t("dash.step5"), t("dash.step5d")),
        ])


# ── Projects ──────────────────────────────────────────────────────────────────
elif nav == "tenders":
    theme.page_header(t("proj.title"), bi_icon="folder2-open")
    from views import projects
    projects.render()


# ── Workspace ─────────────────────────────────────────────────────────────────
elif nav == "workspace":
    theme.page_header(
        f"{t('nav.workspace')}"
        + (f" — {_project_name}" if _project_name else ""),
        bi_icon="layout-text-sidebar-reverse",
    )

    from views import analysis, tables, doc_builder, review

    tab1, tab2, tab3, tab4 = st.tabs([
        f"1. {t('an.tab')}",
        f"2. {t('tb.tab')}",
        f"3. {t('db.tab')}",
        f"4. {t('rv.tab')}",
    ])
    with tab1:
        analysis.render()
    with tab2:
        tables.render()
    with tab3:
        doc_builder.render()
    with tab4:
        review.render()


# ── Company Profile ───────────────────────────────────────────────────────────
elif nav == "company":
    theme.page_header(t("nav.company"), t("co.subtitle"), bi_icon="buildings")
    from views import company
    company.render()


# ── Settings ─────────────────────────────────────────────────────────────────
elif nav == "settings":
    theme.page_header(t("st.title"), bi_icon="gear")
    from views import settings
    settings.render_settings()


# ── Data Management ───────────────────────────────────────────────────────────
elif nav == "data":
    theme.page_header(t("dm.title"), bi_icon="hdd-stack")
    from views import settings
    settings.render_data()


# ─── Auto-save ────────────────────────────────────────────────────────────────
# يُنفَّذ بعد رسم الصفحة، فيلتقط أي تغيير أحدثه المستخدم في هذه الدورة.
from views.projects import autosave  # noqa: E402
autosave()
