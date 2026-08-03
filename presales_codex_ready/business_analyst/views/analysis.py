"""
views/analysis.py — Tab 1: رفع المرفقات وتصنيفها + التحليل الذكي

تُحلَّل كل مرفقات المنافسة معاً (الكراسة، الملاحق الفنية، جداول الكميات)،
مع حفظ نص كل دور على حدة لتغذية التعليمات التي تميّز بينها.
"""
import streamlit as st

from utils.ai_engine import (
    DEFAULT_LANGUAGE,
    EXTRACT_PROMPTS,
    PROJECT_CONTEXT_SCHEMA,
    ai_generate,
    ai_generate_json,
    build_prompt,
    estimate_tokens,
    language_instruction,
)
from utils import (
    auth,
    addenda, boq_parser, db, history, knowledge, savings, submission, textprep,
)
from utils.file_handler import extract_texts_per_file
from utils.i18n import t
from utils.state import (
    ATTACHMENT_ROLES,
    DEFAULT_BOQ_DF,
    boq_scope_block,
    company_block,
    entity_block,
    guess_attachment_role,
    project_context_block,
    records_block,
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
        # 12-6: الصفوف الموثّقة تسبق مستودع المعرفة — «نعم + المستند» يخرج من
        # صفٍّ لا من نص حر، وما لا صف له يبقى «غير معلوم».
        records_block(),
        entity_block(),
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


def _clean_attachments(per_file: dict) -> list:
    """
    ينظّف نصوص المرفقات ويُسقط المكرّر منها **قبل** أي استدعاء نموذج.

    ترويسة تتكرّر في كل صفحة وأرقام الصفحات والفهرس تُدفع توكناً في كل
    استدعاء بلا أن تضيف متطلباً واحداً. التنظيف حسابي بسقف أمان: تجاوزه
    يعني أن الكشف أخطأ فيُعاد النص الأصلي كما هو.
    """
    notices = []
    for name, text in list(per_file.items()):
        cleaned, stats = textprep.clean(text)
        per_file[name] = cleaned
        savings.record(savings.METHOD_CLEANUP, stats["before"], stats["after"])
        if stats["reverted"]:
            notices.append(t("an.clean_reverted", name=name))
        elif stats["saved"]:
            notices.append(t("an.clean_saved", name=name,
                             pct=round(stats["ratio"] * 100)))

    kept, dropped = textprep.dedupe_attachments(per_file)
    if dropped:
        for name in list(per_file):
            if name not in kept:
                savings.record(savings.METHOD_DEDUPE,
                               len(per_file[name]), 0, avoided_call=False)
        per_file.clear()
        per_file.update(kept)
        notices.append(t("an.dedupe_dropped", files=" · ".join(dropped)))
    return notices


def _try_local_boq(files) -> str:
    """
    يقرأ جدول الكميات من ملف Excel/CSV حسابياً — فيُوفَّر استدعاء النموذج كاملاً.

    لا يُطبَّق إلا على جدول لم يُحرَّر بعد: قراءة آلية تمحو تعديلات المستخدم
    أسوأ من استدعاء يُنفق توكناً. والفشل رجوع صامت إلى مسار النموذج.
    """
    current = st.session_state.get("df_boq")
    edited = current is not None and not current.equals(DEFAULT_BOQ_DF)
    if edited:
        return ""

    for file in files or []:
        name = getattr(file, "name", "")
        if not name.lower().endswith((".xlsx", ".xls", ".csv")):
            continue
        parsed, report = boq_parser.parse_file(file)
        if parsed is None or report.get("rows", 0) < 1:
            continue
        st.session_state["df_boq"] = parsed
        st.session_state.pop("de_boq", None)
        savings.record(savings.METHOD_LOCAL_PARSE,
                       len(str(parsed)), 0, avoided_call=True)
        return t("an.boq_local", name=name, n=report["rows"])
    return ""


def _render_upload():
    st.markdown(t("an.upload_title"))

    # 13-3: المراجع والمطّلع يقرآن المنافسة ولا يرفعان لها مرفقات
    if auth.blocked("projects.edit"):
        st.info(t("role.project_read_only"))

    col_upload, col_clear = st.columns([4, 1])
    with col_upload:
        files = st.file_uploader(
            t("an.formats"),
            accept_multiple_files=True,
            label_visibility="collapsed",
            disabled=auth.blocked("projects.edit"),
        )
    with col_clear:
        if st.session_state.get("rfp_raw_text") and st.button(
            f"🗑️ {t('common.clear')}", width="stretch",
            disabled=auth.blocked("projects.edit"),
        ):
            from utils.state import reset_analysis
            reset_analysis()
            st.rerun()

    if st.button(t("an.extract"), type="primary",
                 disabled=not files or auth.blocked("projects.edit")):
        with st.spinner(t("common.extracting")):
            per_file = extract_texts_per_file(files)
        per_file = {name: text for name, text in per_file.items() if text.strip()}
        if not per_file:
            st.error(t("an.extract_failed"))
            return

        # معالجة محلية قبل أي استدعاء: تنظيف · إسقاط المكرّر · قراءة الكميات
        notices = _clean_attachments(per_file)
        boq_notice = _try_local_boq(files)
        if boq_notice:
            notices.append(boq_notice)
        st.session_state["_ingest_notices"] = notices

        texts = dict(st.session_state.get("attachment_texts") or {})
        roles = dict(st.session_state.get("attachment_roles") or {})
        for name, text in per_file.items():
            texts[name] = text
            roles.setdefault(name, guess_attachment_role(name))
        st.session_state["attachment_texts"] = texts
        st.session_state["attachment_roles"] = roles
        _rebuild_combined_text()
        _snapshot_version()
        st.rerun()

    for notice in st.session_state.pop("_ingest_notices", []) or []:
        st.caption(notice)


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
                if st.button("🗑️", key=f"delatt_{name}", width="stretch",
                             disabled=auth.blocked("projects.edit")):
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
            from utils.ai_engine import default_model_name, model_names

            options = model_names()
            current = default_model_name()
            model = st.selectbox(
                t("common.engine"),
                options,
                index=options.index(current) if current in options else 0,
                key="model_context",
                label_visibility="collapsed",
            )
        with c_btn:
            run = st.button(t("an.context_run"), type="primary", width="stretch",
                            disabled=auth.blocked("projects.edit"))

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


# ─── الملاحق والتعديلات ───────────────────────────────────────────────────────


def _snapshot_version():
    """
    يحفظ نسخة من المرفقات عند كل استخراج.

    بدونها تمحو الرفعة الجديدة القديمة بلا أثر، فلا يُعرف ما الذي غيّره
    التعديل ولا أي متطلب صار على شرط ملغى.
    """
    pid = st.session_state.get("_project_id")
    if pid is None:
        return
    try:
        db.add_attachment_version(
            pid,
            st.session_state.get("attachment_texts") or {},
            st.session_state.get("attachment_roles") or {},
        )
    except Exception:
        # فشل الحفظ لا يُسقط الاستخراج — النص بين يدي المستخدم بالفعل
        pass


def _render_addenda():
    """مقارنة رفعة المرفقات بما قبلها، وتحديد المتطلبات التي مسّها التعديل."""
    pid = st.session_state.get("_project_id")
    if pid is None:
        return

    try:
        versions = db.list_attachment_versions(pid)
    except Exception:
        return

    with st.expander(t("ad.title"), expanded=False):
        st.caption(t("ad.hint"))

        if not versions:
            st.info(t("ad.no_versions"))
            return

        st.caption(t("ad.versions", n=len(versions)))
        for i, version in enumerate(versions[:5]):
            st.markdown(
                f"- {t('ad.version_label', n=len(versions) - i, at=version['created_at'])}"
            )

        if len(versions) < 2:
            st.info(t("ad.need_two"))
            return

        if st.button(t("ad.compare"), type="primary", key="compare_versions",
                     disabled=auth.blocked("projects.edit")):
            st.session_state["_addenda_diff"] = _compute_diff(versions)
            st.rerun()

        diff = st.session_state.get("_addenda_diff")
        if not diff:
            return

        if not addenda.has_changes(diff):
            st.success(t("ad.no_changes"))
            return

        stats = addenda.summarize(diff)
        st.warning(t(
            "ad.changed_summary",
            changed=stats["changed_files"], added=stats["added_files"],
            removed=stats["removed_files"], added_lines=stats["added_lines"],
            removed_lines=stats["removed_lines"],
        ))

        for label, names in (
            (t("ad.added_files"), diff["added"]),
            (t("ad.removed_files"), diff["removed"]),
            (t("ad.changed_files"), [c["name"] for c in diff["changed"]]),
        ):
            if names:
                st.markdown(f"**{label}**: " + " · ".join(names))

        sample = [ln for ln in diff["new_text"].splitlines() if ln.strip()][:6]
        if sample:
            with st.expander(t("ad.sample_added")):
                for line in sample:
                    st.markdown(f"- {line[:200]}")

        affected = addenda.affected_requirements(
            st.session_state.get("df_compliance"), diff
        )
        if not affected:
            st.info(t("ad.affected_none"))
            return

        st.error(t("ad.affected", n=len(affected)) + "\n\n" + "\n".join(
            f"- **{a['req_id']}** — {a['requirement'][:90]} · _{a['reason'][:90]}_"
            for a in affected[:12]
        ))

        if st.button(t("ad.mark"), type="primary", key="mark_affected",
                     disabled=auth.blocked("projects.edit")):
            st.session_state["df_compliance"] = addenda.mark_unchecked(
                st.session_state.get("df_compliance"), affected
            )
            st.session_state.pop("de_compliance", None)
            st.success(t("ad.marked", n=len(affected)))


def _compute_diff(versions: list) -> dict:
    """يقارن أحدث نسختين محفوظتين."""
    latest = db.load_attachment_version(versions[0]["id"]) or {}
    previous = db.load_attachment_version(versions[1]["id"]) or {}
    return addenda.diff_versions(
        (previous.get("payload") or {}).get("texts"),
        (latest.get("payload") or {}).get("texts"),
    )


# ─── لوحة المواعيد ────────────────────────────────────────────────────────────

# تحذير مبكّر: أقل من هذا العدد من الأيام يعني أن التحضير صار سباقاً
DEADLINE_WARNING_DAYS = 10


def _render_deadlines():
    """
    الموعد النهائي وما يرتبط به. التسليم المتأخر خسارة كاملة لا نقص درجات،
    وسريان العرض والضمان الابتدائي موعدان يُغفَلان فيسقط عرض مكتمل فنياً.
    """
    ctx = st.session_state.get("project_context") or {}
    if not ctx:
        return

    with st.expander(t("dl.title"), expanded=True):
        deadline = submission.deadline_date(ctx)
        summary = submission.submission_summary(
            st.session_state.get("df_submission"), ctx
        )

        c1, c2, c3 = st.columns(3)
        c1.metric(t("dl.deadline"), ctx.get("submission_deadline") or t("common.none"))

        if deadline is None:
            c2.metric(t("dl.remaining"), "—")
            st.caption(t("dl.unreadable"))
        else:
            import datetime as _dt

            days = (deadline - _dt.date.today()).days
            if days > 0:
                remaining = t("dl.days", n=days)
            elif days == 0:
                remaining = t("dl.today")
            else:
                remaining = t("dl.passed", n=abs(days))
            c2.metric(t("dl.remaining"), remaining)
            if 0 <= days <= DEADLINE_WARNING_DAYS:
                st.warning(t("dl.soon", n=days))

        c3.metric(t("dl.expiring"), len(summary["expiring"]))

        for label, key in (
            (t("dl.offer_validity"), "offer_validity"),
            (t("dl.bid_bond"), "bid_bond"),
        ):
            value = str(ctx.get(key, "")).strip()
            if value:
                st.markdown(f"**{label}**: {value}")


def render():
    _render_upload()

    if not st.session_state.get("rfp_raw_text"):
        st.info(t("an.start_hint"))
        return

    _render_attachment_roles()
    _render_addenda()
    st.divider()
    _render_project_context()
    _render_deadlines()

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
