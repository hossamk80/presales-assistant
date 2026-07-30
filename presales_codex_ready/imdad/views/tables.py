"""
views/tables.py — Tab 2: Compliance Matrix + BOQ Editor

الجداول تُملأ آلياً من الكراسة عبر استخراج مُهيكل (JSON)، وتبقى قابلة للتحرير.
"""
import streamlit as st
import pandas as pd
from utils.state import DEFAULT_COMPLIANCE_DF, DEFAULT_BOQ_DF
from utils.ai_engine import (
    BOQ_SCHEMA,
    COMPLIANCE_SCHEMA,
    DEFAULT_MODEL,
    EXTRACT_PROMPTS,
    MODEL_NAMES,
    ai_generate_json,
)
from components.ui import status_badge

BOQ_UNITS = ["شهر", "سنة", "قطعة", "ترخيص", "مستخدم", "نقطة", "مشروع", "أخرى"]


def _model_picker(key: str) -> str:
    """منتقي نموذج مضغوط يتبع التفضيل الافتراضي."""
    current = st.session_state.get("ai_model_preference", DEFAULT_MODEL)
    return st.selectbox(
        "المحرك:",
        MODEL_NAMES,
        index=MODEL_NAMES.index(current) if current in MODEL_NAMES else 0,
        key=key,
        label_visibility="collapsed",
    )


def _compliance_to_df(items: list) -> pd.DataFrame:
    """تحويل المتطلبات المستخرجة إلى شكل جدول الامتثال."""
    rows = []
    for it in items:
        mandatory = bool(it.get("mandatory"))
        category = it.get("category", "فني")
        req = str(it.get("requirement", "")).strip()
        if not req:
            continue
        ref = str(it.get("source_ref", "")).strip()
        note_bits = [f"التصنيف: {category}"]
        if mandatory:
            note_bits.append("⛔ شرط استبعاد")
        if ref:
            note_bits.append(f"المرجع: {ref}")
        rows.append({
            "المتطلب التقني": req,
            # الالتزام قرار بشري — يبدأ دائماً بانتظار التحقق ولا يفترضه النموذج
            "الالتزام": "بانتظار التحقق",
            "التبرير / الملاحظة": " · ".join(note_bits),
            "الشهادة المطلوبة": str(it.get("certificate", "")).strip(),
        })
    return pd.DataFrame(rows) if rows else DEFAULT_COMPLIANCE_DF.copy()


def _boq_to_df(items: list) -> pd.DataFrame:
    """تحويل البنود المستخرجة إلى شكل جدول الكميات."""
    rows = []
    for it in items:
        name = str(it.get("item", "")).strip()
        if not name:
            continue
        try:
            qty = float(it.get("quantity", 1) or 1)
        except (TypeError, ValueError):
            qty = 1.0
        unit = str(it.get("unit", "")).strip()
        rows.append({
            "البند": name,
            "الوصف": str(it.get("description", "")).strip(),
            "الكمية": int(qty) if qty == int(qty) else qty,
            "الوحدة": unit if unit in BOQ_UNITS else "أخرى",
            "ملاحظات": str(it.get("notes", "")).strip(),
        })
    return pd.DataFrame(rows) if rows else DEFAULT_BOQ_DF.copy()


