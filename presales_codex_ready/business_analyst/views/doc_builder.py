"""
views/doc_builder.py — Tab 3: منشئ العرض الفني

الهيكل ديناميكي: إمّا الهيكل الافتراضي أو هيكل يقترحه الذكاء الاصطناعي من
كراسة الشروط. كل قسم قابل للتوليد والتحرير والحذف وإعادة الترتيب.
"""
import re
import streamlit as st

from utils import knowledge
from utils.ai_engine import (
    DEFAULT_LANGUAGE,
    DEFAULT_MODEL,
    EXTRACT_PROMPTS,
    MODEL_NAMES,
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
from utils.file_handler import BRAND_COLOR, build_pdf_document, build_word_document
from utils.i18n import t
from utils.state import (
    get_sections,
    project_context_block as _project_context_block,
    reset_sections,
    section_content_key,
    set_sections,
)

PLACEHOLDER_RE = re.compile(r"\[.+?\]")


def _has_placeholders(*texts) -> bool:
    return any(PLACEHOLDER_RE.search(str(x)) for x in texts)


def _model_picker(key: str) -> str:
    current = st.session_state.get("ai_model_preference", DEFAULT_MODEL)
    return st.selectbox(
        t("common.engine"),
        MODEL_NAMES,
        index=MODEL_NAMES.index(current) if current in MODEL_NAMES else 0,
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
                disabled=not rfp,
                help=None if rfp else t("db.propose_hint"),
            )
        with col_reset:
            if st.button(f"↩️ {t('common.default')}", width="stretch"):
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
                    extra_context=_project_context_block(),
                    merge_key="outline",
                    on_progress=lambda m: status.caption(f"⏳ {m}"),
                )
            status.empty()
            proposed = (result or {}).get("outline") or []
            if isinstance(result, dict) and result.get("proposal_title"):
                st.session_state["proposal_title"] = str(result["proposal_title"]).strip()
            if proposed:
                _apply_proposed_outline(proposed)
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
    tail = [s for s in existing if s["kind"] in ("table_compliance", "table_boq")]

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
        })

    set_sections(head + body + tail, source="proposed")
    st.success(t("db.proposed", n=len(body)))


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
        "مؤهلات الشركة والخبرات السابقة": ["مؤهل", "خبرا", "خبرة"],
        "المنهجية والنهج الفني": ["منهج"],
        "خطة العمل والجدول الزمني": ["خطة", "الجدول الزمني"],
        "هيكل الفريق والحوكمة": ["فريق", "حوكم"],
        "إدارة الجودة ومستويات الخدمة": ["جودة", "مستويات الخدمة", "SLA"],
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
                f"<span style='color:#64748B;font-size:12px'>{prio}</span>",
                unsafe_allow_html=True,
            )

        with c_up:
            if st.button("⬆️", key=f"up_{sec['key']}", disabled=i == 0):
                sections[i - 1], sections[i] = sections[i], sections[i - 1]
                set_sections(sections)
                st.rerun()
        with c_down:
            if st.button("⬇️", key=f"dn_{sec['key']}", disabled=i == len(sections) - 1):
                sections[i + 1], sections[i] = sections[i], sections[i + 1]
                set_sections(sections)
                st.rerun()
        with c_del:
            if st.button("🗑️", key=f"del_{sec['key']}", disabled=sec["kind"] != "ai"):
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
    if not knowledge.is_populated() or not st.session_state.get("api_gemini"):
        return ""
    query = " ".join(filter(None, [sec.get("title"), sec.get("guidance")]))
    return knowledge.build_context(query)


def _render_editors(sections: list):
    st.markdown(t("db.editors"))

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
            go = st.button(t("db.cover_generate"), key="btn_cover", type="primary", width="stretch")
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
        )


