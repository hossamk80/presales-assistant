"""
app.py — IMDAD Enterprise Bid Management Platform
Refactored: modular architecture, bug fixes, professional UI.

Run with: streamlit run app.py
"""
import streamlit as st

# ─── Must be FIRST Streamlit call ─────────────────────────────────────────────
st.set_page_config(
    page_title="إمداد | منصة إدارة العطاءات",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Imports (after page config) ──────────────────────────────────────────────
from utils.state import init_state
from utils.ai_engine import estimate_tokens

# ─── Initialize Session State ─────────────────────────────────────────────────
init_state()

# ─── Global Styles ────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;800&display=swap');

/* ── Base & Typography ── */
*, .stApp, .main, .block-container,
[data-testid="stSidebar"], [data-testid="stHeader"] {
    font-family: 'Tajawal', 'Segoe UI', sans-serif !important;
}

.stApp, body {
    background-color: #F1F5F9 !important;
    color: #1E293B !important;
}

.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 2rem !important;
    max-width: 1200px;
}

/* ── RTL Global ── */
.stApp, .main, .block-container,
[data-testid="stSidebar"],
.stTextInput, .stTextArea, .stSelectbox,
.stRadio, .stCheckbox, .stExpander,
.stDataFrame, .stMarkdown {
    direction: rtl !important;
    text-align: right !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0F172A 0%, #1E293B 100%) !important;
    border-left: none !important;
}

[data-testid="stSidebar"] * {
    color: #CBD5E1 !important;
}

[data-testid="stSidebar"] .stRadio label {
    color: #E2E8F0 !important;
    font-size: 14px !important;
}

[data-testid="stSidebar"] hr {
    border-color: #334155 !important;
}

/* ── Inputs ── */
.stTextInput input,
.stTextArea textarea {
    direction: rtl !important;
    text-align: right !important;
    background: #FFFFFF !important;
    border: 1.5px solid #CBD5E1 !important;
    border-radius: 8px !important;
    font-family: 'Tajawal', sans-serif !important;
    font-size: 14px !important;
    color: #1E293B !important;
    transition: border-color 0.2s;
}
.stTextInput input:focus,
.stTextArea textarea:focus {
    border-color: #3B82F6 !important;
    box-shadow: 0 0 0 3px rgba(59,130,246,0.15) !important;
}

/* ── Buttons ── */
.stButton > button {
    font-family: 'Tajawal', sans-serif !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    transition: all 0.2s ease !important;
}

.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #1D4ED8, #2563EB) !important;
    color: #FFFFFF !important;
    border: none !important;
    box-shadow: 0 2px 8px rgba(37,99,235,0.3) !important;
}

.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #1E40AF, #1D4ED8) !important;
    box-shadow: 0 4px 12px rgba(37,99,235,0.4) !important;
    transform: translateY(-1px);
}

.stButton > button[kind="secondary"] {
    background: #FFFFFF !important;
    color: #1E293B !important;
    border: 1.5px solid #CBD5E1 !important;
}

/* ── Cards & Containers ── */
div[data-testid="stContainer"],
div[data-testid="stVerticalBlock"] > div[data-testid="stContainer"] {
    background: #FFFFFF;
    border-radius: 12px;
    border: 1px solid #E2E8F0;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    padding: 20px 24px;
    margin-bottom: 16px;
}

/* ── Expanders ── */
.streamlit-expanderHeader {
    font-weight: 700 !important;
    font-size: 15px !important;
    color: #1E293B !important;
    background: #F8FAFC !important;
    border-radius: 8px !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: #F1F5F9;
    padding: 4px;
    border-radius: 10px;
}

.stTabs [data-baseweb="tab"] {
    font-family: 'Tajawal', sans-serif !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    padding: 8px 16px !important;
    color: #64748B !important;
}

.stTabs [aria-selected="true"] {
    background: #FFFFFF !important;
    color: #1D4ED8 !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.1) !important;
}

/* ── Metrics ── */
div[data-testid="metric-container"] {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    padding: 12px 16px;
}

