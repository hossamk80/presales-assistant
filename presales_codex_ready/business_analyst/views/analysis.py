"""
views/analysis.py — Tab 1: رفع المرفقات وتصنيفها + التحليل الذكي

تُحلَّل كل مرفقات المنافسة معاً (الكراسة، الملاحق الفنية، جداول الكميات)،
مع حفظ نص كل دور على حدة لتغذية التعليمات التي تميّز بينها.
"""
import streamlit as st

from utils.ai_engine import (
    DEFAULT_LANGUAGE,
    DEFAULT_MODEL,
    EXTRACT_PROMPTS,
    MODEL_NAMES,
    PROJECT_CONTEXT_SCHEMA,
    ai_generate,
    ai_generate_json,
    build_prompt,
    estimate_tokens,
    language_instruction,
)
from utils import db, history, knowledge
from utils.file_handler import extract_texts_per_file
from utils.i18n import t
from utils.state import (
    ATTACHMENT_ROLES,
    boq_scope_block,
    company_block,
    guess_attachment_role,
    project_context_block,
    role_text,
)
from components.ui import ai_generate_button


def _language() -> str:
    return st.session_state.get("output_language", DEFAULT_LANGUAGE)


# استعلام مستودع المعرفة عمّا يُثبت التأهيل — الشهادات والتصنيف والمشاريع
# المنفَّذة هي ما تسأل عنه لجنة التأهيل، لا نبذة الشركة العامة.
_QUALIFICATION_QUERY = (
    "الشهادات والتصنيف والتراخيص والمشاريع السابقة المنفَّذة وخبرات الفريق"
)


def _qualification_context() -> str:
    """
    ما يحتاجه قرار الخوض ليكون عن **هذه الشركة**: ملفها، وما يثبت تأهيلها من
    مستودع المعرفة، وقيود المنافسة، ونطاق العمل من جدول الكميات.
    """
    parts = [
        company_block(),
        knowledge.build_context(_QUALIFICATION_QUERY),
        project_context_block(),
        boq_scope_block(),
        _history_block(),
    ]
    return "\n\n".join(p for p in parts if p)


def _history_block() -> str:
    """
    دروس المنافسات السابقة المشابهة — سوابقك أنت لا بيانات سوقية.

    خسارتان مع نفس الجهة بسبب المحتوى المحلي معلومة تغيّر قرار الخوض، وكانت
    محفوظة في قاعدة البيانات بلا من يقرأها.
    """
    pid = st.session_state.get("_project_id")
    if pid is None:
        return ""
    try:
        projects = db.list_projects()
    except Exception:
        return ""

    current = next((p for p in projects if p["id"] == pid), None)
    if current is None:
        return ""
    return history.lessons_block(history.similar_projects(
        projects, current["name"], current.get("entity", ""), exclude_id=pid,
    ))


def _rebuild_combined_text():
    """يعيد بناء النص المدموج من المرفقات وأدوارها الحالية."""
    texts = st.session_state.get("attachment_texts") or {}
    roles = st.session_state.get("attachment_roles") or {}
    parts = [
        f"\n\n=== {name} [{ATTACHMENT_ROLES.get(roles.get(name, 'other'))}] ===\n{text}"
        for name, text in texts.items()
    ]
    st.session_state["rfp_raw_text"] = "\n".join(parts).strip()
    st.session_state["rfp_file_names"] = list(texts)