def _extraction_bar(kind: str):
    """
    شريط الاستخراج الآلي فوق كل جدول.
    kind: "compliance" أو "boq"
    """
    rfp = st.session_state.get("rfp_raw_text", "")
    if not rfp:
        st.info("💡 ارفع كراسة الشروط في التبويب الأول لتفعيل التعبئة الآلية لهذا الجدول.")
        return

    is_comp = kind == "compliance"
    label = "استخراج المتطلبات من الكراسة" if is_comp else "استخراج بنود الكميات من الكراسة"

    col_model, col_btn = st.columns([3, 2])
    with col_model:
        model = _model_picker(f"model_extract_{kind}")
    with col_btn:
        clicked = st.button(f"🤖 {label}", key=f"btn_extract_{kind}", type="primary", width="stretch")

    if not clicked:
        return

    status = st.empty()
    with st.spinner("جاري الاستخراج..."):
        result = ai_generate_json(
            EXTRACT_PROMPTS["compliance_items" if is_comp else "boq_items"],
            schema=COMPLIANCE_SCHEMA if is_comp else BOQ_SCHEMA,
            model_choice=model,
            rfp_context=rfp,
            merge_key="requirements" if is_comp else "items",
            on_progress=lambda m: status.caption(f"⏳ {m}"),
        )
    status.empty()

    if not result:
        return

    items = result.get("requirements" if is_comp else "items", []) if isinstance(result, dict) else result
    if not items:
        st.warning("⚠️ لم يعثر النموذج على بنود قابلة للاستخراج في الكراسة.")
        return

    df = _compliance_to_df(items) if is_comp else _boq_to_df(items)
    st.session_state["df_compliance" if is_comp else "df_boq"] = df
    # data_editor يحتفظ بتعديلات المستخدم السابقة تحت مفتاحه، فنُبطلها
    # حتى يعرض الجدول البيانات المستخرجة الجديدة بدل القديمة
    st.session_state.pop("de_compliance" if is_comp else "de_boq", None)
    st.success(f"✅ تم استخراج **{len(df)}** بند. راجعها وعدّلها قبل الاعتماد.")
    st.rerun()


def render():
    st.markdown("### 📊 جداول المراجعة والكميات")

    # ── Compliance Matrix ──────────────────────────────────────────────────────
    with st.expander("📋 جدول الامتثال بالمواصفات (Compliance Matrix)", expanded=True):
        _extraction_bar("compliance")
        st.divider()

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
            if st.button("↩️ إعادة ضبط", key="reset_comp", width="stretch"):
                st.session_state["df_compliance"] = DEFAULT_COMPLIANCE_DF.copy()
                st.rerun()

        edited_comp = st.data_editor(
            st.session_state["df_compliance"],
            num_rows="dynamic",
            width="stretch",
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
        _extraction_bar("boq")
        st.divider()

        col_info2, col_actions = st.columns([3, 2])
        with col_actions:
            if st.button("↩️ إعادة ضبط الجدول", key="reset_boq", width="stretch"):
                st.session_state["df_boq"] = DEFAULT_BOQ_DF.copy()
                st.rerun()

        edited_boq = st.data_editor(
            st.session_state.get("df_boq", DEFAULT_BOQ_DF.copy()),
            num_rows="dynamic",
            width="stretch",
            key="de_boq",
            column_config={
                "البند": st.column_config.TextColumn("البند / الخدمة", width="large"),
                "الوصف": st.column_config.TextColumn("الوصف التفصيلي", width="large"),
                "الكمية": st.column_config.NumberColumn("الكمية", min_value=0, step=1),
                "الوحدة": st.column_config.SelectboxColumn("الوحدة", options=BOQ_UNITS),
                "ملاحظات": st.column_config.TextColumn("ملاحظات"),
            },
        )
        st.session_state["df_boq"] = edited_boq

    # ── Export Tables ──────────────────────────────────────────────────────────
    st.divider()
    st.markdown("#### 📥 تصدير الجداول")
    col_e1, col_e2 = st.columns(2)

    with col_e1:
        if st.button("📥 تصدير Compliance Matrix (CSV)", width="stretch"):
            csv = st.session_state["df_compliance"].to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                "⬇️ تحميل compliance_matrix.csv",
                data=csv.encode("utf-8-sig"),
                file_name="compliance_matrix.csv",
                mime="text/csv",
                key="dl_comp_csv",
            )

    with col_e2:
        if st.button("📥 تصدير BOQ (CSV)", width="stretch"):
            csv = st.session_state["df_boq"].to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                "⬇️ تحميل boq.csv",
                data=csv.encode("utf-8-sig"),
                file_name="boq.csv",
                mime="text/csv",
                key="dl_boq_csv",
            )
