"""
views/company.py — ملف الشركة ومستودع المعرفة

ملف الشركة يُحفظ على القرص ويُشارَك بين كل المنافسات.
مستودع المعرفة يُفهرس مستندات الشركة ليستند إليها الذكاء الاصطناعي عند الصياغة.
"""
import streamlit as st

from utils import db, knowledge
from utils.state import get_company_snapshot


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
            "ارفع القالب (صيغة .docx)", type=["docx"], key="template_upload",
        )
        if uploaded_template:
            data = uploaded_template.getvalue()
            if data != st.session_state.get("c_word_template_bytes"):
                st.session_state["c_word_template_bytes"] = data
                db.save_company(get_company_snapshot(), template=data)
                st.success(
                    f"✅ حُفظ القالب: **{uploaded_template.name}** ({len(data) // 1024} KB)"
                )

        if st.session_state.get("c_word_template_bytes"):
            col_info, col_remove = st.columns([3, 1])
            with col_info:
                st.info("✅ قالب الشركة محفوظ ومفعّل.")
            with col_remove:
                if st.button("🗑️ حذف القالب", width="stretch"):
                    st.session_state["c_word_template_bytes"] = None
                    db.clear_company_template()
                    st.rerun()

    st.divider()
    _render_knowledge_base()

    # حفظ ملف الشركة على القرص عند تغيّره
    snapshot = get_company_snapshot()
    if snapshot != st.session_state.get("_company_saved"):
        db.save_company(snapshot)
        st.session_state["_company_saved"] = snapshot


# ─── مستودع المعرفة ───────────────────────────────────────────────────────────


def _render_knowledge_base():
    st.markdown("### 🗂️ مستودع المعرفة")
    stats = db.kb_stats()
    st.caption(
        "مستندات شركتك الحقيقية — سير ذاتية وشهادات ومشاريع سابقة. تُفهرس هنا "
        "ويسترجع منها المساعد ما يخص كل قسم أثناء الصياغة، فيستند العرض إلى "
        "خبراتك الفعلية بدل محتوى عام."
    )

    c1, c2 = st.columns(2)
    c1.metric("المستندات المفهرسة", stats.get("docs", 0))
    c2.metric("المقاطع القابلة للاسترجاع", stats.get("chunks", 0))

    has_key = bool(st.session_state.get("api_gemini"))
    if not has_key:
        st.warning(
            "⚠️ الفهرسة تحتاج مفتاح Gemini API — أدخله في **إعدادات النظام** أولاً."
        )

    with st.expander("📤 إضافة مستندات للمستودع", expanded=stats.get("docs", 0) == 0):
        category = st.selectbox(
            "نوع المستندات:",
            options=list(knowledge.CATEGORIES),
            format_func=lambda k: knowledge.CATEGORIES[k],
        )
        files = st.file_uploader(
            "يدعم: PDF · Word · Excel · CSV · TXT · HTML",
            accept_multiple_files=True,
            key="kb_upload",
        )
        if st.button("🔎 فهرسة المستندات", type="primary", disabled=not files or not has_key):
            progress = st.progress(0.0)
            added = 0
            for i, f in enumerate(files, start=1):
                progress.progress((i - 1) / len(files), text=f"فهرسة {f.name}…")
                count = knowledge.ingest_file(f, category)
                if count:
                    added += 1
                    st.success(f"✅ `{f.name}` — {count} مقطع.")
            progress.empty()
            if added:
                st.rerun()

    documents = db.list_kb_documents()
    if not documents:
        return

    with st.expander(f"📚 المستندات المفهرسة ({len(documents)})", expanded=False):
        for doc in documents:
            c_info, c_del = st.columns([6, 1])
            with c_info:
                st.markdown(
                    f"**{doc['name']}**<br>"
                    f"<span style='color:#64748B;font-size:12px'>"
                    f"{knowledge.CATEGORIES.get(doc['category'], doc['category'])} · "
                    f"{doc['chunks']} مقطع · {doc['char_count']:,} حرف · {doc['added_at']}"
                    f"</span>",
                    unsafe_allow_html=True,
                )
            with c_del:
                if st.button("🗑️", key=f"kbdel_{doc['id']}", width="stretch"):
                    db.delete_kb_document(doc["id"])
                    st.rerun()

    with st.expander("🔍 جرّب الاسترجاع", expanded=False):
        query = st.text_input(
            "استعلام تجريبي", placeholder="خبرتنا في مشاريع الأمن السيبراني"
        )
        if query and has_key:
            hits = knowledge.search(query)
            if not hits:
                st.info("لا توجد مقاطع ذات صلة كافية بهذا الاستعلام.")
            for h in hits:
                st.markdown(f"**{h['doc_name']}** · تشابه {h['score']:.2f}")
                st.caption(h["text"][:400] + ("…" if len(h["text"]) > 400 else ""))