def _render_upload():
    st.markdown(t("an.upload_title"))

    col_upload, col_clear = st.columns([4, 1])
    with col_upload:
        files = st.file_uploader(
            t("an.formats"),
            accept_multiple_files=True,
            label_visibility="collapsed",
        )
    with col_clear:
        if st.session_state.get("rfp_raw_text") and st.button(f"🗑️ {t('common.clear')}", width="stretch"):
            from utils.state import reset_analysis
            reset_analysis()
            st.rerun()

    if st.button(t("an.extract"), type="primary", disabled=not files):
        with st.spinner(t("common.extracting")):
            per_file = extract_texts_per_file(files)
        per_file = {name: text for name, text in per_file.items() if text.strip()}
        if not per_file:
            st.error(t("an.extract_failed"))
            return

        texts = dict(st.session_state.get("attachment_texts") or {})
        roles = dict(st.session_state.get("attachment_roles") or {})
        for name, text in per_file.items():
            texts[name] = text
            roles.setdefault(name, guess_attachment_role(name))
        st.session_state["attachment_texts"] = texts
        st.session_state["attachment_roles"] = roles
        _rebuild_combined_text()
        st.rerun()


def _render_attachment_roles():
    """جدول المرفقات مع دور كل ملف — مُرجَّح تلقائياً وقابل للتعديل."""
    texts = st.session_state.get("attachment_texts") or {}
    if not texts:
        return

    roles = dict(st.session_state.get("attachment_roles") or {})
    total_tokens = estimate_tokens(st.session_state.get("rfp_raw_text", ""))

    with st.expander(
        f"{t('an.attachments', n=len(texts))} · {t('an.tokens_est', n=f'{total_tokens:,}')}",
        expanded=True,
    ):
        st.caption(t("an.role_hint"))
        role_keys = list(ATTACHMENT_ROLES)
        changed = False

        for name in list(texts):
            c_name, c_role, c_del = st.columns([5, 3, 1])
            with c_name:
                st.markdown(
                    f"**{name}**<br><span style='color:#64748B;font-size:12px'>"
                    f"{t('an.chars', n=f'{len(texts[name]):,}')}</span>",
                    unsafe_allow_html=True,
                )
            with c_role:
                current = roles.get(name, "rfp")
                picked = st.selectbox(
                    t("an.role"),
                    role_keys,
                    index=role_keys.index(current) if current in role_keys else 0,
                    format_func=lambda k: t(f"role.{k}"),
                    key=f"role_{name}",
                    label_visibility="collapsed",
                )
                if picked != current:
                    roles[name] = picked
                    changed = True
            with c_del:
                if st.button("🗑️", key=f"delatt_{name}", width="stretch"):
                    texts.pop(name, None)
                    roles.pop(name, None)
                    st.session_state["attachment_texts"] = texts
                    st.session_state["attachment_roles"] = roles
                    _rebuild_combined_text()
                    st.rerun()

        if changed:
            st.session_state["attachment_roles"] = roles
            _rebuild_combined_text()
            st.rerun()


def _render_project_context():
    """دمج المرفقات في سياق معرفي واحد مُهيكل للمشروع."""
    ctx = st.session_state.get("project_context") or {}

    with st.expander(t("an.context_title"), expanded=not ctx):
        c_model, c_btn = st.columns([3, 2])
        with c_model:
            current = st.session_state.get("ai_model_preference", DEFAULT_MODEL)
            model = st.selectbox(
                t("common.engine"),
                MODEL_NAMES,
                index=MODEL_NAMES.index(current) if current in MODEL_NAMES else 0,
                key="model_context",
                label_visibility="collapsed",
            )
        with c_btn:
            run = st.button(t("an.context_run"), type="primary", width="stretch")

        if run:
            status = st.empty()
            annexes = role_text("annex")
            prompt = (
                EXTRACT_PROMPTS["project_context"]
                + f"\n{language_instruction(_language())}"
                + (f"\n\n--- الملاحق الفنية ---\n{annexes}" if annexes else "")
            )
            with st.spinner(t("an.context_merging")):
                result = ai_generate_json(
                    prompt,
                    schema=PROJECT_CONTEXT_SCHEMA,
                    model_choice=model,
                    rfp_context=role_text("rfp") or st.session_state.get("rfp_raw_text", ""),
                    on_progress=lambda m: status.caption(f"⏳ {m}"),
                )
            status.empty()
            if isinstance(result, dict) and result:
                st.session_state["project_context"] = result
                st.rerun()

        if not ctx:
            st.info(t("an.context_hint"))
            return

        c1, c2, c3 = st.columns(3)
        c1.metric(t("an.entity"), ctx.get("issuing_entity") or t("common.none"))
        c2.metric(t("an.deadline"), ctx.get("submission_deadline") or t("common.none"))
        c3.metric(t("an.certs_count"), len(ctx.get("required_certifications") or []))

        st.markdown(f"**{ctx.get('project_title', '')}**")
        if ctx.get("scope_summary"):
            st.write(ctx["scope_summary"])

        lists = [
            (t("an.deliverables"), "key_deliverables"),
            (t("an.constraints"), "technical_constraints"),
            (t("an.penalties"), "contractual_penalties"),
            (t("an.certs"), "required_certifications"),
        ]
        for label, key in lists:
            values = ctx.get(key) or []
            if values:
                st.markdown(f"**{label}**")
                for v in values:
                    st.markdown(f"- {v}")

        if ctx.get("local_content_requirements"):
            st.info(f"{t('an.local_content')} {ctx['local_content_requirements']}")


