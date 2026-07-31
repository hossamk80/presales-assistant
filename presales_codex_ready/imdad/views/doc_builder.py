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
    OUTLINE_SCHEMA,
    PROMPTS,
    ai_generate,
    ai_generate_json,
    build_prompt,
    is_rtl,
    language_instruction,
)
from utils.file_handler import build_pdf_document, build_word_document
from utils.state import get_sections, reset_sections, section_content_key, set_sections

PLACEHOLDER_RE = re.compile(r"\[.+?\]")


def _has_placeholders(*texts) -> bool:
    return any(PLACEHOLDER_RE.search(str(t)) for t in texts)


def _model_picker(key: str) -> str:
    current = st.session_state.get("ai_model_preference", DEFAULT_MODEL)
    return st.selectbox(
        "المحرك:",
        MODEL_NAMES,
        index=MODEL_NAMES.index(current) if current in MODEL_NAMES else 0,
        key=key,
        label_visibility="collapsed",
    )


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

    with st.expander("🗂️ هيكل العرض الفني", expanded=True):
        st.caption(
            f"المصدر الحالي: **{st.session_state.get('outline_source', 'افتراضي')}** · "
            f"{len(sections)} قسم · {sum(1 for s in sections if s.get('include'))} مُدرَج"
        )

        rfp = st.session_state.get("rfp_raw_text", "")
        col_model, col_gen, col_reset = st.columns([2, 2, 1])
        with col_model:
            model = _model_picker("model_outline")
        with col_gen:
            propose = st.button(
                "🤖 اقترح هيكلاً من الكراسة",
                type="primary",
                width="stretch",
                disabled=not rfp,
                help=None if rfp else "ارفع كراسة الشروط أولاً من التبويب الأول.",
            )
        with col_reset:
            if st.button("↩️ الافتراضي", width="stretch"):
                reset_sections()
                st.rerun()

        if propose:
            status = st.empty()
            with st.spinner("جاري اقتراح الهيكل..."):
                result = ai_generate_json(
                    EXTRACT_PROMPTS["outline"] + f"\n{language_instruction(_language())}",
                    schema=OUTLINE_SCHEMA,
                    model_choice=model,
                    rfp_context=rfp,
                    merge_key="sections",
                    on_progress=lambda m: status.caption(f"⏳ {m}"),
                )
            status.empty()
            proposed = (result or {}).get("sections") or []
            if proposed:
                _apply_proposed_outline(proposed)
                st.rerun()
            elif result is not None:
                st.warning("⚠️ لم يقترح النموذج أي أقسام.")

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
    for item in proposed:
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        # أعِد استخدام مفتاح قسم قائم بنفس العنوان حتى لا يضيع نصّه المكتوب
        match = next(
            (s for s in existing if s["kind"] == "ai" and s["title"].strip() == title),
            None,
        )
        key = match["key"] if match and match["key"] not in taken else _slugify_key(title, taken)
        taken.add(key)
        body.append({
            "key": key,
            "title": title,
            "kind": "ai",
            "include": str(item.get("priority", "")) != "منخفضة",
            "guidance": str(item.get("guidance", "")).strip(),
            "rationale": str(item.get("rationale", "")).strip(),
            "priority": str(item.get("priority", "متوسطة")),
            "prompt_key": (by_key.get(key) or {}).get("prompt_key"),
        })

    set_sections(head + body + tail, source="مقترح من الكراسة")
    st.success(f"✅ اقتُرح هيكل من **{len(body)}** قسماً. راجعه وعدّله قبل الصياغة.")


def _render_section_list(sections: list):
    """قائمة الأقسام مع الإدراج والترتيب والحذف."""
    st.markdown("**الأقسام** — رتّبها واختر ما يُدرَج في المستند النهائي:")

    changed = False
    for i, sec in enumerate(sections):
        c_inc, c_title, c_up, c_down, c_del = st.columns([1, 8, 1, 1, 1])

        with c_inc:
            new_inc = st.checkbox(
                "إدراج",
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
            prio = f" · أولوية {sec['priority']}" if sec.get("priority") else ""
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
                "عنوان قسم جديد", placeholder="مثال: خطة نقل المعرفة", label_visibility="collapsed"
            )
        with c2:
            if st.form_submit_button("➕ أضف قسماً", width="stretch") and new_title.strip():
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

    return build_prompt(
        "section", lang,
        title=sec["title"],
        guidance=sec.get("guidance") or "غطِّ ما تقتضيه طبيعة هذا القسم في عرض فني حكومي.",
        company_overview=company,
        eval_weights=eval_weights,
        compliance_summary=compliance,
    )