/* ── Data Editor ── */
.stDataFrame, [data-testid="stDataFrame"] {
    direction: rtl;
}

/* ── Alerts ── */
.stAlert {
    border-radius: 8px !important;
    font-family: 'Tajawal', sans-serif !important;
}

/* ── Sidebar Nav Radio ── */
[data-testid="stSidebar"] .stRadio > div {
    gap: 4px;
}
[data-testid="stSidebar"] .stRadio label {
    padding: 8px 12px !important;
    border-radius: 6px !important;
    transition: background 0.15s;
}
[data-testid="stSidebar"] .stRadio label:hover {
    background: rgba(255,255,255,0.08) !important;
}

/* ── Token Badge ── */
.token-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #1E293B;
    color: #94A3B8;
    padding: 6px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-family: 'Tajawal', sans-serif;
}
.token-badge span {
    color: #60A5FA;
    font-weight: 700;
}

/* ── Page Title ── */
h1 { 
    color: #0F172A !important;
    font-size: 24px !important;
    font-weight: 800 !important;
}
h2, h3 { 
    color: #1E293B !important;
    font-weight: 700 !important;
}

/* ── Dividers ── */
hr { border-color: #E2E8F0 !important; }

/* ── Select boxes ── */
.stSelectbox [data-baseweb="select"] {
    direction: rtl !important;
    font-family: 'Tajawal', sans-serif !important;
}

</style>
""", unsafe_allow_html=True)


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    # Logo & Brand
    st.markdown("""
    <div style="text-align:center; padding: 16px 0 8px 0;">
        <div style="font-size: 36px;">🏢</div>
        <div style="font-size: 20px; font-weight: 800; color: #F1F5F9; 
                    font-family: Tajawal, sans-serif; letter-spacing: -0.5px;">
            منصة إمداد
        </div>
        <div style="font-size: 11px; color: #64748B; font-family: Tajawal, sans-serif;">
            Enterprise Bid Management
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    nav = st.radio(
        "nav",
        options=[
            "🏠 لوحة التحكم",
            "🚀 مساحة العمل",
            "🏢 ملف الشركة",
            "⚙️ إعدادات النظام",
            "💾 إدارة البيانات",
        ],
        label_visibility="collapsed",
        key="nav_radio",
    )
    st.session_state["nav_selection"] = nav

    st.divider()

    # Status Panel
    company = st.session_state.get("c_name")
    api_ok = bool(st.session_state.get("api_gemini"))
    rfp_ok = bool(st.session_state.get("rfp_raw_text"))

    st.markdown(f"""
    <div style="font-family:Tajawal,sans-serif;font-size:12px;padding:8px 4px;">
        <div style="margin-bottom:4px;">{'🟢' if api_ok else '🔴'} &nbsp; Gemini API: {'متصل' if api_ok else 'غير مُهيأ'}</div>
        <div style="margin-bottom:4px;">{'🟢' if company else '🟡'} &nbsp; الشركة: {company or 'غير محددة'}</div>
        <div>{'🟢' if rfp_ok else '⚪'} &nbsp; كراسة الشروط: {'محمّلة' if rfp_ok else 'لم تُحمَّل بعد'}</div>
    </div>
    """, unsafe_allow_html=True)

    if rfp_ok:
        tokens = estimate_tokens(st.session_state["rfp_raw_text"])
        st.markdown(
            f'<div class="token-badge">التوكنز: <span>{tokens:,}</span></div>',
            unsafe_allow_html=True,
        )


# ─── Page Routing ─────────────────────────────────────────────────────────────
nav = st.session_state.get("nav_selection", "🏠 لوحة التحكم")

# ── Dashboard ─────────────────────────────────────────────────────────────────
if nav == "🏠 لوحة التحكم":
    st.title("لوحة التحكم")
    st.markdown("مرحباً بك في **منصة إمداد** لإدارة العروض الفنية ومراحل ما قبل البيع.")

    st.divider()

    # KPI Cards
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        status = "✅ متصل" if st.session_state.get("api_gemini") else "❌ غير مُهيأ"
        st.metric("Gemini API", status)
    with c2:
        st.metric("اسم الشركة", st.session_state.get("c_name") or "—")
    with c3:
        rfp_text = st.session_state.get("rfp_raw_text", "")
        st.metric("كراسة الشروط", f"{estimate_tokens(rfp_text):,} توكن" if rfp_text else "لم تُحمَّل")
    with c4:
        sections_done = sum(1 for k in ["sec_methodology", "sec_plan", "sec_cover"] if st.session_state.get(k))
        st.metric("الأقسام المكتملة", f"{sections_done} / 3")

    st.divider()

    # Quick Workflow Guide
    st.markdown("### 🗺️ خطوات سير العمل")
    steps = [
        ("1", "⚙️ الإعدادات", "أدخل مفتاح Gemini API وبيانات الشركة.", "#3B82F6"),
        ("2", "🏢 ملف الشركة", "أدخل بيانات الشركة والقالب الرسمي.", "#8B5CF6"),
        ("3", "📥 رفع الكراسة", "ارفع ملفات RFP واستخرج النصوص.", "#10B981"),
        ("4", "🤖 التحليل الذكي", "شغّل تحليل Go/No-Go والأوزان والامتثال.", "#F59E0B"),
        ("5", "📄 بناء العرض", "أنشئ أقسام العرض الفني واستخرج الوثيقة.", "#EF4444"),
    ]
    cols = st.columns(5)
    for col, (num, title, desc, color) in zip(cols, steps):
        with col:
            st.markdown(f"""
            <div style="background:#fff;border:1px solid #E2E8F0;border-radius:12px;
                        padding:16px;text-align:center;border-top:3px solid {color};
                        font-family:Tajawal,sans-serif;">
                <div style="font-size:28px;font-weight:800;color:{color};">{num}</div>
                <div style="font-size:14px;font-weight:700;color:#1E293B;margin:6px 0;">{title}</div>
                <div style="font-size:12px;color:#64748B;">{desc}</div>
            </div>
            """, unsafe_allow_html=True)

    st.divider()

    # Feature Highlights
    st.markdown("### ✨ قدرات المنصة")
    f1, f2, f3 = st.columns(3)
    features = [
        ("🤖 تحليل ذكي شامل", "Go/No-Go · مصفوفة التقييم · فجوات الامتثال"),
        ("📄 منشئ الوثائق", "توليد الأقسام · حقن القوالب · تصدير Word"),
        ("📊 جداول تفاعلية", "Compliance Matrix · BOQ · تصدير CSV"),
    ]
    for col, (title, desc) in zip([f1, f2, f3], features):
        with col:
            st.markdown(f"""
            <div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;
                        padding:16px;font-family:Tajawal,sans-serif;">
                <div style="font-size:15px;font-weight:700;color:#1E293B;">{title}</div>
                <div style="font-size:13px;color:#64748B;margin-top:4px;">{desc}</div>
            </div>
            """, unsafe_allow_html=True)


# ── Workspace ─────────────────────────────────────────────────────────────────
elif nav == "🚀 مساحة العمل":
    st.title("🚀 مساحة العمل")

    from pages import analysis, tables, doc_builder

    tab1, tab2, tab3 = st.tabs([
        "📥 1. التحليل والمخاطر",
        "📊 2. المراجعة وجدول الكميات",
        "📄 3. منشئ العرض الفني",
    ])
    with tab1:
        analysis.render()
    with tab2:
        tables.render()
    with tab3:
        doc_builder.render()


# ── Company Profile ───────────────────────────────────────────────────────────
elif nav == "🏢 ملف الشركة":
    st.title("🏢 ملف الشركة")
    from pages import company
    company.render()


# ── Settings ─────────────────────────────────────────────────────────────────
elif nav == "⚙️ إعدادات النظام":
    st.title("⚙️ إعدادات النظام")
    from pages import settings
    settings.render_settings()


# ── Data Management ───────────────────────────────────────────────────────────
elif nav == "💾 إدارة البيانات":
    st.title("💾 إدارة البيانات")
    from pages import settings
    settings.render_data()
