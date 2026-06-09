"""
pages/analysis.py — Tab 1: RFP Upload + AI Analysis
"""
import streamlit as st
from utils.ai_engine import ai_generate, estimate_tokens, PROMPTS
from utils.file_handler import extract_text_from_files
from components.ui import ai_generate_button


def render():
    # ── RFP Upload ─────────────────────────────────────────────────────────────
    st.markdown("### 📥 رفع ملفات كراسة الشروط")

    col_upload, col_clear = st.columns([4, 1])
    with col_upload:
        files = st.file_uploader(
            "يدعم: PDF · Word · Excel · CSV · TXT · HTML",
            accept_multiple_files=True,
            label_visibility="collapsed",
        )
    with col_clear:
        if st.session_state.get("rfp_raw_text") and st.button("🗑️ مسح", width="stretch"):
            from utils.state import reset_analysis
            reset_analysis()
            st.rerun()

    col_extract, col_status = st.columns([2, 3])
    with col_extract:
        if st.button("📂 استخراج النصوص", type="primary", width="stretch", disabled=not files):
            with st.spinner("جاري الاستخراج..."):
                text, names = extract_text_from_files(files)
                if text:
                    st.session_state["rfp_raw_text"] = text
                    st.session_state["rfp_file_names"] = names
                    st.rerun()
                else:
                    st.error("❌ لم يتم استخراج أي نص. تأكد من الملفات المرفوعة.")

    with col_status:
        if st.session_state.get("rfp_raw_text"):
            tokens = estimate_tokens(st.session_state["rfp_raw_text"])
            names = st.session_state.get("rfp_file_names", [])
            st.success(
                f"✅ **{len(names)} ملف** · تقدير التوكنز: **{tokens:,}**"
                + (f" · {', '.join(names[:3])}{'...' if len(names) > 3 else ''}" if names else "")
            )

    if not st.session_state.get("rfp_raw_text"):
        st.info("ارفع ملفات كراسة الشروط واضغط **استخراج النصوص** للبدء.")
        return

    st.divider()

    # ── Section 1: Go/No-Go ────────────────────────────────────────────────────
    with st.expander("1️⃣ قرار الملاءمة والجدوى (Go / No-Go)", expanded=True):
        ai_generate_button(
            label="توليد تقرير Go/No-Go",
            key="gonogo",
            model_key="m1",
            on_generate=lambda model: ai_generate(
                PROMPTS["gonogo"],
                model_choice=model,
                rfp_context=st.session_state["rfp_raw_text"],
            ),
            result_state_key="analysis_gonogo",
            summary_state_key="sum_gonogo",
            summary_label="✍️ قرار المهندس المعتمد (يُمرَّر للـ AI لاحقاً):",
            result_style="info",
        )

    # ── Section 2: Evaluation Matrix ──────────────────────────────────────────
    with st.expander("2️⃣ مصفوفة معايير التقييم والأوزان"):
        ai_generate_button(
            label="استخراج الأوزان",
            key="eval",
            model_key="m2",
            on_generate=lambda model: ai_generate(
                PROMPTS["eval_matrix"],
                model_choice=model,
                rfp_context=st.session_state["rfp_raw_text"],
            ),
            result_state_key="evaluation_matrix",
            summary_state_key="sum_eval",
            summary_label="✍️ الأوزان المعتمدة (توجيه لكتابة المنهجية):",
            result_style="success",
        )

    # ── Section 3: Compliance Check ───────────────────────────────────────────
    with st.expander("3️⃣ الشروط الحاكمة وفجوات الامتثال"):
        ai_generate_button(
            label="فحص الشروط الإلزامية",
            key="compliance",
            model_key="m3",
            on_generate=lambda model: ai_generate(
                PROMPTS["compliance"],
                model_choice=model,
                rfp_context=st.session_state["rfp_raw_text"],
            ),
            result_state_key="compliance_check",
            summary_state_key="sum_comp",
            summary_label="✍️ الشهادات والفجوات المعتمدة للمعالجة:",
            result_style="warning",
        )

    # ── Raw Text Preview ───────────────────────────────────────────────────────
    with st.expander("👁️ معاينة النص المستخرج من الكراسة"):
        raw = st.session_state["rfp_raw_text"]
        st.code(raw[:5000] + ("\n\n... [تم الاختصار]" if len(raw) > 5000 else ""), language=None)