def _kb_context(sec: dict) -> str:
    """يسترجع من مستودع معرفة الشركة ما يخص هذا القسم تحديداً."""
    if not knowledge.is_populated() or not st.session_state.get("api_gemini"):
        return ""
    query = " ".join(filter(None, [sec.get("title"), sec.get("guidance")]))
    return knowledge.build_context(query)


def _project_context_block() -> str:
    """
    سياق المشروع الموحّد (الجهة، الموعد، التسليمات، الغرامات، المحتوى المحلي).

    يُحقن في تعليمات كل قسم ليكتب النموذج بمعرفة قيود المنافسة الفعلية بدل
    استنتاجها من نص الكراسة الخام في كل مرة.
    """
    ctx = st.session_state.get("project_context") or {}
    if not ctx:
        return ""

    lines = []
    for label, key in (
        ("المشروع", "project_title"),
        ("الجهة المصدِرة", "issuing_entity"),
        ("الموعد النهائي", "submission_deadline"),
        ("ملخص النطاق", "scope_summary"),
        ("متطلبات المحتوى المحلي", "local_content_requirements"),
    ):
        value = str(ctx.get(key, "")).strip()
        if value:
            lines.append(f"{label}: {value}")

    for label, key in (
        ("التسليمات الرئيسية", "key_deliverables"),
        ("القيود الفنية", "technical_constraints"),
        ("الغرامات التعاقدية", "contractual_penalties"),
        ("الشهادات المطلوبة", "required_certifications"),
    ):
        values = ctx.get(key) or []
        if values:
            lines.append(f"{label}: " + " · ".join(str(v) for v in values))

    if not lines:
        return ""
    return "\n\n--- سياق المشروع الموحّد ---\n" + "\n".join(lines)


def _render_editors(sections: list):
    st.markdown("### ✍️ محررات الأقسام")

    included = [s for s in sections if s.get("include")]
    if not included:
        st.info("لم تختر أي قسم بعد. فعّل الأقسام من قائمة الهيكل أعلاه.")
        return

    for sec in included:
        if sec["kind"] == "docinfo":
            continue

        if sec["kind"] == "table_compliance":
            df = st.session_state.get("df_compliance")
            n = 0 if df is None else len(df)
            st.caption(f"📋 **{sec['title']}** — يُحقن من التبويب الثاني ({n} صف).")
            continue

        if sec["kind"] == "table_boq":
            df = st.session_state.get("df_boq")
            n = 0 if df is None else len(df)
            st.caption(f"📦 **{sec['title']}** — يُحقن من التبويب الثاني ({n} صف).")
            continue

        if sec["kind"] == "cover":
            _render_cover_editor(sec)
            continue

        _render_ai_editor(sec)


