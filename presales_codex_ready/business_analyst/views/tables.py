"""
views/tables.py — Tab 2: Compliance Matrix + BOQ Editor

الجداول تُملأ آلياً من الكراسة عبر استخراج مُهيكل (JSON)، وتبقى قابلة للتحرير.
"""
import streamlit as st
import pandas as pd
from utils.state import (
    BOQ_COLUMNS,
    DEFAULT_TIMELINE_DF,
    migrate_timeline_df,
    timeline_to_df,
    COMPLIANCE_CATEGORY_OPTIONS,
    COMPLIANCE_COLUMNS,
    COMPLIANCE_STATUS_OPTIONS,
    COVERAGE_OPTIONS,
    COVERAGE_UNCHECKED,
    CRITICALITY_OPTIONS,
    DEFAULT_BOQ_DF,
    DEFAULT_COMPLIANCE_DF,
    SUBMISSION_HAVE_OPTIONS,
    get_sections,
    migrate_boq_df,
    migrate_compliance_df,
    migrate_submission_df,
    role_text,
    section_content_key,
)
from utils import audit, auth, db, submission, timeline as timeline_utils, traceability
from utils.ai_engine import (
    BOQ_SCHEMA,
    COMPLIANCE_SCHEMA,
    DEFAULT_LANGUAGE,
    EXTRACT_PROMPTS,
    KEY_PERSONNEL_SCHEMA,
    SUBMISSION_SCHEMA,
    TIMELINE_SCHEMA,
    ai_generate_json,
    language_instruction,
)
from components.ui import status_badge
from components import theme
from utils.i18n import t


def _output_language() -> str:
    return st.session_state.get("output_language", DEFAULT_LANGUAGE)


