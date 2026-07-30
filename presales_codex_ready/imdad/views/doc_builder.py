"""
pages/doc_builder.py — Tab 3: Document Builder + Export
Bug fixes:
  - cover_type NameError: defined before use, scoped correctly
  - placeholder detection improved with regex
  - export button correctly scoped
"""
import streamlit as st
import re
from utils.ai_engine import ai_generate, PROMPTS
from utils.file_handler import build_word_document
from components.ui import ai_generate_button, placeholder_warning


def _has_placeholders(*texts) -> bool:
    pattern = re.compile(r'\[.+?\]')
    return any(pattern.search(str(t)) for t in texts)


def render():
    st.markdown("### 📄 منشئ العرض الفني")

    # ── Section Selector ───────────────────────────────────────────────────────
    with st.expander("🗂️ اختر أقسام العرض الفني", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**الأقسام الافتتاحية**")
            inc_cover = st.checkbox("خطاب التقديم (Cover Letter)", value=True, key="inc_cover")
            inc_docinfo = st.checkbox("معلومات المستند وإشعار السرية", value=True, key="inc_docinfo")
            inc_exec = st.checkbox("الملخص التنفيذي", value=False, key="inc_exec")
        with c2:
            st.markdown("**المحتوى الفني**")
            inc_scope = st.checkbox("فهم النطاق", value=False, key="inc_scope")
            inc_meth = st.checkbox("المنهجية والحل المقترح ⭐", value=True, key="inc_meth")
            inc_gov = st.checkbox("حوكمة المشروع والـ SLAs", value=False, key="inc_gov")
            inc_plan = st.checkbox("خطة المشروع", value=True, key="inc_plan")
            inc_team = st.checkbox("هيكلة الفريق", value=False, key="inc_team")
            inc_ext = st.checkbox("المتطلبات الخارجية والضمانات", value=False, key="inc_ext")

        c3, c4 = st.columns(2)
        with c3:
            inc_comp_table = st.checkbox("جدول الامتثال (من التبويب 2)", value=True, key="inc_comp_table")
        with c4:
            inc_boq_table = st.checkbox("جدول الكميات BOQ (من التبويب 2)", value=False, key="inc_boq_table")

    st.divider()
    st.markdown("### ✍️ محررات الأقسام")

    # ── Cover Letter ──────────────────────────────────────────────────────────
    if inc_cover:
        with st.expander("📝 خطاب التقديم", expanded=False):
            # FIX: cover_type defined here, in scope for export
            cover_use_template = st.radio(
                "طريقة الإعداد:",
                ["قالب ثابت (من ملف الشركة)", "توليد ديناميكي (AI)"],
                key="cover_type_radio",
            )
            st.session_state["sec_cover_use_template"] = (cover_use_template == "قالب ثابت (من ملف الشركة)")

            if not st.session_state["sec_cover_use_template"]:
                ai_generate_button(
                    label="توليد الخطاب",
                    key="cover",
                    model_key="m_cover",
                    on_generate=lambda model: ai_generate(
                        f"اكتب خطاب تقديم احترافي لشركة {st.session_state['c_name']} للتقدم لعطاء حكومي. باللغة العربية.",
                        model_choice=model,
                    ),
                    result_state_key="sec_cover",
                    summary_state_key=None,
                )
            else:
                st.info(f"سيُستخدم القالب المحفوظ في **ملف الشركة**:\n\n{st.session_state.get('c_cover_template', '')[:200]}...")

    # ── Executive Summary ─────────────────────────────────────────────────────
    if inc_exec:
        with st.expander("📌 الملخص التنفيذي"):
            ai_generate_button(
                label="توليد الملخص التنفيذي",
                key="exec_sum",
                model_key="m_exec",
                on_generate=lambda model: ai_generate(
                    f"اكتب ملخصاً تنفيذياً احترافياً لشركة {st.session_state['c_name']}. سياق: {st.session_state.get('sum_gonogo', '')}",
                    model_choice=model,
                ),
                result_state_key="sec_exec",
                summary_state_key=None,
                height=200,
            )

    # ── Scope ─────────────────────────────────────────────────────────────────
    if inc_scope:
        with st.expander("🔍 فهم النطاق"):
            ai_generate_button(
                label="توليد فهم النطاق",
                key="scope",
                model_key="m_scope",
                on_generate=lambda model, report: ai_generate(
                    PROMPTS["scope"],
                    model_choice=model,
                    rfp_context=st.session_state.get("rfp_raw_text", ""),
                    on_progress=report,
                ),
                result_state_key="sec_scope",
                summary_state_key=None,
                height=200,
            )

    # ── Methodology ──────────────────────────────────────────────────────────
    if inc_meth:
        with st.expander("🛠️ المنهجية الفنية والحل المقترح ⭐"):
            st.caption("يستخدم الأوزان والشروط المعتمدة من التبويب 1 تلقائياً.")
            ai_generate_button(
                label="توليد المنهجية",
                key="methodology",
                model_key="m_meth",
                on_generate=lambda model, report: ai_generate(
                    PROMPTS["methodology"].format(
                        company_overview=st.session_state.get("c_overview") or st.session_state.get("c_name", ""),
                        eval_weights=st.session_state.get("sum_eval", "غير محدد"),
                        compliance_summary=st.session_state.get("sum_comp", "غير محدد"),
                    ),
                    model_choice=model,
                    rfp_context=st.session_state.get("rfp_raw_text", ""),
                    on_progress=report,
                ),
                result_state_key="sec_methodology",
                summary_state_key=None,
                height=300,
            )

    # ── Governance ────────────────────────────────────────────────────────────
    if inc_gov:
        with st.expander("⚙️ حوكمة المشروع والـ SLAs"):
            ai_generate_button(
                label="توليد الحوكمة",
                key="gov",
                model_key="m_gov",
                on_generate=lambda model: ai_generate(
                    "اكتب قسم حوكمة مشروع تقنية معلومات حكومي يشمل هيكل الإشراف، آليات التصعيد، ومستويات الخدمة SLAs. باللغة العربية.",
                    model_choice=model,
                ),
                result_state_key="sec_gov",
                summary_state_key=None,
                height=200,
            )

    # ── Project Plan ─────────────────────────────────────────────────────────
    if inc_plan:
        with st.expander("📅 خطة المشروع والجدول الزمني"):
            ai_generate_button(
                label="توليد خطة المشروع",
                key="plan",
                model_key="m_plan",
                on_generate=lambda model: ai_generate(
                    PROMPTS["project_plan"].format(
                        company_name=st.session_state.get("c_name", "الشركة"),
                        project_context=st.session_state.get("sum_gonogo", ""),
                    ),
                    model_choice=model,
                ),
                result_state_key="sec_plan",
                summary_state_key=None,
                height=200,
            )

    # ── Team ─────────────────────────────────────────────────────────────────
    if inc_team:
        with st.expander("👥 هيكلة الفريق والسير الذاتية"):
            ai_generate_button(
                label="توليد هيكلة الفريق",
                key="team",
                model_key="m_team",
                on_generate=lambda model: ai_generate(
                    f"اكتب قسم هيكلة الفريق لمشروع تقنية معلومات لشركة {st.session_state.get('c_name', '')}. باللغة العربية.",
                    model_choice=model,
                ),
                result_state_key="sec_team",
                summary_state_key=None,
                height=200,
            )

    # ── External Requirements ─────────────────────────────────────────────────
    if inc_ext:
        with st.expander("📎 المتطلبات الخارجية والضمانات"):
            ai_generate_button(
                label="توليد المتطلبات الخارجية",
                key="ext",
                model_key="m_ext",
                on_generate=lambda model: ai_generate(
                    "اكتب قسم المتطلبات الخارجية والضمانات لعرض فني حكومي سعودي. باللغة العربية.",
                    model_choice=model,
                ),
                result_state_key="sec_external",
                summary_state_key=None,
                height=200,
            )

    # ── Export Section ────────────────────────────────────────────────────────
    st.divider()
    st.markdown("### 📥 مراجعة وتصدير العرض الفني")

    # Gather all content for validation
    content_to_check = " ".join(filter(None, [
        st.session_state.get("sec_cover", ""),
        st.session_state.get("sec_exec", ""),
        st.session_state.get("sec_scope", ""),
        st.session_state.get("sec_methodology", ""),
        st.session_state.get("sec_gov", ""),
        st.session_state.get("sec_plan", ""),
        st.session_state.get("sec_team", ""),
        st.session_state.get("sec_external", ""),
    ]))

    has_placeholders = _has_placeholders(content_to_check)

    # Completeness Check
    col_checks = st.columns(4)
    checks = {
        "ملف الشركة": bool(st.session_state.get("c_name")),
        "تحليل الكراسة": bool(st.session_state.get("rfp_raw_text")),
        "المنهجية": bool(st.session_state.get("sec_methodology")),
        "لا يوجد نص ناقص": not has_placeholders,
    }
    for col, (label, ok) in zip(col_checks, checks.items()):
        col.metric(label, "✅" if ok else "❌")

    if has_placeholders:
        st.error("🚨 يوجد نص بين أقواس [ ] يحتاج تعبئة يدوية. راجع الأقسام أعلاه قبل التصدير.")

    if st.session_state.get("c_word_template_bytes"):
        st.success("✅ سيتم الحقن داخل قالب الشركة الرسمي.")
    else:
        st.info("💡 لا يوجد قالب مخصص. سيُصدَّر كمستند وورد قياسي. (أضف قالباً في **ملف الشركة**).")

    col_export, col_spacer = st.columns([2, 3])
    with col_export:
        export_clicked = st.button(
            "📥 بناء وتصدير العرض الفني (Word)",
            type="primary",
            width="stretch",
            disabled=has_placeholders,
        )

    if export_clicked:
        with st.spinner("جاري بناء المستند..."):
            try:
                bio = build_word_document(
                    company_name=st.session_state.get("c_name", ""),
                    sections={
                        "cover": st.session_state.get("sec_cover", ""),
                        "cover_use_template": st.session_state.get("sec_cover_use_template", True),
                        "exec": st.session_state.get("sec_exec", ""),
                        "scope": st.session_state.get("sec_scope", ""),
                        "methodology": st.session_state.get("sec_methodology", ""),
                        "gov": st.session_state.get("sec_gov", ""),
                        "plan": st.session_state.get("sec_plan", ""),
                        "team": st.session_state.get("sec_team", ""),
                        "external": st.session_state.get("sec_external", ""),
                    },
                    template_bytes=st.session_state.get("c_word_template_bytes"),
                    include_flags={
                        "cover": inc_cover,
                        "docinfo": inc_docinfo,
                        "exec": inc_exec,
                        "scope": inc_scope,
                        "methodology": inc_meth,
                        "gov": inc_gov,
                        "plan": inc_plan,
                        "team": inc_team,
                        "external": inc_ext,
                        "compliance_table": inc_comp_table,
                        "boq_table": inc_boq_table,
                    },
                    cover_template_text=st.session_state.get("c_cover_template", ""),
                    df_compliance=st.session_state.get("df_compliance"),
                    df_boq=st.session_state.get("df_boq"),
                )

                company_slug = (st.session_state.get("c_name") or "Proposal").replace(" ", "_")[:20]
                filename = f"Technical_Proposal_{company_slug}.docx"

                st.success("✅ تم بناء المستند بنجاح!")
                st.download_button(
                    "⬇️ تحميل العرض الفني النهائي",
                    data=bio.getvalue(),
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="dl_final_doc",
                )
            except Exception as e:
                st.error(f"❌ فشل بناء المستند: {e}")
                import traceback
                st.code(traceback.format_exc())