def _render_ai_editor(sec: dict):
    key = sec["key"]
    ckey = section_content_key(key)
    content = st.session_state.get(ckey, "")
    icon = "🟢" if content.strip() else "⚪"

    with st.expander(f"{icon} {sec['title']}", expanded=False):
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
            go = st.button(f"⚡ {t('common.generate')}", key=f"btn_{key}", type="primary", width="stretch")

        if go:
            status = st.empty()
            with st.spinner(t("common.generating")):
                out = ai_generate(
                    _section_prompt(sec),
                    model_choice=model,
                    rfp_context=st.session_state.get("rfp_raw_text", ""),
                    on_progress=lambda m: status.caption(f"⏳ {m}"),
                    extra_context=_project_context_block() + _kb_context(sec),
                    language=_language(),
                )
            status.empty()
            if out:
                st.session_state[ckey] = out
                # نُبطل مفتاح المحرر ليعرض النص المولَّد الجديد
                st.session_state.pop(f"ta_{key}", None)
                st.rerun()

        # توجيه الكتابة يُحفظ مع المنافسة ويُمرَّر للنموذج عند التوليد
        st.text_area(
            t("db.steering"),
            height=80,
            placeholder=t("db.steering_ph"),
            key=_steering_key(key),
        )

        st.session_state[ckey] = st.text_area(
            t("db.section_text"),
            value=content,
            height=300,
            key=f"ta_{key}",
        )

        if _has_placeholders(st.session_state[ckey]):
            st.warning(t("db.placeholder_warn"))

        _render_side_assistant(sec, model)


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
                if st.button(label, key=f"quick_{qkey}_{key}", width="stretch"):
                    _apply_refinement(sec, label, model)
                    st.rerun()

        c_req, c_btn = st.columns([4, 1])
        with c_req:
            request = st.text_input(
                t("db.assistant"),
                placeholder=t("db.assistant_ph"),
                key=f"refine_req_{key}",
                label_visibility="collapsed",
            )
        with c_btn:
            go = st.button(t("db.refine"), key=f"refine_{key}",
                           type="primary", width="stretch")

        if go and request.strip():
            _apply_refinement(sec, request.strip(), model)
            st.rerun()

        undo_key = f"_undo_{ckey}"
        if st.session_state.get(undo_key):
            if st.button(f"↩️ {t('common.undo')}", key=f"undo_refine_{key}"):
                st.session_state[ckey] = st.session_state.pop(undo_key)
                st.session_state.pop(f"ta_{key}", None)
                st.rerun()


def _apply_refinement(sec: dict, request: str, model: str):
    """ينفّذ طلب التنقيح على نص القسم مع حفظ نسخة للتراجع."""
    ckey = section_content_key(sec["key"])
    current = st.session_state.get(ckey, "")

    with st.spinner(t("db.refining")):
        revised = ai_generate(
            build_prompt("refine", _language(), content=current, edit_request=request),
            model_choice=model,
            language=_language(),
        )
    if not revised:
        return

    st.session_state[f"_undo_{ckey}"] = current
    st.session_state[ckey] = revised
    st.session_state.pop(f"ta_{sec['key']}", None)


# ─── التصدير ──────────────────────────────────────────────────────────────────


def _collect_export_payload(sections: list) -> list:
    """يبني قائمة الأقسام المُدرَجة بمحتواها النهائي، جاهزة للبنّاء."""
    payload = []
    for sec in sections:
        if not sec.get("include"):
            continue
        item = {"key": sec["key"], "title": sec["title"], "kind": sec["kind"], "content": ""}

        if sec["kind"] == "cover":
            item["content"] = (
                st.session_state.get("c_cover_template", "")
                if st.session_state.get("sec_cover_use_template", True)
                else st.session_state.get("sec_cover", "")
            )
        elif sec["kind"] == "docinfo":
            company = st.session_state.get("c_name", "")
            item["content"] = (
                "هذا المستند سري للغاية ومُعدّ حصرياً للجهة المُرسَل إليها.\n"
                f"الشركة المُقدِّمة: {company}\n"
                "يُحظر توزيع هذا المستند أو إعادة إنتاجه دون إذن كتابي مسبق."
            )
        elif sec["kind"] == "ai":
            item["content"] = st.session_state.get(section_content_key(sec["key"]), "")

        payload.append(item)
    return payload


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

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("db.chk_company"), "✅" if st.session_state.get("c_name") else "❌")
    c2.metric(t("db.chk_rfp"), "✅" if st.session_state.get("rfp_raw_text") else "❌")
    c3.metric(t("db.chk_written"), f"{len(text_items) - len(empty_sections)} / {len(text_items)}")
    c4.metric(t("db.chk_placeholders"), "✅" if not has_placeholders else "❌")

    if empty_sections:
        st.warning(t("db.empty_sections") + " · ".join(empty_sections))
    if placeholder_sections:
        details = "\n".join(
            f"- **{title}**: {' · '.join(marks)}"
            for title, marks in placeholder_sections.items()
        )
        st.error(t("db.placeholders_found") + "\n\n" + details)

    if st.session_state.get("c_word_template_bytes"):
        st.success(t("db.template_on"))
    else:
        st.info(t("db.template_off"))

    opt1, opt2 = st.columns(2)
    with opt1:
        include_toc = st.checkbox(t("db.opt_toc"), value=True, key="exp_toc")
    with opt2:
        include_pageno = st.checkbox(t("db.opt_pageno"), value=True, key="exp_pageno")

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
    blocked = has_placeholders or not payload

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
                        include_toc=include_toc,
                        include_page_numbers=include_pageno,
                        rtl=is_rtl(_language()),
                        font_name=st.session_state.get("c_doc_font", ""),
                        **brand,
                    )
                st.session_state["_built_docx"] = bio.getvalue()
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
                        include_toc=include_toc,
                        include_page_numbers=include_pageno,
                        rtl=is_rtl(_language()),
                        **brand,
                    )
                st.session_state["_built_pdf"] = bio.getvalue()
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
