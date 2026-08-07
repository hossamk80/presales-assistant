"""
views/doc_builder.py — Tab 3: منشئ العرض الفني

الهيكل ديناميكي: إمّا الهيكل الافتراضي أو هيكل يقترحه الذكاء الاصطناعي من
كراسة الشروط. كل قسم قابل للتوليد والتحرير والحذف وإعادة الترتيب.
"""
import re
import streamlit as st

from utils import knowledge, submission, traceability
from utils.ai_engine import (
    DEFAULT_LANGUAGE,
    EXTRACT_PROMPTS,
    MANDATORY_OUTLINE_SECTIONS,
    OUTLINE_SCHEMA,
    PROMPTS,
    ai_generate,
    ai_generate_json,
    build_prompt,
    is_rtl,
    language_instruction,
    outline_prompt,
)
from utils.file_handler import (
    BRAND_COLOR,
    build_pdf_document,
    build_word_document,
    confidentiality_notice,
    resolve_document_tokens,
)
from utils import audit, auth
from components import theme
from utils.i18n import t
from utils.state import (
    SECTION_STATUSES,
    boq_scope_block,
    get_sections,
    matrix_block,
    project_context_block as _project_context_block,
    reset_sections,
    section_content_key,
    section_owner,
    section_status,
    set_section_owner,
    set_section_status,
    set_sections,
)

PLACEHOLDER_RE = re.compile(r"\[.+?\]")

# عدد تبادلات السؤال والجواب المحفوظة لكل قسم قبل إسقاط الأقدم.
QA_THREAD_LIMIT = 5


def _has_placeholders(*texts) -> bool:
    return any(PLACEHOLDER_RE.search(str(x)) for x in texts)


def _model_picker(key: str) -> str:
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


