"""
views/tables.py — Tab 2: Compliance Matrix + BOQ Editor

الجداول تُملأ آلياً من الكراسة عبر استخراج مُهيكل (JSON)، وتبقى قابلة للتحرير.
"""
import streamlit as st
import pandas as pd
from utils.state import (
    BOQ_COLUMNS,
    COMPLIANCE_CATEGORY_OPTIONS,
    COMPLIANCE_COLUMNS,
    COMPLIANCE_STATUS_OPTIONS,
    CRITICALITY_OPTIONS,
    DEFAULT_BOQ_DF,
    DEFAULT_COMPLIANCE_DF,
    migrate_boq_df,
    migrate_compliance_df,
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
from utils.i18n import t


def _model_picker(key: str) -> str:
    """منتقي نموذج مضغوط يتبع التفضيل الافتراضي."""
    current = st.session_state.get("ai_model_preference", DEFAULT_MODEL)
    return st.selectbox(
        t("common.engine"),
        MODEL_NAMES,
        index=MODEL_NAMES.index(current) if current in MODEL_NAMES else 0,
        key=key,
        label_visibility="collapsed",
    )


def _compliance_to_df(items: list) -> pd.DataFrame:
    """تحويل مصفوفة الامتثال المستخرجة إلى شكل الجدول القابل للتحرير."""
    rows = []
    for i, it in enumerate(items, start=1):
        req = str(it.get("requirement_summary", "")).strip()
        if not req:
            continue

        strategy = str(it.get("proposed_compliance_strategy", "")).strip()
        if bool(it.get("mandatory")):
            strategy = ("⛔ شرط استبعاد · " + strategy) if strategy else "⛔ شرط استبعاد"

        category = str(it.get("category", "")).strip()
        criticality = str(it.get("criticality", "")).strip()

        rows.append({
            "المعرّف": str(it.get("req_id", "") or f"REQ-{i:03d}").strip(),
            "التصنيف": category if category in COMPLIANCE_CATEGORY_OPTIONS else "Technical",
            "مرجع البند": str(it.get("clause_reference", "")).strip(),
            "المتطلب": req,
            "الأهمية": criticality if criticality in CRITICALITY_OPTIONS else "Medium",
            "استراتيجية الاستجابة": strategy,
            # الالتزام قرار بشري — يبدأ دائماً بانتظار التحقق ولا يفترضه النموذج
            "الالتزام": "بانتظار التحقق",
            "الشهادة المطلوبة": str(it.get("certificate", "")).strip(),
        })
    return pd.DataFrame(rows)[COMPLIANCE_COLUMNS] if rows else DEFAULT_COMPLIANCE_DF.copy()


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
        st.info(t("tb.upload_first"))
        return

    is_comp = kind == "compliance"
    label = t("tb.extract_reqs") if is_comp else t("tb.extract_boq")

    # جداول الكميات غالباً في ملف مستقل — نقدّمه على النص المدموج إن وُجد
    source = rfp if is_comp else (role_text("boq") or rfp)
    if not is_comp and role_text("boq"):
        st.caption(t("tb.boq_source"))

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
    with st.spinner(t("common.extracting")):
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
        st.warning(t("tb.nothing_found"))
        return

    df = _compliance_to_df(items) if is_comp else _boq_to_df(items)
    st.session_state["df_compliance" if is_comp else "df_boq"] = df
    # data_editor يحتفظ بتعديلات المستخدم السابقة تحت مفتاحه، فنُبطلها
    # حتى يعرض الجدول البيانات المستخرجة الجديدة بدل القديمة
    st.session_state.pop("de_compliance" if is_comp else "de_boq", None)
    st.success(t("tb.extracted", n=len(df)))
    st.rerun()


def render():
    st.markdown(t("tb.title"))

    # ── Compliance Matrix ──────────────────────────────────────────────────────
    with st.expander(t("tb.compliance"), expanded=True):
        _extraction_bar("compliance")
        st.divider()

        # منافسات محفوظة قبل توسيع المخطط تُرقَّى عند العرض
        df = migrate_compliance_df(st.session_state.get("df_compliance"))
        st.session_state["df_compliance"] = df

        col_info, col_reset = st.columns([4, 1])
        with col_info:
            total = len(df)
            status = df.get("الالتزام", pd.Series(dtype=str))
            compliant = int((status == "نعم").sum())
            partial = int((status == "جزئي").sum())
            high = int((df.get("الأهمية", pd.Series(dtype=str)) == "High").sum())

            c1, c2, c3, c4 = st.columns(4)
            c1.metric(t("tb.total_reqs"), total)
            c2.metric(t("tb.compliant"), compliant)
            c3.metric(t("tb.partial"), partial)
            c4.metric(t("tb.high_criticality"), high)

        with col_reset:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button(f"↩️ {t('common.reset')}", key="reset_comp", width="stretch"):
                st.session_state["df_compliance"] = DEFAULT_COMPLIANCE_DF.copy()
                st.rerun()

        st.caption(t("tb.compliance_note"))

        edited_comp = st.data_editor(
            df,
            num_rows="dynamic",
            width="stretch",
            key="de_compliance",
            column_config={
                "المعرّف": st.column_config.TextColumn("REQ", width="small"),
                "التصنيف": st.column_config.SelectboxColumn(
                    t("tb.col_category"), options=COMPLIANCE_CATEGORY_OPTIONS
                ),
                "مرجع البند": st.column_config.TextColumn(t("tb.col_clause"), width="small"),
                "المتطلب": st.column_config.TextColumn(t("tb.col_requirement"), width="large"),
                "الأهمية": st.column_config.SelectboxColumn(
                    t("tb.col_criticality"), options=CRITICALITY_OPTIONS
                ),
                "استراتيجية الاستجابة": st.column_config.TextColumn(
                    t("tb.col_strategy"), width="large"
                ),
                "الالتزام": st.column_config.SelectboxColumn(
                    t("tb.col_status"), options=COMPLIANCE_STATUS_OPTIONS, required=True
                ),
                "الشهادة المطلوبة": st.column_config.TextColumn(t("tb.col_certificate")),
            },
        )
        # Persist changes immediately
        st.session_state["df_compliance"] = edited_comp

    st.divider()

    # ── BOQ ───────────────────────────────────────────────────────────────────
    with st.expander(t("tb.boq"), expanded=True):
        _extraction_bar("boq")
        st.divider()

        # منافسات محفوظة قبل توسيع المخطط تُرقَّى عند العرض
        boq_df = migrate_boq_df(st.session_state.get("df_boq"))
        st.session_state["df_boq"] = boq_df

        col_info2, col_actions = st.columns([3, 2])
        with col_info2:
            flagged = int(boq_df["القائمة الإلزامية"].fillna(False).astype(bool).sum())
            m1, m2 = st.columns(2)
            m1.metric(t("tb.total_items"), len(boq_df))
            m2.metric(t("tb.flagged"), flagged)
        with col_actions:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button(t("tb.reset_table"), key="reset_boq", width="stretch"):
                st.session_state["df_boq"] = DEFAULT_BOQ_DF.copy()
                st.session_state.pop("de_boq", None)
                st.rerun()

        st.caption(t("tb.mandatory_warning"))

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
    st.markdown(t("tb.export"))
    col_e1, col_e2 = st.columns(2)

    with col_e1:
        if st.button(t("tb.export_comp"), width="stretch"):
            csv = st.session_state["df_compliance"].to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                t("tb.download_comp"),
                data=csv.encode("utf-8-sig"),
                file_name="compliance_matrix.csv",
                mime="text/csv",
                key="dl_comp_csv",
            )

    with col_e2:
        if st.button(t("tb.export_boq"), width="stretch"):
            csv = st.session_state["df_boq"].to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                t("tb.download_boq"),
                data=csv.encode("utf-8-sig"),
                file_name="boq.csv",
                mime="text/csv",
                key="dl_boq_csv",
            )