def render():
    _render_upload()

    if not st.session_state.get("rfp_raw_text"):
        st.info(t("an.start_hint"))
        return

    _render_attachment_roles()
    st.divider()
    _render_project_context()

    # ── Section 1: Go/No-Go ────────────────────────────────────────────────────
    with st.expander(t("an.gonogo"), expanded=True):
        # قرار خوض بلا ملف شركة يعود حكماً على المنافسة في المطلق — نقولها
        # قبل التشغيل لا بعده.
        if not company_block():
            st.warning(t("an.gonogo_no_company"))
        st.caption(t("an.gonogo_hint"))

        ai_generate_button(
            label=t("an.gonogo_btn"),
            key="gonogo",
            model_key="m1",
            on_generate=lambda model, report: ai_generate(
                build_prompt("gonogo", _language()),
                model_choice=model,
                rfp_context=st.session_state["rfp_raw_text"],
                extra_context=_qualification_context(),
                on_progress=report,
                language=_language(),
            ),
            result_state_key="analysis_gonogo",
            summary_state_key="sum_gonogo",
            summary_label=t("an.gonogo_note"),
            result_style="info",
        )

    # ── Section 2: Evaluation Matrix ──────────────────────────────────────────
    with st.expander(t("an.eval")):
        ai_generate_button(
            label=t("an.eval_btn"),
            key="eval",
            model_key="m2",
            on_generate=lambda model, report: ai_generate(
                build_prompt("eval_matrix", _language()),
                model_choice=model,
                rfp_context=st.session_state["rfp_raw_text"],
                on_progress=report,
                language=_language(),
            ),
            result_state_key="evaluation_matrix",
            summary_state_key="sum_eval",
            summary_label=t("an.eval_note"),
            result_style="success",
        )

    # ── Section 3: Compliance Check ───────────────────────────────────────────
    with st.expander(t("an.comp")):
        ai_generate_button(
            label=t("an.comp_btn"),
            key="compliance",
            model_key="m3",
            on_generate=lambda model, report: ai_generate(
                build_prompt("compliance", _language()),
                model_choice=model,
                rfp_context=st.session_state["rfp_raw_text"],
                on_progress=report,
                language=_language(),
            ),
            result_state_key="compliance_check",
            summary_state_key="sum_comp",
            summary_label=t("an.comp_note"),
            result_style="warning",
        )

    # ── Raw Text Preview ───────────────────────────────────────────────────────
    with st.expander(t("an.preview")):
        raw = st.session_state["rfp_raw_text"]
        truncated = "\n\n" + t("an.truncated") if len(raw) > 5000 else ""
        st.code(raw[:5000] + truncated, language=None)
