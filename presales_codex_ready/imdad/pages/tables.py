"""
pages/tables.py — Tab 2: Compliance Matrix + BOQ Editor
"""
import streamlit as st
import pandas as pd
from utils.state import DEFAULT_COMPLIANCE_DF, DEFAULT_BOQ_DF
from components.ui import status_badge


def render():
    st.markdown("### 📊 جداول المراجعة والكميات")

    # ── Compliance Matrix ──────────────────────────────────────────────────────
    with st.expander("📋 جدول الامتثال بالمواصفات (Compliance Matrix)", expanded=True):
        col_info, col_reset = st.columns([4, 1])
        with col_info:
            df = st.session_state.get("df_compliance", DEFAULT_COMPLIANCE_DF.copy())
            total = len(df)
            compliant = (df.get("الالتزام", pd.Series()) == "نعم").sum() if "الالتزام" in df.columns else 0
            partial = (df.get("الالتزام", pd.Series()) == "جزئي").sum() if "الالتزام" in df.columns else 0
            non = total - compliant - partial if total > 0 else 0

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("إجمالي المتطلبات", total)
            c2.metric("✅ ملتزم", compliant)
            c3.metric("⚠️ جزئي", partial)
            c4.metric("❌ غير ملتزم", non)

        with col_reset:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("↩️ إعادة ضبط", key="reset_comp", use_container_width=True):
                st.session_state["df_compliance"] = DEFAULT_COMPLIANCE_DF.copy()
                st.rerun()

        edited_comp = st.data_editor(
            st.session_state["df_compliance"],
            num_rows="dynamic",
            use_container_width=True,
            key="de_compliance",
            column_config={
                "الالتزام": st.column_config.SelectboxColumn(
                    "الالتزام",
                    options=["نعم", "جزئي", "لا", "بانتظار التحقق"],
                    required=True,
                ),
                "المتطلب التقني": st.column_config.TextColumn("المتطلب التقني", width="large"),
                "التبرير / الملاحظة": st.column_config.TextColumn("التبرير / الملاحظة", width="large"),
                "الشهادة المطلوبة": st.column_config.TextColumn("الشهادة المطلوبة"),
            },
        )
        # Persist changes immediately
        st.session_state["df_compliance"] = edited_comp

    st.divider()

    # ── BOQ ───────────────────────────────────────────────────────────────────
    with st.expander("📦 جدول الكميات (Bill of Quantities — BOQ)", expanded=True):
        col_info2, col_actions = st.columns([3, 2])
        with col_actions:
            if st.button("↩️ إعادة ضبط الجدول", key="reset_boq", use_container_width=True):
                st.session_state["df_boq"] = DEFAULT_BOQ_DF.copy()
                st.rerun()

        edited_boq = st.data_editor(
            st.session_state.get("df_boq", DEFAULT_BOQ_DF.copy()),
            num_rows="dynamic",
            use_container_width=True,
            key="de_boq",
            column_config={
                "البند": st.column_config.TextColumn("البند / الخدمة", width="large"),
                "الوصف": st.column_config.TextColumn("الوصف التفصيلي", width="large"),
                "الكمية": st.column_config.NumberColumn("الكمية", min_value=0, step=1),
                "الوحدة": st.column_config.SelectboxColumn(
                    "الوحدة",
                    options=["شهر", "سنة", "قطعة", "ترخيص", "مستخدم", "نقطة", "مشروع", "أخرى"],
                ),
                "ملاحظات": st.column_config.TextColumn("ملاحظات"),
            },
        )
        st.session_state["df_boq"] = edited_boq

    # ── Export Tables ──────────────────────────────────────────────────────────
    st.divider()
    st.markdown("#### 📥 تصدير الجداول")
    col_e1, col_e2 = st.columns(2)

    with col_e1:
        if st.button("📥 تصدير Compliance Matrix (CSV)", use_container_width=True):
            csv = st.session_state["df_compliance"].to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                "⬇️ تحميل compliance_matrix.csv",
                data=csv.encode("utf-8-sig"),
                file_name="compliance_matrix.csv",
                mime="text/csv",
                key="dl_comp_csv",
            )

    with col_e2:
        if st.button("📥 تصدير BOQ (CSV)", use_container_width=True):
            csv = st.session_state["df_boq"].to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                "⬇️ تحميل boq.csv",
                data=csv.encode("utf-8-sig"),
                file_name="boq.csv",
                mime="text/csv",
                key="dl_boq_csv",
            )
