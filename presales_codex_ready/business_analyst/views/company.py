"""
views/company.py — ملف الشركة ومستودع المعرفة

ملف الشركة يُحفظ على القرص ويُشارَك بين كل المنافسات.
مستودع المعرفة يُفهرس مستندات الشركة ليستند إليها الذكاء الاصطناعي عند الصياغة.
"""
import streamlit as st

from utils import db, knowledge
from utils.file_handler import BRAND_COLOR, BRAND_FONT_AR
from utils.i18n import t
from utils.state import get_company_snapshot


def render():
    st.markdown(t("co.title"))

    # ── Legal Info ─────────────────────────────────────────────────────────────
    with st.expander(t("co.legal"), expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.session_state["c_name"] = st.text_input(
                t("co.name"),
                value=st.session_state.get("c_name", ""),
                placeholder="شركة الحلول التقنية المتقدمة",
            )
            st.session_state["c_cr"] = st.text_input(
                t("co.cr"),
                value=st.session_state.get("c_cr", ""),
                placeholder="1010XXXXXX",
            )
        with c2:
            st.session_state["c_vat"] = st.text_input(
                t("co.vat"),
                value=st.session_state.get("c_vat", ""),
                placeholder="3XXXXXXXXXXXXXXX3",
            )
            st.session_state["c_phone"] = st.text_input(
                t("co.phone"),
                value=st.session_state.get("c_phone", ""),
                placeholder="+966-11-XXXXXXX",
            )
        with c3:
            st.session_state["c_email"] = st.text_input(
                t("co.email"),
                value=st.session_state.get("c_email", ""),
                placeholder="bids@company.com.sa",
            )
            st.session_state["c_web"] = st.text_input(
                t("co.web"),
                value=st.session_state.get("c_web", ""),
                placeholder="https://www.company.com.sa",
            )
        st.session_state["c_address"] = st.text_input(
            t("co.address"),
            value=st.session_state.get("c_address", ""),
            placeholder="الرياض، المملكة العربية السعودية",
        )
        st.session_state["c_overview"] = st.text_area(
            t("co.overview"),
            value=st.session_state.get("c_overview", ""),
            height=120,
            placeholder="أدخل نبذة مختصرة عن الشركة: سنوات الخبرة، التخصصات، الشهادات...",
        )

        if st.session_state.get("c_name"):
            st.success(f"✅ الشركة: **{st.session_state['c_name']}**")
        else:
            st.warning(t("co.name_missing"))

    # ── Brand identity ────────────────────────────────────────────────────────
    with st.expander(t("co.brand"), expanded=False):
        st.caption(t("co.brand_hint"))
        b1, b2 = st.columns(2)
        with b1:
            st.session_state["c_brand_color"] = st.color_picker(
                t("co.brand_color"),
                value=st.session_state.get("c_brand_color") or f"#{BRAND_COLOR}",
            )
        with b2:
            st.session_state["c_doc_font"] = st.text_input(
                t("co.doc_font"),
                value=st.session_state.get("c_doc_font", ""),
                placeholder=BRAND_FONT_AR,
                help=t("co.doc_font_help"),
            )

    # ── Templates ─────────────────────────────────────────────────────────────
    with st.expander(t("co.templates"), expanded=False):
        st.session_state["c_cover_template"] = st.text_area(
            t("co.cover_template"),
            value=st.session_state.get("c_cover_template", ""),
            height=180,
            help="هذا النص يُستخدم تلقائياً في كل عرض فني. يمكن تخصيصه لكل عطاء من منشئ الوثائق.",
        )

    # ── Word Template Upload ───────────────────────────────────────────────────
    with st.expander(t("co.word_template"), expanded=False):
        st.markdown(t("co.word_template_hint"))
        uploaded_template = st.file_uploader(
            t("co.template_upload"), type=["docx"], key="template_upload",
        )
        if uploaded_template:
            data = uploaded_template.getvalue()
            if data != st.session_state.get("c_word_template_bytes"):
                st.session_state["c_word_template_bytes"] = data
                db.save_company(get_company_snapshot(), template=data)
                st.success(t("co.template_saved", name=uploaded_template.name))

        if st.session_state.get("c_word_template_bytes"):
            col_info, col_remove = st.columns([3, 1])
            with col_info:
                st.info(t("co.template_active"))
            with col_remove:
                if st.button(t("co.template_delete"), width="stretch"):
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
    st.markdown(t("co.kb"))
    stats = db.kb_stats()
    st.caption(t("co.kb_caption"))

    c1, c2 = st.columns(2)
    c1.metric(t("co.kb_docs"), stats.get("docs", 0))
    c2.metric(t("co.kb_chunks"), stats.get("chunks", 0))

    has_key = bool(st.session_state.get("api_gemini"))
    if not has_key:
        st.warning(t("co.kb_needs_key"))

    with st.expander(t("co.kb_add"), expanded=stats.get("docs", 0) == 0):
        category = st.selectbox(
            t("co.kb_type"),
            options=list(knowledge.CATEGORIES),
            format_func=lambda k: t(f"kbcat.{k}"),
        )
        files = st.file_uploader(
            t("an.formats"),
            accept_multiple_files=True,
            key="kb_upload",
        )
        if st.button(t("co.kb_index"), type="primary", disabled=not files or not has_key):
            progress = st.progress(0.0)
            added = 0
            for i, f in enumerate(files, start=1):
                progress.progress((i - 1) / len(files), text=f"فهرسة {f.name}…")
                count = knowledge.ingest_file(f, category)
                if count:
                    added += 1
                    st.success(t("co.kb_indexed", name=f.name, n=count))
            progress.empty()
            if added:
                st.rerun()

    documents = db.list_kb_documents()
    if not documents:
        return

    with st.expander(t("co.kb_list", n=len(documents)), expanded=False):
        for doc in documents:
            c_info, c_del = st.columns([6, 1])
            with c_info:
                st.markdown(
                    f"**{doc['name']}**<br>"
                    f"<span style='color:#64748B;font-size:12px'>"
                    f"{t('kbcat.' + doc['category'])} · "
                    f"{doc['chunks']} {t('co.kb_chunk_unit')} · "
                    f"{doc['char_count']:,} {t('co.kb_char_unit')} · {doc['added_at']}"
                    f"</span>",
                    unsafe_allow_html=True,
                )
            with c_del:
                if st.button("🗑️", key=f"kbdel_{doc['id']}", width="stretch"):
                    db.delete_kb_document(doc["id"])
                    st.rerun()

    with st.expander(t("co.kb_try"), expanded=False):
        query = st.text_input(
            t("co.kb_query"), placeholder="…"
        )
        if query and has_key:
            hits = knowledge.search(query)
            if not hits:
                st.info(t("co.kb_no_hits"))
            for h in hits:
                st.markdown(f"**{h['doc_name']}** · {t('co.kb_similarity')} {h['score']:.2f}")
                st.caption(h["text"][:400] + ("…" if len(h["text"]) > 400 else ""))
