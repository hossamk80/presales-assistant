"""
pages/company.py — Company Profile Management
"""
import streamlit as st


def render():
    st.markdown("### 🏢 ملف الشركة (Company Profile)")

    # ── Legal Info ─────────────────────────────────────────────────────────────
    with st.expander("📋 البيانات الأساسية والقانونية", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.session_state["c_name"] = st.text_input(
                "اسم الشركة *",
                value=st.session_state.get("c_name", ""),
                placeholder="شركة الإمداد للحلول التقنية",
            )
            st.session_state["c_cr"] = st.text_input(
                "رقم السجل التجاري",
                value=st.session_state.get("c_cr", ""),
                placeholder="1010XXXXXX",
            )
        with c2:
            st.session_state["c_vat"] = st.text_input(
                "الرقم الضريبي",
                value=st.session_state.get("c_vat", ""),
                placeholder="3XXXXXXXXXXXXXXX3",
            )
            st.session_state["c_phone"] = st.text_input(
                "الهاتف",
                value=st.session_state.get("c_phone", ""),
                placeholder="+966-11-XXXXXXX",
            )
        with c3:
            st.session_state["c_email"] = st.text_input(
                "البريد الإلكتروني",
                value=st.session_state.get("c_email", ""),
                placeholder="bids@company.com.sa",
            )
            st.session_state["c_web"] = st.text_input(
                "الموقع الإلكتروني",
                value=st.session_state.get("c_web", ""),
                placeholder="https://www.company.com.sa",
            )
        st.session_state["c_address"] = st.text_input(
            "العنوان",
            value=st.session_state.get("c_address", ""),
            placeholder="الرياض، المملكة العربية السعودية",
        )
        st.session_state["c_overview"] = st.text_area(
            "نبذة عن الشركة (يستخدمها الذكاء الاصطناعي للتخصيص)",
            value=st.session_state.get("c_overview", ""),
            height=120,
            placeholder="أدخل نبذة مختصرة عن الشركة: سنوات الخبرة، التخصصات، الشهادات...",
        )

        if st.session_state.get("c_name"):
            st.success(f"✅ الشركة: **{st.session_state['c_name']}**")
        else:
            st.warning("⚠️ أدخل اسم الشركة — سيُستخدم في جميع وثائق العرض الفني.")

    # ── Templates ─────────────────────────────────────────────────────────────
    with st.expander("📝 قوالب الصياغة", expanded=False):
        st.session_state["c_cover_template"] = st.text_area(
            "قالب خطاب التقديم الثابت",
            value=st.session_state.get("c_cover_template", ""),
            height=180,
            help="هذا النص يُستخدم تلقائياً في كل عرض فني. يمكن تخصيصه لكل عطاء من منشئ الوثائق.",
        )

    # ── Word Template Upload ───────────────────────────────────────────────────
    with st.expander("📄 قالب Word المخصص (اختياري)", expanded=False):
        st.markdown("""
        ارفع ملف Word يحتوي على هوية شركتك (ترويسة، تذييل، غلاف).  
        سيتم **حقن محتوى العرض الفني** داخله تلقائياً بدلاً من ملف فارغ.
        """)
        uploaded_template = st.file_uploader(
            "ارفع القالب (صيغة .docx)",
            type=["docx"],
            key="template_upload",
        )
        if uploaded_template:
            st.session_state["c_word_template_bytes"] = uploaded_template.getvalue()
            st.success(f"✅ تم رفع القالب: **{uploaded_template.name}** ({len(st.session_state['c_word_template_bytes']) // 1024} KB)")

        if st.session_state.get("c_word_template_bytes"):
            col_info, col_remove = st.columns([3, 1])
            with col_info:
                st.info("✅ قالب الشركة محفوظ ومفعّل.")
            with col_remove:
                if st.button("🗑️ حذف القالب", width="stretch"):
                    st.session_state["c_word_template_bytes"] = None
                    st.rerun()

    # ── Knowledge Base ─────────────────────────────────────────────────────────
    with st.expander("🗂️ مستودع المعرفة (للمراجعة فقط — لا يُعالَج بعد)", expanded=False):
        st.caption("قريباً: تغذية الذكاء الاصطناعي بالسير الذاتية والشهادات وملفات الخبرات السابقة.")
        c1, c2 = st.columns(2)
        with c1:
            st.file_uploader("السير الذاتية للفريق (PDF, Word)", accept_multiple_files=True, key="cv_upload")
        with c2:
            st.file_uploader("الشهادات والاعتمادات", accept_multiple_files=True, key="certs_upload")
        col_logo, col_cr = st.columns(2)
        with col_logo:
            st.file_uploader("شعار الشركة (PNG/JPG)", type=["png", "jpg", "jpeg"], key="logo_upload")
        with col_cr:
            st.file_uploader("السجل التجاري (PDF/صورة)", type=["pdf", "png", "jpg"], key="cr_upload")