def _render_cover_editor(sec: dict):
    with st.expander(f"✉️ {sec['title']}", expanded=False):
        use_template = st.radio(
            "طريقة الإعداد:",
            ["قالب ثابت (من ملف الشركة)", "توليد ديناميكي (AI)"],
            key="cover_type_radio",
        )
        st.session_state["sec_cover_use_template"] = use_template.startswith("قالب ثابت")

        if st.session_state["sec_cover_use_template"]:
            st.info(
                "سيُستخدم القالب المحفوظ في **ملف الشركة**:\n\n"
                f"{st.session_state.get('c_cover_template', '')[:300]}"
            )
            return

        col_m, col_b = st.columns([3, 1])
        with col_m:
            model = _model_picker("model_cover")
        with col_b:
            go = st.button("⚡ توليد الخطاب", key="btn_cover", type="primary", width="stretch")
        if go:
            with st.spinner("جاري التوليد..."):
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
            "نص الخطاب",
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
        if sec.get("guidance"):
            st.caption(f"يغطي: {sec['guidance']}")

        col_m, col_b = st.columns([3, 1])
        with col_m:
            model = _model_picker(f"model_{key}")
        with col_b:
            go = st.button("⚡ توليد", key=f"btn_{key}", type="primary", width="stretch")

        if go:
            status = st.empty()
            with st.spinner("جاري التوليد..."):
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

        st.session_state[ckey] = st.text_area(
            "النص (قابل للتحرير)",
            value=content,
            height=300,
            key=f"ta_{key}",
        )

        if _has_placeholders(st.session_state[ckey]):
            st.warning("⚠️ يحتوي هذا القسم على نص نائب بين [ ] يحتاج تعبئة.")


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
    st.markdown("### 📥 مراجعة وتصدير العرض الفني")

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
    c1.metric("ملف الشركة", "✅" if st.session_state.get("c_name") else "❌")
    c2.metric("تحليل الكراسة", "✅" if st.session_state.get("rfp_raw_text") else "❌")
    c3.metric("أقسام مكتوبة", f"{len(text_items) - len(empty_sections)} / {len(text_items)}")
    c4.metric("لا يوجد نص ناقص", "✅" if not has_placeholders else "❌")

    if empty_sections:
        st.warning("📝 أقسام مُدرَجة وفارغة: " + " · ".join(empty_sections))
    if placeholder_sections:
        details = "\n".join(
            f"- **{title}**: {' · '.join(marks)}"
            for title, marks in placeholder_sections.items()
        )
        st.error(
            "🚨 يوجد نص بين أقواس [ ] يحتاج تعبئة يدوية قبل التصدير:\n\n" + details
        )

    if st.session_state.get("c_word_template_bytes"):
        st.success("✅ سيتم الحقن داخل قالب الشركة الرسمي (Word).")
    else:
        st.info("💡 لا يوجد قالب مخصص. سيُصدَّر كمستند قياسي. (أضف قالباً في **ملف الشركة**).")

    opt1, opt2 = st.columns(2)
    with opt1:
        include_toc = st.checkbox("إدراج فهرس المحتويات", value=True, key="exp_toc")
    with opt2:
        include_pageno = st.checkbox("ترقيم الصفحات", value=True, key="exp_pageno")

    company_name = st.session_state.get("c_name", "")
    slug = (company_name or "Proposal").replace(" ", "_")[:20]
    blocked = has_placeholders or not payload

    col_w, col_p = st.columns(2)

    with col_w:
        if st.button("📄 بناء ملف Word", type="primary", width="stretch", disabled=blocked):
            try:
                with st.spinner("جاري بناء المستند..."):
                    bio = build_word_document(
                        company_name=company_name,
                        sections=payload,
                        template_bytes=st.session_state.get("c_word_template_bytes"),
                        df_compliance=st.session_state.get("df_compliance"),
                        df_boq=st.session_state.get("df_boq"),
                        include_toc=include_toc,
                        include_page_numbers=include_pageno,
                        rtl=is_rtl(_language()),
                    )
                st.session_state["_built_docx"] = bio.getvalue()
                st.success("✅ تم بناء ملف Word.")
            except Exception as e:
                st.error(f"❌ فشل بناء المستند: {e}")
                import traceback
                st.code(traceback.format_exc())

    with col_p:
        if st.button("📕 بناء ملف PDF", type="primary", width="stretch", disabled=blocked):
            try:
                with st.spinner("جاري بناء الـ PDF..."):
                    bio = build_pdf_document(
                        company_name=company_name,
                        sections=payload,
                        df_compliance=st.session_state.get("df_compliance"),
                        df_boq=st.session_state.get("df_boq"),
                        include_toc=include_toc,
                        include_page_numbers=include_pageno,
                        rtl=is_rtl(_language()),
                    )
                st.session_state["_built_pdf"] = bio.getvalue()
                st.success("✅ تم بناء ملف PDF.")
            except ImportError as e:
                st.error(
                    f"❌ مكتبات الـ PDF غير مثبّتة: {e}\n\n"
                    "شغّل: `pip install reportlab arabic-reshaper python-bidi`"
                )
            except Exception as e:
                st.error(f"❌ فشل بناء الـ PDF: {e}")
                import traceback
                st.code(traceback.format_exc())

    dl1, dl2 = st.columns(2)
    with dl1:
        if st.session_state.get("_built_docx"):
            st.download_button(
                "⬇️ تحميل Word",
                data=st.session_state["_built_docx"],
                file_name=f"Technical_Proposal_{slug}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                width="stretch",
                key="dl_docx",
            )
    with dl2:
        if st.session_state.get("_built_pdf"):
            st.download_button(
                "⬇️ تحميل PDF",
                data=st.session_state["_built_pdf"],
                file_name=f"Technical_Proposal_{slug}.pdf",
                mime="application/pdf",
                width="stretch",
                key="dl_pdf",
            )


# ─── نقطة الدخول ──────────────────────────────────────────────────────────────


def render():
    st.markdown("### 📄 منشئ العرض الفني")
    _render_outline_designer()
    st.divider()
    sections = get_sections()
    _render_editors(sections)
    _render_export(sections)
