"""
views/tables.py — Tab 2: Compliance Matrix + BOQ Editor

الجداول تُملأ آلياً من الكراسة عبر استخراج مُهيكل (JSON)، وتبقى قابلة للتحرير.
"""
import streamlit as st
import pandas as pd
from utils.state import (
    BOQ_COLUMNS,
    DEFAULT_BOQ_DF,
    DEFAULT_COMPLIANCE_DF,
    migrate_boq_df,
    role_text,
)
from utils.ai_engine import (
    BOQ_SCHEMA,
    COMPLIANCE_SCHEMA,
    DEFAULT_MODEL,
    EXTRACT_PROMPTS,
    MODEL_NAMES,
    ai_generate_json,
)
from components.ui import status_badge


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
    """
    تحويل البنود المستخرجة إلى شكل جدول الكميات الموسّع.

    الوحدة تُترك كما وردت في المصدر ولا تُجبَر على قائمة مغلقة — جداول
    الكميات الحكومية تستخدم وحدات متنوعة، وإجبارها على "أخرى" يُفقد معلومة
    لازمة للتسعير.
    """
    rows = []
    for i, it in enumerate(items, start=1):
        name = str(it.get("item_name", "")).strip()
        if not name:
            continue
        try:
            qty = float(it.get("quantity", 1) or 1)
        except (TypeError, ValueError):
            qty = 1.0
        rows.append({
            "رقم البند": str(it.get("item_number", "") or i).strip(),
            "التصنيف": str(it.get("category", "")).strip(),
            "البند": name,
            "الوحدة": str(it.get("unit", "")).strip(),
            "الوصف": str(it.get("description", "")).strip(),
            "المواصفات": str(it.get("specifications", "")).strip(),
            "كود البناء": str(it.get("construction_code", "")).strip(),
            "الكمية": int(qty) if qty == int(qty) else qty,
            "القائمة الإلزامية": bool(it.get("mandatory_list_flag")),
        })
    return pd.DataFrame(rows)[BOQ_COLUMNS] if rows else DEFAULT_BOQ_DF.copy()


def _mandatory_list_reference() -> str:
    """
    يسترجع القائمة الإلزامية للمحتوى المحلي من مستودع المعرفة إن رُفعت.

    بدونها يبقى ترشيح mandatory_list_flag اجتهاداً من النموذج، وهو ما يُحذّر
    منه في الواجهة صراحةً.
    """
    from utils import knowledge

    if not knowledge.is_populated() or not st.session_state.get("api_gemini"):
        return ""
    return knowledge.build_context(
        "القائمة الإلزامية للمحتوى المحلي المنتجات الإلزامية هيئة المحتوى المحلي",
        top_k=4,
    )


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
    label = "استخراج المتطلبات من الكراسة" if is_comp else "استخراج بنود الكميات"

    # جداول الكميات غالباً في ملف مستقل — نقدّمه على النص المدموج إن وُجد
    source = rfp if is_comp else (role_text("boq") or rfp)
    if not is_comp and role_text("boq"):
        st.caption("📄 المصدر: الملفات المصنّفة **جدول الكميات**.")

    col_model, col_btn = st.columns([3, 2])
    with col_model:
        model = _model_picker(f"model_extract_{kind}")
    with col_btn:
        clicked = st.button(f"🤖 {label}", key=f"btn_extract_{kind}", type="primary", width="stretch")

    if not clicked:
        return

    prompt = EXTRACT_PROMPTS["compliance_items" if is_comp else "boq_items"]

    # ترشيح القائمة الإلزامية يصير مبنياً على مرجع بدل التخمين متى توفّر
    if not is_comp:
        reference = _mandatory_list_reference()
        if reference:
            prompt += (
                "\n\n--- القائمة المرجعية للمحتوى المحلي (استند إليها في "
                f"mandatory_list_flag) ---\n{reference}"
            )

    status = st.empty()
    with st.spinner("جاري الاستخراج..."):
        result = ai_generate_json(
            prompt,
            schema=COMPLIANCE_SCHEMA if is_comp else BOQ_SCHEMA,
            model_choice=model,
            rfp_context=source,
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

        # منافسات محفوظة قبل توسيع المخطط تُرقَّى عند العرض
        boq_df = migrate_boq_df(st.session_state.get("df_boq"))
        st.session_state["df_boq"] = boq_df

        col_info2, col_actions = st.columns([3, 2])
        with col_info2:
            flagged = int(boq_df["القائمة الإلزامية"].fillna(False).astype(bool).sum())
            m1, m2 = st.columns(2)
            m1.metric("إجمالي البنود", len(boq_df))
            m2.metric("🇸🇦 مرشّح للقائمة الإلزامية", flagged)
        with col_actions:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("↩️ إعادة ضبط الجدول", key="reset_boq", width="stretch"):
                st.session_state["df_boq"] = DEFAULT_BOQ_DF.copy()
                st.session_state.pop("de_boq", None)
                st.rerun()

        st.caption(
            "⚠️ عمود **القائمة الإلزامية** ترشيح من النموذج لا حكم نهائي — تحقّق منه "
            "مقابل القائمة الرسمية للمحتوى المحلي قبل الاعتماد. رفع القائمة الرسمية "
            "في **مستودع المعرفة** يحسّن دقة الترشيح."
        )

        edited_boq = st.data_editor(
            boq_df,
            num_rows="dynamic",
            width="stretch",
            key="de_boq",
            column_config={
                "رقم البند": st.column_config.TextColumn("رقم البند", width="small"),
                "التصنيف": st.column_config.TextColumn("التصنيف"),
                "البند": st.column_config.TextColumn("البند / الخدمة", width="medium"),
                "الوحدة": st.column_config.TextColumn("الوحدة", width="small"),
                "الوصف": st.column_config.TextColumn("الوصف التفصيلي", width="large"),
                "المواصفات": st.column_config.TextColumn("المواصفات الفنية", width="large"),
                "كود البناء": st.column_config.TextColumn("كود البناء"),
                "الكمية": st.column_config.NumberColumn("الكمية", min_value=0),
                "القائمة الإلزامية": st.column_config.CheckboxColumn(
                    "القائمة الإلزامية",
                    help="هل يقع البند ضمن القائمة الإلزامية للمحتوى المحلي؟",
                ),
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