def _model_picker(key: str) -> str:
    """منتقي نموذج مضغوط يتبع الموفّر النشط وتفضيله الافتراضي."""
    from utils.ai_engine import default_model_name, model_names

    options = model_names()
    current = default_model_name()
    return st.selectbox(
        t("common.engine"),
        options,
        index=options.index(current) if current in options else 0,
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
            # الاستخراج يقرأ الكراسة لا نص العرض، فلا علم له بالتغطية بعد.
            "التغطية": COVERAGE_UNCHECKED,
            "القسم المغطّي": "",
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

    if not knowledge.is_populated():
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
        clicked = st.button(f"🤖 {label}", key=f"btn_extract_{kind}", type="primary",
                            width="stretch", disabled=auth.blocked("tables.edit"))

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


def _section_content(key: str) -> str:
    return str(st.session_state.get(section_content_key(key), ""))


# ─── مصفوفة الحلّ (ب-5) ────────────────────────────────────────────────────────


def _render_solution_matrix():
    """
    مصفوفة الحلّ: لكل متطلب مكوّنه.

    موضعها **بعد مصفوفة الامتثال** لأنها تجيب سؤالها التالي: قرأنا «نعم،
    ملتزمون» فبماذا؟ والمعرّفات تُنقل من المصفوفة الأولى ولا تُعاد كتابتها —
    قائمةُ متطلبات ثانية تنحرف عن الأولى فيصير للعرض حقيقتان.
    """
    from utils import traceability
    from utils.state import DEFAULT_SOLUTION_DF, SOLUTION_COLUMNS, migrate_solution_df

    df = migrate_solution_df(st.session_state.get("df_solution"))
    st.session_state["df_solution"] = df
    compliance = st.session_state.get("df_compliance")

    with st.expander(t("sol.title"), expanded=False):
        st.caption(t("sol.hint"))

        # الفجوة أولاً: مُلتزَم به بلا مكوّن يلبّيه
        gaps = traceability.solution_gaps(compliance, df)
        if gaps:
            critical = [g for g in gaps if g["severity"] == "حرجة"]
            body = "\n".join(f"- {g['message']}" for g in gaps[:10])
            if critical:
                st.error(t("sol.gaps_critical", n=len(critical)) + "\n\n" + body)
            else:
                st.warning(t("sol.gaps", n=len(gaps)) + "\n\n" + body)

        col_add, col_reset = st.columns([3, 1])
        with col_add:
            # النقل من مصفوفة الامتثال: المعرّف والمتطلب يُملآن، والباقي للفريق
            if st.button(t("sol.pull_requirements"), disabled=auth.blocked("tables.edit"),
                         help=t("sol.pull_help")):
                st.session_state["df_solution"] = _solution_from_compliance(
                    compliance, df)
                st.session_state.pop("de_solution", None)
                st.rerun()
        with col_reset:
            if st.button(f"↩️ {t('common.reset')}", key="reset_solution",
                         width="stretch", disabled=auth.blocked("tables.edit")):
                st.session_state["df_solution"] = DEFAULT_SOLUTION_DF.copy()
                st.session_state.pop("de_solution", None)
                st.rerun()

        edited = st.data_editor(
            df, num_rows="dynamic", width="stretch", key="de_solution",
            disabled=auth.blocked("tables.edit"),
            column_config={
                "المعرّف": st.column_config.TextColumn("REQ", width="small"),
                "المتطلب": st.column_config.TextColumn(
                    t("tb.col_requirement"), width="large"),
                "مكوّن الحل": st.column_config.TextColumn(
                    t("sol.col_component"), width="medium"),
                "دوره": st.column_config.TextColumn(t("sol.col_role"), width="medium"),
                "المنتج/التقنية": st.column_config.TextColumn(t("sol.col_product")),
                "المورّد": st.column_config.TextColumn(t("sol.col_vendor")),
                "ملاحظات": st.column_config.TextColumn(t("sol.col_notes"), width="large"),
            },
        )
        st.session_state["df_solution"] = edited

        filled = sum(1 for r in edited.to_dict("records")
                     if str(r.get("مكوّن الحل", "") or "").strip())
        st.caption(t("sol.count", filled=filled, total=len(edited),
                     columns=len(SOLUTION_COLUMNS)))


def _solution_from_compliance(compliance, current):
    """
    يملأ المعرّفات والمتطلبات من مصفوفة الامتثال، ويُبقي ما كُتب.

    **لا يمسح عمل الفريق**: صفٌّ لمعرّف موجود يبقى كما هو، والجديد يُضاف —
    وإعادة النقل بعد تعديل الكرّاس تُضيف ما استُجدّ ولا تُلغي ما بُني.
    """
    import pandas as pd

    from utils.state import DEFAULT_SOLUTION_DF, SOLUTION_COLUMNS

    if compliance is None or not hasattr(compliance, "to_dict"):
        return DEFAULT_SOLUTION_DF.copy()

    existing = [r for r in (current.to_dict("records") if current is not None else [])
                if any(str(v or "").strip() for v in r.values())]
    known = {str(r.get("المعرّف", "") or "").strip() for r in existing}

    rows = list(existing)
    for req in compliance.to_dict("records"):
        req_id = str(req.get("المعرّف", "") or "").strip()
        if not req_id or req_id in known:
            continue
        known.add(req_id)
        row = {col: "" for col in SOLUTION_COLUMNS}
        row["المعرّف"] = req_id
        row["المتطلب"] = str(req.get("المتطلب", "") or "").strip()
        rows.append(row)

    return pd.DataFrame(rows or DEFAULT_SOLUTION_DF.to_dict("records"))[SOLUTION_COLUMNS]


# ─── وحدة الاستفسارات (14-9) ───────────────────────────────────────────────────


def _clarify_status_label(item: dict) -> str:
    return t("cl.status_" + str(item.get("status", "") or db.CLARIFY_DRAFT))


def _render_clarifications():
    """
    الاستفسارات: سؤال للجهة بموعده وجوابه، مربوطاً بصفّ المصفوفة.

    موضعها **بعد المصفوفة مباشرةً** لا في شاشة أخرى: الغموض يُرصد هنا، والسؤال
    يُكتب حيث يُرصد — وإلا كُتب في بريد ونُسي، وهو ما وُجد هذا البند لعلاجه.
    """
    from utils import clarifications as clarify

    project_id = st.session_state.get("_project_id")
    df = st.session_state.get("df_compliance")
    may_edit = auth.can("tables.edit")

    with st.expander(t("cl.title"), expanded=False):
        st.caption(t("cl.hint"))
        if project_id is None:
            st.info(t("cl.needs_project"))
            return

        items = db.list_clarifications(project_id)
        stats = clarify.summary(items, df)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(t("cl.m_total"), stats["total"])
        c2.metric(t("cl.m_unsent"), stats["unsent"])
        c3.metric(t("cl.m_overdue"), stats["overdue"])
        c4.metric(t("cl.m_answered"), stats["answered"])

        # المخاطر أولاً: غياب الجواب على متطلب حرج أخطر من ورودِه مخالفاً
        found = clarify.risks(items, df)
        if found:
            critical = [f for f in found if f["severity"] == "حرجة"]
            body = "\n".join(f"- {f['message']}" for f in found)
            if critical:
                st.error(t("cl.risks_critical", n=len(critical)) + "\n\n" + body)
            else:
                st.warning(t("cl.risks", n=len(found)) + "\n\n" + body)
        elif items:
            st.success(t("cl.no_risks"))

        # ── سؤال جديد من متطلب مرصود ──
        index = clarify.requirement_index(df)
        options = [""] + sorted(index)
        with st.form("new_clarification", clear_on_submit=True):
            c_req, c_due = st.columns([1, 1])
            with c_req:
                req_id = st.selectbox(
                    t("cl.req"), options,
                    format_func=lambda r: (
                        t("cl.req_none") if not r
                        else f"{r} — {clarify._short(index[r].get(clarify.REQ_TEXT_COLUMN), 40)}"
                    ),
                )
            with c_due:
                due = st.text_input(t("cl.due"), placeholder="2026-09-01",
                                    help=t("cl.due_help"))
            question = st.text_area(t("cl.question"), height=80,
                                    placeholder=t("cl.question_ph"))
            if st.form_submit_button(t("cl.add"), type="primary",
                                     disabled=not may_edit):
                if not question.strip():
                    st.warning(t("cl.question_required"))
                else:
                    db.add_clarification(project_id, question, req_id=req_id,
                                         due_at=due, created_by=auth.display_name())
                    audit.record(audit.CLARIFY_ADD, detail=req_id or "—")
                    st.success(t("cl.added"))
                    st.rerun()

        if not items:
            st.caption(t("cl.empty"))
            return

        # ── القائمة ──
        for item in items:
            blocking = clarify.is_blocking(item, df)
            left = clarify.days_left(item)
            head = f"{_clarify_status_label(item)} · {clarify._short(item['question'], 60)}"
            if blocking:
                head = "🚨 " + head
            with st.expander(head):
                meta = [t("cl.req") + ": " + (item["req_id"] or t("cl.req_none"))]
                if item["req_id"] and clarify.linked_requirement(item, df) is None:
                    # معرّف لم يعد في المصفوفة: السؤال أُرسل فعلاً فلا يُخفى
                    meta.append(t("cl.req_unlinked"))
                if item["due_at"]:
                    meta.append(t("cl.due") + ": " + item["due_at"] + (
                        f" ({t('cl.days_left', n=left)})" if left is not None
                        else f" — {t('cl.due_unreadable')}"
                    ))
                st.caption(" · ".join(meta))

                if item["status"] == db.CLARIFY_ANSWERED:
                    st.success(t("cl.answer") + ": " + item["answer"])
                    st.caption(t("cl.answer_reaches_model"))

                c_send, c_close, c_del = st.columns(3)
                with c_send:
                    if st.button(t("cl.mark_sent"), key=f"cl_send_{item['id']}",
                                 width="stretch",
                                 disabled=not may_edit
                                 or item["status"] != db.CLARIFY_DRAFT):
                        db.mark_clarification_sent(item["id"])
                        audit.record(audit.CLARIFY_SENT, detail=item["req_id"] or "—")
                        st.rerun()
                with c_close:
                    if st.button(t("cl.close"), key=f"cl_close_{item['id']}",
                                 width="stretch", disabled=not may_edit
                                 or item["status"] == db.CLARIFY_CLOSED):
                        db.close_clarification(item["id"])
                        st.rerun()
                with c_del:
                    if st.button(t("common.delete"), key=f"cl_del_{item['id']}",
                                 width="stretch", disabled=not may_edit):
                        db.delete_clarification(item["id"])
                        st.rerun()

                if item["status"] != db.CLARIFY_ANSWERED:
                    answer = st.text_area(t("cl.answer"), key=f"cl_ans_{item['id']}",
                                          height=80, disabled=not may_edit)
                    if st.button(t("cl.save_answer"), key=f"cl_save_{item['id']}",
                                 type="primary", disabled=not may_edit):
                        # جواب فارغ لا يُغلق سؤالاً: «أُجيب» حالة تُبنى عليها
                        # قرارات امتثال، فتسجيلها بلا نصّ تجعل المتطلب يبدو
                        # محسوماً بلا شيء يحسمه
                        if db.answer_clarification(item["id"], answer):
                            audit.record(audit.CLARIFY_ANSWERED,
                                         detail=item["req_id"] or "—")
                            st.success(t("cl.answer_saved"))
                            st.rerun()
                        else:
                            st.warning(t("cl.answer_required"))


def _render_coverage():
    """
    مصفوفة التتبّع: أي متطلب عولج في أي قسم، وما الذي لم يُعالَج.

    الفحص يقارن نص العرض المكتوب فعلاً بالمصفوفة، فلا يُشغَّل قبل الكتابة.
    """
    with st.expander(t("tb.coverage"), expanded=True):
        st.caption(t("tb.coverage_hint"))

        df = st.session_state.get("df_compliance")
        summary = traceability.coverage_summary(df)

        # لوحات ملوّنة بالنغمة: الفجوة تُقرأ من لونها قبل رقمها.
        theme.stat_tiles(
            [
                (f"{summary['covered']} / {summary['total']}", t("tb.cov_covered")),
                (str(summary["partial"]), t("tb.cov_partial")),
                (str(summary["missing"]), t("tb.cov_missing")),
                (str(summary["unchecked"]), t("tb.cov_unchecked")),
            ],
            tones=[
                "ok",
                "warn" if summary["partial"] else "neutral",
                "error" if summary["missing"] else "neutral",
                "neutral",
            ],
        )

        if summary["blocking"]:
            st.error(t("tb.cov_blocking") + "\n\n"
                     + "\n".join(f"- {item}" for item in summary["blocking"]))

        model = _model_picker("m_coverage")

        if st.button(t("tb.cov_run"), type="primary", key="run_coverage"):
            status = st.empty()
            with st.spinner(t("tb.cov_running")):
                updated = traceability.run_coverage_check(
                    df,
                    get_sections(),
                    content_of=_section_content,
                    model_choice=model,
                    language=st.session_state.get("output_language", DEFAULT_LANGUAGE),
                    on_progress=lambda m: status.caption(f"⏳ {m}"),
                )
            status.empty()
            if updated is None:
                st.warning(t("tb.cov_failed"))
            else:
                st.session_state["df_compliance"] = updated
                st.rerun()


def _render_submission_docs():
    """
    مستندات المظروف: تُستخرج من الكراسة، وحيازتها وإرفاقها قرار بشري.

    الاستبعاد الشكلي لا علاقة له بجودة العرض الفني، فيُتتبَّع مستقلاً عنه.
    """
    with st.expander(t("tb.submission"), expanded=False):
        st.caption(t("tb.submission_hint"))

        df = migrate_submission_df(st.session_state.get("df_submission"))
        st.session_state["df_submission"] = df

        summary = submission.submission_summary(
            df, st.session_state.get("project_context")
        )
        c1, c2, c3 = st.columns(3)
        c1.metric(t("tb.sub_total"), summary["total"])
        c2.metric(t("tb.sub_ready"), f"{summary['ready']} / {summary['mandatory']}")
        c3.metric(t("tb.sub_missing"), len(summary["missing"]))

        if summary["missing"]:
            st.error(t("tb.sub_missing_list") + " · ".join(summary["missing"]))
        if summary["expiring"]:
            st.error(t("tb.sub_expiring") + "\n\n"
                     + "\n".join(f"- {item}" for item in summary["expiring"]))

        col_model, col_btn = st.columns([2, 1])
        with col_model:
            model = _model_picker("m_submission")
        with col_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            run = st.button(t("tb.sub_extract"), type="primary",
                            key="extract_submission", width="stretch",
                            disabled=not st.session_state.get("rfp_raw_text")
                            or auth.blocked("tables.edit"))

        if run:
            status = st.empty()
            with st.spinner(t("common.extracting")):
                result = ai_generate_json(
                    EXTRACT_PROMPTS["submission_docs"]
                    + f"\n{language_instruction(_output_language())}",
                    schema=SUBMISSION_SCHEMA,
                    model_choice=model,
                    rfp_context=st.session_state.get("rfp_raw_text", ""),
                    merge_key="documents",
                    on_progress=lambda m: status.caption(f"⏳ {m}"),
                )
            status.empty()
            docs = (result or {}).get("documents") or []
            if docs:
                st.session_state["df_submission"] = submission.documents_to_df(docs)
                st.rerun()
            elif result is not None:
                st.warning(t("tb.sub_none"))

        edited = st.data_editor(
            df,
            num_rows="dynamic",
            width="stretch",
            key="de_submission",
            disabled=auth.blocked("tables.edit"),
            column_config={
                "المستند": st.column_config.TextColumn(t("tb.sub_col_doc"), width="large"),
                "مرجع البند": st.column_config.TextColumn(t("tb.col_clause"), width="small"),
                "إلزامي": st.column_config.CheckboxColumn(t("tb.sub_col_mandatory")),
                "لدينا": st.column_config.SelectboxColumn(
                    t("tb.sub_col_have"), options=SUBMISSION_HAVE_OPTIONS, required=True
                ),
                "تاريخ الانتهاء": st.column_config.TextColumn(
                    t("tb.sub_col_expiry"), help=t("tb.sub_col_expiry_help")
                ),
                "مرفق في المظروف": st.column_config.CheckboxColumn(t("tb.sub_col_attached")),
                "ملاحظات": st.column_config.TextColumn(t("tb.sub_col_notes"), width="medium"),
            },
        )
        st.session_state["df_submission"] = edited


def _render_timeline():
    """
    الجدول الزمني المُهيكل: مراحل واعتماديات وتسليمات، مع فحص حسابي فوري.

    كان هذا القسم الإلزامي يخرج نصاً حراً لا يُقاس على مدة العقد ولا يُرسم.
    """
    with st.expander(t("tl.title"), expanded=False):
        st.caption(t("tl.hint"))

        df = migrate_timeline_df(st.session_state.get("df_timeline"))
        st.session_state["df_timeline"] = df

        ctx = st.session_state.get("project_context") or {}
        report = timeline_utils.validate(
            df, ctx, st.session_state.get("timeline_contract_weeks")
        )

        c1, c2, c3 = st.columns(3)
        c1.metric(t("tl.phases"), report["phases"])
        c2.metric(t("tl.span"), report["span_weeks"] or "—")
        c3.metric(t("tl.contract"), report["contract_weeks"] or t("tl.contract_unknown"))

        if report["errors"]:
            st.error(t("tl.errors") + "\n\n"
                     + "\n".join(f"- {e}" for e in report["errors"]))
        if report["uncovered_deliverables"]:
            st.warning(t("tl.uncovered") + "\n\n" + "\n".join(
                f"- {d}" for d in report["uncovered_deliverables"][:10]))
        if report["warnings"]:
            st.warning(t("tl.warnings") + "\n\n"
                       + "\n".join(f"- {w}" for w in report["warnings"]))
        if report["phases"] and not report["errors"] and not report["warnings"]:
            st.success(t("tl.ok"))

        col_model, col_btn, col_reset = st.columns([2, 2, 1])
        with col_model:
            model = _model_picker("m_timeline")
        with col_btn:
            run = st.button(t("tl.extract"), type="primary", key="extract_timeline",
                            width="stretch",
                            disabled=not st.session_state.get("rfp_raw_text")
                            or auth.blocked("tables.edit"))
        with col_reset:
            if st.button(f"↩️ {t('common.reset')}", key="reset_timeline", width="stretch",
                         disabled=auth.blocked("tables.edit")):
                st.session_state["df_timeline"] = DEFAULT_TIMELINE_DF.copy()
                st.session_state.pop("de_timeline", None)
                st.rerun()

        if run:
            status = st.empty()
            with st.spinner(t("tl.extracting")):
                result = ai_generate_json(
                    EXTRACT_PROMPTS["timeline_items"]
                    + f"\n{language_instruction(_output_language())}",
                    schema=TIMELINE_SCHEMA,
                    model_choice=model,
                    rfp_context=st.session_state.get("rfp_raw_text", ""),
                    merge_key="phases",
                    on_progress=lambda m: status.caption(f"⏳ {m}"),
                )
            status.empty()
            phases = (result or {}).get("phases") or []
            if phases:
                st.session_state["df_timeline"] = timeline_to_df(result)
                st.session_state["timeline_contract_weeks"] = (
                    result.get("contract_duration_weeks") or 0
                )
                st.session_state.pop("de_timeline", None)
                st.success(t("tl.extracted", n=len(phases)))
                st.rerun()
            elif result is not None:
                st.warning(t("tl.none"))

        edited = st.data_editor(
            df,
            num_rows="dynamic",
            width="stretch",
            key="de_timeline",
            disabled=auth.blocked("tables.edit"),
            column_config={
                "رقم المرحلة": st.column_config.NumberColumn(
                    t("tl.col_number"), min_value=1, width="small"),
                "المرحلة": st.column_config.TextColumn(t("tl.col_phase"), width="medium"),
                "البداية (أسبوع)": st.column_config.NumberColumn(
                    t("tl.col_start"), min_value=1, width="small"),
                "المدة (أسبوع)": st.column_config.NumberColumn(
                    t("tl.col_duration"), min_value=1, width="small"),
                "يعتمد على": st.column_config.TextColumn(t("tl.col_depends"), width="small"),
                "التسليمات": st.column_config.TextColumn(
                    t("tl.col_deliverables"), width="large"),
                "معلم دفع": st.column_config.CheckboxColumn(
                    t("tl.col_payment"), help=t("tl.col_payment_help")),
                "وزن الإنجاز %": st.column_config.NumberColumn(
                    t("tl.col_weight"), min_value=0.0, max_value=100.0),
            },
        )
        st.session_state["df_timeline"] = edited

        grid = timeline_utils.gantt_grid(edited)
        if grid:
            st.caption(t("tl.gantt"))
            st.dataframe(_gantt_preview(grid), width="stretch", hide_index=True)


def _gantt_preview(grid: dict) -> pd.DataFrame:
    """معاينة المخطط في الواجهة — نفس شبكة المستند المصدَّر."""
    prefix = "أ" if grid["unit"] == "week" else "ش"
    columns = [f"{prefix}{i + 1}" for i in range(grid["columns"])]
    rows = []
    for row in grid["rows"]:
        record = {t("tl.col_phase"): row["label"]}
        record.update({c: ("█" if on else "") for c, on in zip(columns, row["cells"])})
        rows.append(record)
    return pd.DataFrame(rows)


def _render_personnel():
    """
    مصفوفة الكوادر الرئيسية (12-2): دور تشترطه الكراسة ← مرشّح من السجل ←
    دليل ← فجوة. الدور بلا مرشّح يظهر فجوةً لا يُحذف.
    """
    from utils import records
    from utils.state import (
        DEFAULT_PERSONNEL_DF, migrate_personnel_df, personnel_gaps,
        personnel_to_df,
    )

    with st.expander(t("tb.personnel"), expanded=False):
        st.caption(t("tb.personnel_hint"))

        people = db.list_records("people")
        rfp = st.session_state.get("rfp_raw_text", "")
        if not people:
            st.warning(t("tb.personnel_no_registry"))
        if not rfp:
            st.info(t("tb.upload_first"))

        col_model, col_btn = st.columns([3, 2])
        with col_model:
            model = _model_picker("model_personnel")
        with col_btn:
            run = st.button(
                t("tb.personnel_run"), type="primary", width="stretch",
                disabled=not rfp or not people,
            )

        if run:
            labels = {c["key"]: c["label_key"] for c in records.columns_of("people")}
            from utils.state import _RECORD_LABELS

            listing = "\n".join(
                "- " + " · ".join(
                    f"{_RECORD_LABELS[labels[k]]}: {v}"
                    for k, v in row.items() if str(v).strip() and str(v) != "0"
                )
                for row in people
            )
            status = st.empty()
            with st.spinner(t("common.extracting")):
                result = ai_generate_json(
                    EXTRACT_PROMPTS["key_personnel"].format(people=listing)
                    + f"\n{language_instruction(_output_language())}",
                    schema=KEY_PERSONNEL_SCHEMA,
                    model_choice=model,
                    rfp_context=rfp,
                    merge_key="roles",
                    on_progress=lambda m: status.caption(f"⏳ {m}"),
                )
            status.empty()
            if result:
                df = personnel_to_df(result)
                st.session_state["df_personnel"] = df
                st.session_state.pop("de_personnel", None)
                st.success(t("tb.personnel_done", n=len(df)))
                st.rerun()

        df = migrate_personnel_df(st.session_state.get("df_personnel"))
        st.session_state["df_personnel"] = df

        gaps = personnel_gaps(df)
        if gaps:
            st.error(t("tb.personnel_gaps", n=len(gaps), roles=" · ".join(gaps)))

        edited = st.data_editor(
            df, num_rows="dynamic", width="stretch", key="de_personnel",
            disabled=auth.blocked("tables.edit"),
            column_config={
                "الدور المطلوب": st.column_config.TextColumn(t("tb.pe_role")),
                "مرجع البند": st.column_config.TextColumn(t("tb.col_clause"), width="small"),
                "اشتراطات الكراسة": st.column_config.TextColumn(
                    t("tb.pe_requirements"), width="large"),
                "المرشّح": st.column_config.TextColumn(t("tb.pe_candidate")),
                "دليل المطابقة": st.column_config.TextColumn(
                    t("tb.pe_evidence"), width="large"),
                "الفجوة": st.column_config.TextColumn(t("tb.pe_gap"), width="large"),
            },
        )
        st.session_state["df_personnel"] = edited

        if st.button(f"↩️ {t('common.reset')}", key="reset_personnel"):
            st.session_state["df_personnel"] = DEFAULT_PERSONNEL_DF.copy()
            st.session_state.pop("de_personnel", None)
            st.rerun()


def _render_local_content():
    """درجة المحتوى المحلي والسعودة (12-8) — رقم صريح يراجعه بشر."""
    from utils import local_content

    with st.expander(t("tb.local_content"), expanded=False):
        st.caption(t("tb.local_content_hint"))

        boq = st.session_state.get("df_boq")
        boq_rows = boq.to_dict(orient="records") if boq is not None else []
        ctx = st.session_state.get("project_context") or {}
        result = local_content.score(
            band=st.session_state.get("c_nitaqat_band", ""),
            boq_rows=boq_rows,
            vendors=db.list_records("vendors"),
            requirement_text=str(ctx.get("local_content_requirements", "")),
        )

        c1, c2, c3 = st.columns(3)
        estimate = result["estimate"]
        c1.metric(t("tb.lc_estimate"),
                  f"{estimate:.0f}%" if estimate is not None else t("common.none"))
        c2.metric(t("tb.lc_required"),
                  f"{result['required']:.0f}%" if result["required"] is not None
                  else t("tb.lc_not_declared"))
        c3.metric(t("tb.lc_gap"),
                  f"{result['gap']:.0f}%" if result["gap"] is not None
                  else t("common.none"))

        if result["meets"] is False:
            st.error(t("tb.lc_below"))
        elif result["meets"] is True:
            st.success(t("tb.lc_meets"))

        rows = [
            {t("tb.lc_component"): t(f"tb.lc_{key}"),
             t("tb.lc_value"): f"{value:.0f}%" if value is not None else "—",
             t("tb.lc_weight"): f"{local_content.WEIGHTS[key] * 100:.0f}%"}
            for key, value in result["components"].items()
        ]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

        if result["missing"]:
            st.warning(t("tb.lc_missing", fields=" · ".join(
                t(f"tb.lc_{k}") for k in result["missing"])))
        st.info(t("tb.lc_disclaimer"))


def render():
    st.markdown(t("tb.title"))
    _render_personnel()
    _render_local_content()

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
            disabled=auth.blocked("tables.edit"),
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
                "التغطية": st.column_config.SelectboxColumn(
                    t("tb.col_coverage"), options=COVERAGE_OPTIONS, width="small"
                ),
                "القسم المغطّي": st.column_config.TextColumn(
                    t("tb.col_covered_in"), width="medium"
                ),
            },
        )
        # Persist changes immediately
        st.session_state["df_compliance"] = edited_comp

    st.divider()
    _render_solution_matrix()

    st.divider()
    _render_clarifications()

    st.divider()
    _render_coverage()

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
            disabled=auth.blocked("tables.edit"),
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

    st.divider()
    _render_timeline()

    st.divider()
    _render_submission_docs()

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