def _as_int(value, default: int = 9999) -> int:
    """section_id قد يعود نصاً من النموذج."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _slugify_key(title: str, taken: set) -> str:
    """مفتاح فريد لقسم اقترحه الذكاء الاصطناعي."""
    base = "ai_" + re.sub(r"[^\w]+", "_", title, flags=re.UNICODE).strip("_")[:40]
    key, n = base, 2
    while key in taken:
        key, n = f"{base}_{n}", n + 1
    return key


# ─── اقتراح الهيكل ────────────────────────────────────────────────────────────


def _render_outline_designer():
    sections = get_sections()

    with st.expander(t("db.outline"), expanded=True):
        st.caption(
            t("db.outline_source",
              source=t("db.src." + st.session_state.get("outline_source", "default")))
            + " · "
            + t("db.outline_stats", total=len(sections),
                included=sum(1 for s in sections if s.get("include")))
        )

        rfp = st.session_state.get("rfp_raw_text", "")
        col_model, col_gen, col_reset = st.columns([2, 2, 1])
        with col_model:
            model = _model_picker("model_outline")
        with col_gen:
            propose = st.button(
                t("db.propose"),
                type="primary",
                width="stretch",
                disabled=not rfp or auth.blocked("sections.write"),
                help=None if rfp else t("db.propose_hint"),
            )
        with col_reset:
            if st.button(f"↩️ {t('common.default')}", width="stretch",
                         disabled=auth.blocked("sections.write")):
                reset_sections()
                st.rerun()

        if propose:
            status = st.empty()
            with st.spinner(t("db.proposing")):
                result = ai_generate_json(
                    outline_prompt(_language()),
                    schema=OUTLINE_SCHEMA,
                    model_choice=model,
                    rfp_context=rfp,
                    extra_context=_project_context_block() + boq_scope_block(),
                    merge_key="outline",
                    on_progress=lambda m: status.caption(f"⏳ {m}"),
                )
            status.empty()
            proposed = (result or {}).get("outline") or []
            if isinstance(result, dict) and result.get("proposal_title"):
                st.session_state["proposal_title"] = str(result["proposal_title"]).strip()
            if proposed:
                _apply_proposed_outline(proposed)
                audit.record(audit.OUTLINE_PROPOSE, source=audit.AI,
                             detail=str(len(proposed)))
                st.rerun()
            elif result is not None:
                st.warning(t("db.no_sections"))

        _render_mandatory_check(get_sections())
        st.divider()
        _render_section_list(sections)


def _apply_proposed_outline(proposed: list):
    """
    يستبدل الأقسام النصية بالأقسام المقترحة، مع الإبقاء على الأقسام البنيوية
    (خطاب التقديم، إشعار السرية، الجداول) لأنها ليست من اختصاص النموذج.
    """
    existing = get_sections()
    by_key = {s["key"]: s for s in existing}

    head = [s for s in existing if s["kind"] in ("cover", "docinfo")]
    tail = [s for s in existing
            if s["kind"] in ("table_compliance", "table_boq", "table_timeline")]

    taken = {s["key"] for s in head + tail}
    body = []
    # section_id يحدّد ترتيب المستند النهائي
    ordered = sorted(proposed, key=lambda x: _as_int(x.get("section_id")))
    for item in ordered:
        title = str(item.get("section_title", "")).strip()
        if not title:
            continue
        # أعِد استخدام مفتاح قسم قائم بنفس العنوان حتى لا يضيع نصّه المكتوب
        match = next(
            (s for s in existing if s["kind"] == "ai" and s["title"].strip() == title),
            None,
        )
        key = match["key"] if match and match["key"] not in taken else _slugify_key(title, taken)
        taken.add(key)
        points = [str(p).strip() for p in (item.get("key_points_to_address") or []) if str(p).strip()]
        body.append({
            "key": key,
            "title": title,
            "kind": "ai",
            "include": str(item.get("priority", "")) != "منخفضة",
            # النقاط الجوهرية هي ما يوجّه صياغة القسم لاحقاً
            "guidance": " · ".join(points),
            "key_points": points,
            "rationale": str(item.get("purpose", "")).strip(),
            "priority": str(item.get("priority", "متوسطة")),
            "prompt_key": (by_key.get(key) or {}).get("prompt_key"),
            # 13-4: قسم باقٍ بمفتاحه يبقى بمالكه وحالته — إعادة اقتراح الهيكل
            # لا تُلغي إسناداً اتُّفق عليه
            "owner": (by_key.get(key) or {}).get("owner"),
            "status": (by_key.get(key) or {}).get("status"),
        })

    set_sections(head + body + tail, source="proposed")
    st.success(t("db.proposed", n=len(body)))


# ─── إسناد الأقسام ولوحتها (13-4) ─────────────────────────────────────────────


def _people() -> dict:
    """المستخدمون الفعّالون: معرّف ← اسم ظاهر. مصدر قائمة المُلّاك."""
    from utils import db

    return {
        u["id"]: (u["display_name"] or u["username"])
        for u in db.list_users() if u["active"]
    }


def _owner_label(section: dict, people: dict) -> str:
    owner = section_owner(section)
    if owner is None:
        return t("db.owner_none")
    # مالك حُذف حسابه أو عُطِّل: يبقى القسم مُسنداً ويظهر أن مالكه لم يعد متاحاً
    return people.get(owner) or t("db.owner_gone")


def _render_assignment_board(sections: list):
    """
    لوحة الأقسام: مالك كل قسم وحالته وهل كُتب نصّه.

    الغاية عملية لا تزيينية: في قسم عطاءات يعمل على عرض واحد، السؤال المتكرّر
    «أي قسم ينتظر من؟» — والجواب كان يتطلّب فتح كل موسّع على حدة.
    """
    import pandas as pd

    writable = [s for s in sections if s["kind"] == "ai"]
    if not writable:
        return

    people = _people()
    with st.expander(t("db.board"), expanded=False):
        st.caption(t("db.board_hint"))

        rows = []
        for sec in writable:
            filled = bool(
                str(st.session_state.get(section_content_key(sec["key"]), "")).strip()
            )
            rows.append({
                t("db.board_section"): sec["title"],
                t("db.board_owner"): _owner_label(sec, people),
                t("db.board_status"): t("db.status_" + section_status(sec)),
                t("db.board_text"): "🟢" if filled else "⚪",
                t("db.include"): "✅" if sec.get("include") else "—",
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

        unassigned = sum(1 for s in writable if section_owner(s) is None)
        if unassigned:
            st.caption(t("db.board_unassigned", n=unassigned))


def _assign_owner(key: str):
    owner = st.session_state.get(f"owner_{key}")
    if set_section_owner(key, owner):
        audit.record(audit.SECTION_ASSIGN, target=audit.section_target(key),
                     detail=str(owner or ""))


def _assign_status(key: str):
    status = st.session_state.get(f"status_{key}")
    if set_section_status(key, status):
        audit.record(audit.SECTION_STATUS, target=audit.section_target(key),
                     detail=str(status))


def _render_section_assignment(sec: dict):
    """إسناد قسم بعينه وحالته — داخل موسّع القسم نفسه."""
    people = _people()
    key = sec["key"]
    may_assign = auth.can("sections.assign")
    owner = section_owner(sec)

    c_owner, c_status = st.columns(2)
    with c_owner:
        options = [None] + list(people)
        st.selectbox(
            t("db.owner"),
            options,
            index=options.index(owner) if owner in options else 0,
            format_func=lambda i: t("db.owner_none") if i is None
            else people.get(i, t("db.owner_gone")),
            key=f"owner_{key}",
            disabled=not may_assign,
            help=t("db.owner_help") if may_assign else t("db.owner_locked"),
            on_change=lambda k=key: _assign_owner(k),
        )
    with c_status:
        # الحالة يحدّثها مالك القسم نفسه — هي إقراره لا حكم غيره عليه
        st.selectbox(
            t("db.status"),
            SECTION_STATUSES,
            index=SECTION_STATUSES.index(section_status(sec)),
            format_func=lambda s: t("db.status_" + s),
            key=f"status_{key}",
            disabled=not auth.can_edit_section(sec),
            on_change=lambda k=key: _assign_status(k),
        )

    if not auth.can_edit_section(sec) and auth.can("sections.write"):
        st.info(t("db.owned_by_other", name=_owner_label(sec, people)))

    # 13-5: مصدر النص الحالي — سؤال لجنة الفحص لا سؤال فضول
    source = audit.section_source(key)
    if source:
        st.caption(t("db.source_" + source))


def _render_mandatory_check(sections: list):
    """
    ينبّه على الأقسام الإلزامية الغائبة، وعلى إدراج التسعير في العرض الفني.

    معايير اعتماد تفصل الفني عن المالي، فإدراج جدول كميات في العرض الفني
    قرار يجب أن يكون واعياً لا سهواً.
    """
    titles = " ".join(s["title"] for s in sections if s.get("include"))
    missing = [name for name in MANDATORY_OUTLINE_SECTIONS
               if not _covers(titles, name)]
    if missing:
        st.warning(t("db.missing_mandatory", names=" · ".join(missing)))

    if any(s.get("include") and s["kind"] == "table_boq" for s in sections):
        st.error(t("db.financial_warning"))


def _covers(haystack: str, section_name: str) -> bool:
    """
    مطابقة مرنة: النموذج قد يصوغ العنوان بألفاظ مختلفة، فنكتفي بتطابق
    كلمة دالة بدل التطابق الحرفي الذي يعطي إنذارات كاذبة.
    """
    keywords = {
        "الملخص التنفيذي": ["ملخص"],
        "ملف الشركة والخبرات ذات الصلة": ["مؤهل", "خبرا", "خبرة", "ملف الشركة"],
        "المنهجية الفنية المقترحة وخطة التنفيذ": ["منهج"],
        # "خطة" وحدها تُطابق "خطة التنفيذ" في قسم المنهجية فتُخفي غياب الجدول
        # الزمني — نطابق على ما يخصّ الزمن وحده.
        "الجدول الزمني ومعالم التسليم": ["الجدول الزمني", "زمني", "معالم", "مراحل"],
        "الهيكل التنظيمي والكوادر الرئيسية": ["فريق", "حوكم", "الهيكل التنظيمي", "كوادر"],
        "ضمان الجودة وإدارة مستويات الخدمة": ["جودة", "مستويات الخدمة", "SLA"],
        "الالتزام بالمحتوى المحلي": ["محتوى المحلي", "المحتوى المحلي"],
    }.get(section_name, [section_name])
    return any(k in haystack for k in keywords)


def _render_section_list(sections: list):
    """قائمة الأقسام مع الإدراج والترتيب والحذف."""
    st.markdown(t("db.sections_hint"))

    changed = False
    for i, sec in enumerate(sections):
        c_inc, c_title, c_up, c_down, c_del = st.columns([1, 8, 1, 1, 1])

        with c_inc:
            new_inc = st.checkbox(
                t("db.include"),
                value=bool(sec.get("include")),
                key=f"inc_{sec['key']}",
                label_visibility="collapsed",
            )
            if new_inc != sec.get("include"):
                sections[i]["include"] = new_inc
                changed = True

        with c_title:
            badge = {
                "cover": "✉️", "docinfo": "🔒", "ai": "✍️",
                "table_compliance": "📋", "table_boq": "📦",
            }.get(sec["kind"], "•")
            filled = bool(st.session_state.get(section_content_key(sec["key"]), "").strip())
            mark = "🟢" if filled or sec["kind"] != "ai" else "⚪"
            prio = t("db.priority", value=sec["priority"]) if sec.get("priority") else ""
            st.markdown(
                f"{mark} {badge} **{sec['title']}**"
                f"<span style='color:{theme.TOKENS['muted']};font-size:12px'>{prio}</span>",
                unsafe_allow_html=True,
            )

        with c_up:
            if st.button("⬆️", key=f"up_{sec['key']}",
                         disabled=i == 0 or auth.blocked("sections.write")):
                sections[i - 1], sections[i] = sections[i], sections[i - 1]
                set_sections(sections)
                st.rerun()
        with c_down:
            if st.button("⬇️", key=f"dn_{sec['key']}",
                         disabled=i == len(sections) - 1 or auth.blocked("sections.write")):
                sections[i + 1], sections[i] = sections[i], sections[i + 1]
                set_sections(sections)
                st.rerun()
        with c_del:
            if st.button("🗑️", key=f"del_{sec['key']}",
                         disabled=sec["kind"] != "ai" or auth.blocked("sections.write")):
                st.session_state.pop(section_content_key(sec["key"]), None)
                set_sections([s for s in sections if s["key"] != sec["key"]])
                st.rerun()

    if changed:
        set_sections(sections)

    # إضافة قسم مخصص
    with st.form("add_section", clear_on_submit=True):
        c1, c2 = st.columns([4, 1])
        with c1:
            new_title = st.text_input(
                t("db.new_section"), placeholder=t("db.new_section_ph"),
                label_visibility="collapsed",
            )
        with c2:
            if st.form_submit_button(t("db.add_section"), width="stretch") and new_title.strip():
                secs = get_sections()
                key = _slugify_key(new_title.strip(), {s["key"] for s in secs})
                tail_at = next(
                    (i for i, s in enumerate(secs) if s["kind"].startswith("table_")), len(secs)
                )
                secs.insert(tail_at, {
                    "key": key, "title": new_title.strip(), "kind": "ai",
                    "include": True, "guidance": "",
                })
                set_sections(secs)
                st.rerun()


# ─── تحرير الأقسام ────────────────────────────────────────────────────────────


def _language() -> str:
    return st.session_state.get("output_language", DEFAULT_LANGUAGE)


def _section_prompt(sec: dict) -> str:
    """يبني تعليمات التوليد للقسم: قالب متخصص إن وُجد، وإلا القالب العام."""
    lang = _language()
    company = st.session_state.get("c_overview") or st.session_state.get("c_name", "")
    eval_weights = st.session_state.get("sum_eval") or "غير محدد"
    compliance = st.session_state.get("sum_comp") or "غير محدد"

    prompt_key = sec.get("prompt_key")
    if prompt_key == "methodology":
        return build_prompt(
            "methodology", lang,
            company_overview=company,
            eval_weights=eval_weights,
            compliance_summary=compliance,
        )
    if prompt_key == "project_plan":
        return build_prompt(
            "project_plan", lang,
            company_name=st.session_state.get("c_name", "الشركة"),
            project_context=st.session_state.get("sum_gonogo", ""),
        )
    if prompt_key and prompt_key in PROMPTS:
        return build_prompt(prompt_key, lang)

    points = sec.get("key_points") or []
    guidance = "\n".join(f"- {p}" for p in points) if points else (
        sec.get("guidance") or "- غطِّ ما تقتضيه طبيعة هذا القسم في عرض فني حكومي."
    )
    return build_prompt(
        "section", lang,
        title=sec["title"],
        purpose=sec.get("rationale") or sec.get("guidance") or "—",
        guidance=guidance,
        company_overview=company,
        eval_weights=eval_weights,
        compliance_summary=compliance,
        user_steering=_steering(sec["key"]) or "لا توجد توجيهات إضافية.",
    )


def _steering_key(key: str) -> str:
    return f"steer_{key}"


def _steering(key: str) -> str:
    return str(st.session_state.get(_steering_key(key), "")).strip()


def _kb_context(sec: dict) -> str:
    """يسترجع من مستودع معرفة الشركة ما يخص هذا القسم تحديداً."""
    if not knowledge.is_populated():
        return ""
    query = " ".join(filter(None, [sec.get("title"), sec.get("guidance")]))
    return knowledge.build_context(query)


def _glossary_context(sec: dict, full_rfp: str) -> str:
    """
    مصطلحات المسرد الواردة في هذه المنافسة (14-6).

    الترشيح على **الكرّاس كاملاً** لا على المقاطع المسترجعة للقسم: القسم قد
    يكتب مصطلحاً ورد في موضع آخر من الكرّاس، وحصر المسرد على ما استُرجع له
    يجعل التوحيد يسقط في أول قسم لم يُسترجَع له المصطلح — وهو عين ما نعالجه.
    """
    from utils import ai_engine

    scope = " ".join(filter(None, [
        full_rfp, sec.get("title"), sec.get("guidance"),
        " ".join(sec.get("key_points") or []),
    ]))
    return ai_engine.glossary_context_block(scope, _language())


def _writing_context(sec: dict) -> tuple[str, str]:
    """
    سياق كتابة القسم: (نص الكراسة المُمرَّر، السياق الإضافي).

    الوضع المضغوط (11-10): يستبدل نص الكراسة الكامل بالسياق الموحّد
    وموجز المصفوفة وبنود الكراسة المسترجعة للقسم (11-11) — فينخفض توكن
    الكتابة دون فقد المتطلبات. يعود للنص الكامل إن تعذّرت الفهرسة.

    وبصمة الأسلوب (14-5) تدخل هنا لا في تعليمات القسم: فتصل **كل** قسم بالنص
    نفسه، وهو ما يجعل العرض كلّه بنبرة واحدة بدل قسم يتبع العيّنة وآخر لا.
    ومسرد المصطلحات (14-6) كذلك — كتلة **منفصلة** عن الأسلوب لا مدموجة به.
    """
    full_rfp = st.session_state.get("rfp_raw_text", "")
    extra = (
        _project_context_block() + _kb_context(sec)
        + knowledge.style_context_block()
        + _glossary_context(sec, full_rfp)
    )

    if not st.session_state.get("compressed_context", True) \
            or not st.session_state.get("project_context"):
        return full_rfp, extra

    rfp_block = ""
    if full_rfp:
        query = " ".join(filter(None, [sec.get("title"), sec.get("guidance")]))
        # بالتضمين إن توفّر، وإلا لفظياً بلا كلفة
        rfp_block = knowledge.rfp_context_for(full_rfp, query)
        if not rfp_block:
            # تعذّر الاسترجاع بالمسارين — النص الكامل أفضل من فقد السياق
            return full_rfp, extra

    return "", extra + matrix_block() + rfp_block


def _render_editors(sections: list):
    st.markdown(t("db.editors"))
    _render_assignment_board(sections)

    included = [s for s in sections if s.get("include")]
    if not included:
        st.info(t("db.no_included"))
        return

    for sec in included:
        if sec["kind"] == "docinfo":
            continue

        if sec["kind"] == "table_compliance":
            df = st.session_state.get("df_compliance")
            n = 0 if df is None else len(df)
            st.caption(f"📋 **{sec['title']}** — " + t("db.table_injected", n=n))
            continue

        if sec["kind"] == "table_boq":
            df = st.session_state.get("df_boq")
            n = 0 if df is None else len(df)
            st.caption(f"📦 **{sec['title']}** — " + t("db.table_injected", n=n))
            continue

        if sec["kind"] == "cover":
            _render_cover_editor(sec)
            continue

        _render_ai_editor(sec)


def _render_cover_editor(sec: dict):
    with st.expander(f"✉️ {sec['title']}", expanded=False):
        use_template = st.radio(
            t("db.cover_mode"),
            ["template", "ai"],
            format_func=lambda k: t("db.cover_template") if k == "template" else t("db.cover_ai"),
            key="cover_type_radio",
        )
        st.session_state["sec_cover_use_template"] = use_template == "template"

        if st.session_state["sec_cover_use_template"]:
            st.info(
                t("db.cover_uses") + "\n\n"
                + st.session_state.get("c_cover_template", "")[:300]
            )
            return

        col_m, col_b = st.columns([3, 1])
        with col_m:
            model = _model_picker("model_cover")
        with col_b:
            go = st.button(t("db.cover_generate"), key="btn_cover", type="primary",
                           width="stretch", disabled=auth.blocked("sections.write"))
        if go:
            with st.spinner(t("common.generating")):
                out = ai_generate(
                    f"اكتب خطاب تقديم احترافي موجز لشركة "
                    f"{st.session_state.get('c_name', 'الشركة')} للتقدم لهذه المنافسة الحكومية. "
                    f"لا تخترع أرقاماً أو مراجع.\n{language_instruction(_language())}",
                    model_choice=model,
                    rfp_context=st.session_state.get("rfp_raw_text", ""),
                    language=_language(),
                )
            if out:
                st.session_state["sec_cover"] = out
                st.rerun()

        st.session_state["sec_cover"] = st.text_area(
            t("db.cover_text"),
            value=st.session_state.get("sec_cover", ""),
            height=220,
            key="ta_cover",
            disabled=auth.blocked("sections.write"),
        )


def _render_ai_editor(sec: dict):
    key = sec["key"]
    ckey = section_content_key(key)
    content = st.session_state.get(ckey, "")
    icon = "🟢" if content.strip() else "⚪"

    with st.expander(f"{icon} {sec['title']}", expanded=False):
        _render_section_assignment(sec)
        # 13-4: من هنا فصاعداً الصلاحية على هذا القسم بعينه لا على النوع
        may_write = auth.can_edit_section(sec)
        if sec.get("rationale"):
            st.caption(f"💡 {sec['rationale']}")
        points = sec.get("key_points") or []
        if points:
            st.caption(f"**{t('db.key_points')}:** " + " · ".join(points))
        elif sec.get("guidance"):
            st.caption(t("db.covers", value=sec["guidance"]))

        col_m, col_b = st.columns([3, 1])
        with col_m:
            model = _model_picker(f"model_{key}")
        with col_b:
            go = st.button(f"⚡ {t('common.generate')}", key=f"btn_{key}", type="primary",
                           width="stretch", disabled=not may_write)

        if go:
            status = st.empty()
            with st.spinner(t("common.generating")):
                rfp_context, extra_context = _writing_context(sec)
                out = ai_generate(
                    _section_prompt(sec),
                    model_choice=model,
                    rfp_context=rfp_context,
                    on_progress=lambda m: status.caption(f"⏳ {m}"),
                    extra_context=extra_context,
                    language=_language(),
                )
            status.empty()
            if out:
                st.session_state[ckey] = out
                audit.record(audit.SECTION_GENERATE,
                             target=audit.section_target(key), source=audit.AI,
                             detail=sec["title"])
                audit.snapshot_section(key, out, source=audit.AI)
                # نُبطل مفتاح المحرر ليعرض النص المولَّد الجديد
                st.session_state.pop(f"ta_{key}", None)
                st.rerun()

        # توجيه الكتابة يُحفظ مع المنافسة ويُمرَّر للنموذج عند التوليد
        st.text_area(
            t("db.steering"),
            height=80,
            placeholder=t("db.steering_ph"),
            key=_steering_key(key),
            disabled=not may_write,
        )

        # 13-3: المراجع والمطّلع يقرآن النص ولا يكتبانه
        # 13-4: ومن ليس مالك القسم كذلك — والنص يبقى مقروءاً للجميع
        st.session_state[ckey] = st.text_area(
            t("db.section_text"),
            value=content,
            height=300,
            key=f"ta_{key}",
            disabled=not may_write,
        )

        if _has_placeholders(st.session_state[ckey]):
            st.warning(t("db.placeholder_warn"))

        _render_block_library(sec)
        _render_side_assistant(sec, model)
        _render_versions(sec)


# ─── مكتبة المحتوى المعتمد (14-4) ─────────────────────────────────────────────


def _insert_block(sec: dict, block: dict):
    """
    يُلحق نصّ كتلة معتمدة بنص القسم — **بلا استدعاء نموذج**، وهذا شرط قبول 14-4.

    لا شيء في هذا المسار يمسّ `ai_engine`: النصّ يأتي من القاعدة كما اعتُمد
    ويُكتب في الجلسة. أي توليد هنا يُبطل الغاية — الكتلة موجودة **لأنّ** صياغتها
    حُسمت مرة فلا تُعاد كتابتها في كل عرض.

    الإلحاق لا الاستبدال: كتلة تمحو ما كتبه الكاتب تخسر عملاً، والحذف بيد
    المستخدم في محرّر القسم. والنصّ الحالي يُحفظ نسخةً قبل الإلحاق (13-6)
    فالإدراج تراجعه خطوة.
    """
    from utils import db

    key = sec["key"]
    ckey = section_content_key(key)
    current = str(st.session_state.get(ckey, "") or "")

    audit.snapshot_section(key, current, source=audit.HUMAN)
    body = str(block.get("body") or "").strip()
    st.session_state[ckey] = f"{current.rstrip()}\n\n{body}".lstrip() if current.strip() else body
    st.session_state.pop(f"ta_{key}", None)

    db.record_block_use(int(block["id"]))
    # المصدر إنسان لا نموذج: نصّ كتبه بشر واعتمده بشر لا يصير مسؤولية النموذج
    # لأنّ زرّاً أدرجه — و 13-5 يقرأ هذا الحقل ليقول من يملك الفقرة.
    audit.record(audit.BLOCK_INSERT, target=audit.section_target(key),
                 source=audit.HUMAN, detail=str(block.get("key") or ""))


def _render_block_library(sec: dict):
    """
    اختيار كتلة معتمدة وإدراجها في القسم.

    المعروض **المعتمد وحده** (`db.approved_blocks`) مرشّحاً بقطاع المنافسة ولغة
    المخرجات: كتلة إنجليزية في عرض عربي ضوضاء لا خيار. والمتأخّرة عن مراجعتها
    تُعرض بتحذير ولا تُمنع — المنع يوم انقضاء تاريخ يوقف الكتابة في يوم تسليم،
    والقرار البشري هو الأصل.
    """
    from utils import ai_engine, db

    key = sec["key"]
    blocks = db.approved_blocks(sector=ai_engine.active_sector(),
                                language=_language())

    with st.expander(t("lib.insert_title"), expanded=False):
        st.caption(t("lib.insert_help"))
        if not blocks:
            st.info(t("lib.none_approved"))
            return

        labels = {}
        for block in blocks:
            title = block.get("title") or block.get("key")
            due = "⚠️ " if db.block_review_due(block) else ""
            category = block.get("category") or ""
            labels[block["id"]] = f"{due}{title}" + (f" — {category}" if category else "")

        chosen_id = st.selectbox(
            t("lib.pick"), list(labels), format_func=lambda i: labels[i],
            key=f"lib_pick_{key}",
        )
        chosen = next((b for b in blocks if b["id"] == chosen_id), None)
        if chosen is None:
            return

        if db.block_review_due(chosen):
            st.warning(t("lib.review_due"))
        st.caption(t("lib.used_count", count=int(chosen.get("used_count") or 0)))
        st.text_area(t("lib.preview"), value=chosen.get("body") or "", height=140,
                     key=f"lib_prev_{key}", disabled=True)

        if st.button(f"➕ {t('lib.insert')}", key=f"lib_ins_{key}",
                     type="primary", disabled=not auth.can_edit_section(sec)):
            _insert_block(sec, chosen)
            st.success(t("lib.inserted"))
            st.rerun()


def _render_side_assistant(sec: dict, model: str):
    """
    المساعد الجانبي: تنقيح نص القسم وفق طلب حر من المستخدم.

    يعمل على النص الحالي مهما كان مصدره — مولَّداً أو مكتوباً يدوياً — ويحفظ
    النسخة السابقة ليتمكن المستخدم من التراجع.
    """
    key = sec["key"]
    ckey = section_content_key(key)
    current = str(st.session_state.get(ckey, "")).strip()

    with st.expander(t("db.assistant"), expanded=False):
        if not current:
            st.info(t("db.refine_needs_text"))
            return

        quick = {
            "concise": t("db.quick_concise"),
            "kpis": t("db.quick_kpis"),
            "risk": t("db.quick_risk"),
            "formal": t("db.quick_formal"),
        }
        cols = st.columns(len(quick))
        for col, (qkey, label) in zip(cols, quick.items()):
            with col:
                if st.button(label, key=f"quick_{qkey}_{key}", width="stretch",
                             disabled=not auth.can_edit_section(sec)):
                    _apply_refinement(sec, label, model)
                    st.rerun()

        c_req, c_apply, c_ask = st.columns([4, 1, 1])
        with c_req:
            request = st.text_input(
                t("db.assistant"),
                placeholder=t("db.assistant_ph"),
                key=f"refine_req_{key}",
                label_visibility="collapsed",
            )
        with c_apply:
            go = st.button(t("db.refine"), key=f"refine_{key}",
                           type="primary", width="stretch",
                           disabled=not auth.can_edit_section(sec))
        with c_ask:
            # السؤال والتعديل زرّان منفصلان عمداً: السؤال لا يمسّ نص القسم،
            # وخلطهما كان يجعل "هل غطّينا شرط السعودة؟" يُعيد كتابة القسم.
            ask = st.button(t("db.ask"), key=f"ask_{key}", width="stretch",
                            help=t("db.ask_help"),
                            disabled=auth.blocked("assistant.ask"))

        if go and request.strip():
            _apply_refinement(sec, request.strip(), model)
            st.rerun()

        if ask and request.strip():
            _answer_question(sec, request.strip(), model)
            st.rerun()

        _render_qa_thread(key)

        undo_key = f"_undo_{ckey}"
        if st.session_state.get(undo_key):
            if st.button(f"↩️ {t('common.undo')}", key=f"undo_refine_{key}",
                         disabled=not auth.can_edit_section(sec)):
                st.session_state[ckey] = st.session_state.pop(undo_key)
                st.session_state.pop(f"ta_{key}", None)
                st.rerun()


# ─── نسخ الأقسام واسترجاعها (13-6) ────────────────────────────────────────────


def _version_label(version: dict) -> str:
    """سطر يعرّف النسخة: متى · من · مصدرها · طولها."""
    who = version["username"] or t("ad2.unknown_user")
    mark = "🤖" if version["source"] == "ai" else "✍️"
    return f'{version["created_at"]} · {mark} {who} · {len(version["content"]):,}'


def _diff_lines(old: str, new: str) -> str:
    """
    فرق سطري بصيغة موحّدة — من `difflib` القياسية بلا مكتبة إضافية.

    المقارنة على السطور لا الكلمات: العرض مكتوب فقرات، وفرق الكلمات داخل فقرة
    طويلة يُخرج ضجيجاً لا يُقرأ.
    """
    import difflib

    diff = difflib.unified_diff(
        (old or "").splitlines(), (new or "").splitlines(),
        lineterm="", n=1,
    )
    body = "\n".join(list(diff)[2:])       # سطرا الترويسة لا يفيدان القارئ
    return body


def _render_versions(sec: dict):
    """
    نسخ القسم: عرض ومقارنة واسترجاع.

    الاسترجاع **يحفظ نسخة من النص الحالي قبل أن يستبدله** — وإلا صار الاسترجاع
    نفسه سبباً لفقد ما استُرجع منه.
    """
    from utils import db

    key = sec["key"]
    ckey = section_content_key(key)
    project_id = st.session_state.get("_project_id")
    versions = db.list_section_versions(key, project_id)

    with st.expander(t("db.versions", n=len(versions))):
        if not versions:
            st.caption(t("db.versions_empty"))
            return

        st.caption(t("db.versions_hint", limit=db.SECTION_VERSION_LIMIT))

        labels = {v["id"]: _version_label(v) for v in versions}
        chosen_id = st.selectbox(
            t("db.versions_pick"), list(labels),
            format_func=lambda i: labels[i], key=f"ver_pick_{key}",
        )
        chosen = db.get_section_version(chosen_id)
        if chosen is None:
            return

        current = str(st.session_state.get(ckey, "") or "")
        diff = _diff_lines(chosen["content"], current)
        if diff:
            st.caption(t("db.versions_diff"))
            st.code(diff, language="diff")
        else:
            st.caption(t("db.versions_same"))

        may_restore = auth.can_edit_section(sec) and bool(diff)
        if st.button(t("db.versions_restore"), key=f"ver_restore_{key}",
                     type="primary", disabled=not may_restore,
                     help=None if may_restore else t("db.versions_restore_help")):
            audit.snapshot_section(key, current, source=audit.HUMAN)
            st.session_state[ckey] = chosen["content"]
            st.session_state.pop(f"ta_{key}", None)
            audit.record(audit.SECTION_RESTORE, target=audit.section_target(key),
                         detail=str(chosen_id))
            st.success(t("db.versions_restored"))
            st.rerun()


def _render_qa_thread(key: str):
    """
    آخر تبادلات السؤال والجواب لهذا القسم.

    نقاش عابر لا يُحفظ مع المنافسة: المُخرَج هو نص القسم، والحوار وسيلة إليه.
    """
    thread = st.session_state.get(f"_qa_{key}") or []
    if not thread:
        return

    st.divider()
    for question, answer in thread:
        st.markdown(f"**❓ {question}**")
        st.markdown(answer)
    if st.button(f"🧹 {t('db.qa_clear')}", key=f"qa_clear_{key}"):
        st.session_state.pop(f"_qa_{key}", None)
        st.rerun()


def _assistant_context(sec: dict) -> str:
    """
    سياق المنافسة الذي يعمل عليه المساعد الجانبي.

    بدونه كان "أضف مؤشرات أداء" يُنتج مؤشرات عامة بدل مستويات الخدمة المطلوبة
    في هذه الكراسة بالذات — وهو ما يُفقد درجات بدل أن يكسبها.
    """
    return _project_context_block() + _kb_context(sec)


def _apply_refinement(sec: dict, request: str, model: str):
    """ينفّذ طلب التنقيح على نص القسم مع حفظ نسخة للتراجع."""
    ckey = section_content_key(sec["key"])
    current = st.session_state.get(ckey, "")

    with st.spinner(t("db.refining")):
        revised = ai_generate(
            build_prompt("refine", _language(), content=current, edit_request=request),
            model_choice=model,
            rfp_context=st.session_state.get("rfp_raw_text", ""),
            extra_context=_assistant_context(sec),
            language=_language(),
        )
    if not revised:
        return

    st.session_state[f"_undo_{ckey}"] = current
    st.session_state[ckey] = revised
    st.session_state.pop(f"ta_{sec['key']}", None)
    audit.record(audit.SECTION_REFINE, target=audit.section_target(sec["key"]),
                 source=audit.AI, detail=request[:120])
    # النسخة قبل التنقيح كما بعده: التراجع بنقرة يعالج آخر تنقيح وحده، والنسخ
    # تعالج ما قبله
    audit.snapshot_section(sec["key"], current, source=audit.HUMAN)
    audit.snapshot_section(sec["key"], revised, source=audit.AI)


def _answer_question(sec: dict, question: str, model: str):
    """
    يجيب عن سؤال حول القسم **دون المساس بنصه**.

    السؤال المكتوب في خانة التعديل كان يُعامَل أمراً بالتحرير، فيُعاد كتابة
    القسم وقد يُحقن الجواب داخل نص العرض — والمستخدم يفقد عمله ولا ينقذه إلا
    التراجع.
    """
    current = str(st.session_state.get(section_content_key(sec["key"]), "")).strip()

    with st.spinner(t("db.asking")):
        answer = ai_generate(
            build_prompt("ask", _language(), content=current, question=question),
            model_choice=model,
            rfp_context=st.session_state.get("rfp_raw_text", ""),
            extra_context=_assistant_context(sec),
            language=_language(),
        )
    if not answer:
        return

    thread_key = f"_qa_{sec['key']}"
    st.session_state[thread_key] = (
        st.session_state.get(thread_key, []) + [(question, answer)]
    )[-QA_THREAD_LIMIT:]


# ─── التصدير ──────────────────────────────────────────────────────────────────


def _collect_export_payload(sections: list) -> list:
    """يبني قائمة الأقسام المُدرَجة بمحتواها النهائي، جاهزة للبنّاء."""
    payload = []
    for sec in sections:
        if not sec.get("include"):
            continue
        item = {"key": sec["key"], "title": sec["title"], "kind": sec["kind"], "content": ""}

        if sec["kind"] == "cover":
            raw = (
                st.session_state.get("c_cover_template", "")
                if st.session_state.get("sec_cover_use_template", True)
                else st.session_state.get("sec_cover", "")
            )
            item["content"] = resolve_document_tokens(
                raw, st.session_state.get("c_name", "")
            )
        elif sec["kind"] == "docinfo":
            item["content"] = confidentiality_notice(
                st.session_state.get("c_name", ""), _language()
            )
        elif sec["kind"] == "ai":
            item["content"] = st.session_state.get(section_content_key(sec["key"]), "")

        payload.append(item)

    payload.extend(_appendix_payload())
    return payload


def _appendix_payload() -> list:
    """
    ملاحق السجلات كأقسام في نهاية المستند (12-9).

    تُبنى جداول Markdown فيمرّ بها نفس مسار الأقسام النصية: تدخل الفهرس،
    ويستمر ترقيم الصفحات عليها، وتخرج في Word و PDF بلا شيفرة بنّاء جديدة.
    """
    chosen = st.session_state.get("export_appendices") or []
    if not chosen:
        return []

    from utils import appendices, db
    from utils.state import _RECORD_LABELS

    out = []
    for appendix in appendices.build_all(db.list_records, _RECORD_LABELS, chosen):
        header = "| " + " | ".join(appendix["headers"]) + " |"
        divider = "|" + "---|" * len(appendix["headers"])
        body = "\n".join("| " + " | ".join(row) + " |" for row in appendix["rows"])
        out.append({
            "key": f"appendix_{appendix['registry']}",
            "title": appendix["title"],
            "kind": "ai",
            "content": f"{header}\n{divider}\n{body}",
        })
    return out


def _render_export(sections: list):
    st.divider()
    st.markdown(t("db.export_title"))

    payload = _collect_export_payload(sections)
    text_items = [p for p in payload if p["kind"] in ("cover", "ai")]
    all_text = " ".join(p["content"] for p in text_items)

    has_placeholders = _has_placeholders(all_text)
    empty_sections = [p["title"] for p in text_items if not p["content"].strip()]
    placeholder_sections = {
        p["title"]: sorted(set(PLACEHOLDER_RE.findall(p["content"])))[:6]
        for p in text_items
        if PLACEHOLDER_RE.search(p["content"])
    }

    coverage = traceability.coverage_summary(st.session_state.get("df_compliance"))

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(t("db.chk_company"), "✅" if st.session_state.get("c_name") else "❌")
    c2.metric(t("db.chk_rfp"), "✅" if st.session_state.get("rfp_raw_text") else "❌")
    c3.metric(t("db.chk_written"), f"{len(text_items) - len(empty_sections)} / {len(text_items)}")
    c4.metric(t("db.chk_placeholders"), "✅" if not has_placeholders else "❌")
    c5.metric(t("db.chk_coverage"),
              f"{coverage['covered']} / {coverage['total']}" if coverage["total"] else "—")

    if empty_sections:
        st.warning(t("db.empty_sections") + " · ".join(empty_sections))
    if placeholder_sections:
        details = "\n".join(
            f"- **{title}**: {' · '.join(marks)}"
            for title, marks in placeholder_sections.items()
        )
        st.error(t("db.placeholders_found") + "\n\n" + details)

    # مستند ناقص لا يُبطل العرض الفني نفسه — الملف صحيح والنقص في المظروف.
    # فيُعرض بوضوح ولا يمنع التصدير: قد يبني المستخدم الملف ليراجعه بينما
    # يلاحق الضمان البنكي.
    envelope = submission.submission_summary(
        st.session_state.get("df_submission"), st.session_state.get("project_context")
    )
    if envelope["missing"]:
        st.warning(t("db.envelope_missing") + " · ".join(envelope["missing"][:10]))
    if envelope["expiring"]:
        st.error(t("db.envelope_expiring") + "\n\n"
                 + "\n".join(f"- {item}" for item in envelope["expiring"][:10]))

    # متطلب عالي الأهمية بلا تغطية سبب استبعاد مباشر، فيمنع التصدير كما يمنعه
    # النص النائب — لا تحذيراً يمكن تجاوزه سهواً.
    if coverage["blocking"]:
        st.error(
            t("db.coverage_blocking", count=len(coverage["blocking"])) + "\n\n"
            + "\n".join(f"- {item}" for item in coverage["blocking"][:10])
        )

    if st.session_state.get("c_word_template_bytes"):
        st.success(t("db.template_on"))
    else:
        st.info(t("db.template_off"))

    opt1, opt2 = st.columns(2)
    with opt1:
        include_toc = st.checkbox(t("db.opt_toc"), value=True, key="exp_toc")
    with opt2:
        include_pageno = st.checkbox(t("db.opt_pageno"), value=True, key="exp_pageno")

    # الملاحق المرقّمة من السجلات (12-9)
    from utils import appendices, db as _db

    _available = appendices.available(_db.list_records)
    if _available:
        st.multiselect(
            t("db.appendices"),
            _available,
            format_func=lambda r: t(f"rec.{r}"),
            key="export_appendices",
            help=t("db.appendices_help"),
        )
    else:
        st.caption(t("db.appendices_empty"))

    company_name = st.session_state.get("c_name", "")
    proposal_title = st.session_state.get("proposal_title", "")
    # الجهة المصدِرة تأتي من دمج المرفقات؛ تظهر على الغلاف كسطر "مقدَّم إلى".
    entity_name = str(
        (st.session_state.get("project_context") or {}).get("issuing_entity", "")
    ).strip()
    brand = {
        "brand_color": st.session_state.get("c_brand_color") or BRAND_COLOR,
        "proposal_title": proposal_title,
        "entity_name": entity_name,
    }
    if proposal_title:
        st.caption(f"{t('db.proposal_title')} **{proposal_title}**")
    if entity_name:
        st.caption(f"{t('db.submitted_to')} **{entity_name}**")
    slug = (company_name or "Proposal").replace(" ", "_")[:20]
    # 13-3: التصدير يُخرج المستند من النظام — ممنوع على المطّلع. يُضاف إلى
    # موانع التصدير القائمة (نص ناقص · متطلب حرج بلا تغطية) لا بديلاً عنها.
    may_export = auth.can("export")
    if not may_export:
        st.info(t("role.export_forbidden"))

    # 13-8: لا تصدير نهائي بلا اعتماد مسجَّل على المراجعة الحالية. مانع يُضاف
    # إلى موانع التصدير القائمة (نص ناقص · متطلب حرج بلا تغطية) لا بديلاً عنها.
    from utils import db as _db

    project_id = st.session_state.get("_project_id")
    approved = project_id is not None and _db.approvals_complete(project_id)
    if project_id is None:
        st.warning(t("ap.export_needs_project"))
    elif not approved:
        pending = _db.next_approval_stage(project_id)
        st.warning(t("ap.export_blocked", stage=t("ap.stage_" + pending)))

    blocked = (has_placeholders or not payload or bool(coverage["blocking"])
               or not may_export or not approved)

    col_w, col_p = st.columns(2)

    with col_w:
        if st.button(t("db.build_word"), type="primary", width="stretch", disabled=blocked):
            try:
                with st.spinner(t("db.building")):
                    bio = build_word_document(
                        company_name=company_name,
                        sections=payload,
                        template_bytes=st.session_state.get("c_word_template_bytes"),
                        df_compliance=st.session_state.get("df_compliance"),
                        df_boq=st.session_state.get("df_boq"),
                        df_timeline=st.session_state.get("df_timeline"),
                        include_toc=include_toc,
                        include_page_numbers=include_pageno,
                        rtl=is_rtl(_language()),
                        font_name=st.session_state.get("c_doc_font", ""),
                        **brand,
                    )
                st.session_state["_built_docx"] = bio.getvalue()
                audit.record(audit.EXPORT_BUILD, detail="docx")
                st.success(t("db.built_word"))
            except Exception as e:
                st.error(t("db.build_failed", error=e))
                import traceback
                st.code(traceback.format_exc())

    with col_p:
        if st.button(t("db.build_pdf"), type="primary", width="stretch", disabled=blocked):
            try:
                with st.spinner(t("db.building")):
                    bio = build_pdf_document(
                        company_name=company_name,
                        sections=payload,
                        df_compliance=st.session_state.get("df_compliance"),
                        df_boq=st.session_state.get("df_boq"),
                        df_timeline=st.session_state.get("df_timeline"),
                        include_toc=include_toc,
                        include_page_numbers=include_pageno,
                        rtl=is_rtl(_language()),
                        **brand,
                    )
                st.session_state["_built_pdf"] = bio.getvalue()
                audit.record(audit.EXPORT_BUILD, detail="pdf")
                st.success(t("db.built_pdf"))
            except ImportError as e:
                st.error(
                    t("db.pdf_missing_libs", error=e)
                    + "\n\n`pip install reportlab arabic-reshaper python-bidi`"
                )
            except Exception as e:
                st.error(t("db.build_failed", error=e))
                import traceback
                st.code(traceback.format_exc())

    dl1, dl2 = st.columns(2)
    with dl1:
        if st.session_state.get("_built_docx"):
            st.download_button(
                t("db.download_word"),
                data=st.session_state["_built_docx"],
                file_name=f"Technical_Proposal_{slug}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                width="stretch",
                key="dl_docx",
            )
    with dl2:
        if st.session_state.get("_built_pdf"):
            st.download_button(
                t("db.download_pdf"),
                data=st.session_state["_built_pdf"],
                file_name=f"Technical_Proposal_{slug}.pdf",
                mime="application/pdf",
                width="stretch",
                key="dl_pdf",
            )


# ─── نقطة الدخول ──────────────────────────────────────────────────────────────


def render():
    st.markdown(t("db.title"))
    _render_outline_designer()
    st.divider()
    sections = get_sections()
    _render_editors(sections)
    _render_export(sections)
