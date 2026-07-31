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
from utils.file_handler import extract_texts_per_file
from utils.state import ATTACHMENT_ROLES, guess_attachment_role, role_text
from components.ui import ai_generate_button


def _language() -> str:
    return st.session_state.get("output_language", DEFAULT_LANGUAGE)


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
    st.markdown("### 📥 رفع مرفقات المنافسة")

    col_upload, col_clear = st.columns([4, 1])
    with col_upload:
        files = st.file_uploader(
            "يدعم: PDF · Word · Excel · CSV · TXT · HTML",
            accept_multiple_files=True,
            label_visibility="collapsed",
        )
    with col_clear:
        if st.session_state.get("rfp_raw_text") and st.button("🗑️ مسح", width="stretch"):
            from utils.state import reset_analysis
            reset_analysis()
            st.rerun()

    if st.button("📂 استخراج النصوص", type="primary", disabled=not files):
        with st.spinner("جاري الاستخراج..."):
            per_file = extract_texts_per_file(files)
        per_file = {n: t for n, t in per_file.items() if t.strip()}
        if not per_file:
            st.error("❌ لم يتم استخراج أي نص. تأكد من الملفات المرفوعة.")
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
        f"📎 المرفقات ({len(texts)}) · تقدير التوكنز: {total_tokens:,}", expanded=True
    ):
        st.caption(
            "الدور مُرجَّح من اسم الملف — عدّله إن أخطأ. يؤثر على التعليمات التي "
            "تميّز الكراسة عن ملاحقها عن جداول الكميات."
        )
        role_keys = list(ATTACHMENT_ROLES)
        changed = False

        for name in list(texts):
            c_name, c_role, c_del = st.columns([5, 3, 1])
            with c_name:
                st.markdown(
                    f"**{name}**<br><span style='color:#64748B;font-size:12px'>"
                    f"{len(texts[name]):,} حرف</span>",
                    unsafe_allow_html=True,
                )
            with c_role:
                current = roles.get(name, "rfp")
                picked = st.selectbox(
                    "الدور",
                    role_keys,
                    index=role_keys.index(current) if current in role_keys else 0,
                    format_func=lambda k: ATTACHMENT_ROLES[k],
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

    with st.expander("0️⃣ سياق المشروع الموحّد (من كل المرفقات)", expanded=not ctx):
        c_model, c_btn = st.columns([3, 2])
        with c_model:
            current = st.session_state.get("ai_model_preference", DEFAULT_MODEL)
            model = st.selectbox(
                "المحرك:",
                MODEL_NAMES,
                index=MODEL_NAMES.index(current) if current in MODEL_NAMES else 0,
                key="model_context",
                label_visibility="collapsed",
            )
        with c_btn:
            run = st.button("🧩 دمج المرفقات", type="primary", width="stretch")

        if run:
            status = st.empty()
            annexes = role_text("annex")
            prompt = (
                EXTRACT_PROMPTS["project_context"]
                + f"\n{language_instruction(_language())}"
                + (f"\n\n--- الملاحق الفنية ---\n{annexes}" if annexes else "")
            )
            with st.spinner("جاري الدمج..."):
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
            st.info("اضغط **دمج المرفقات** لاستخراج بيانات المشروع الأساسية وقيوده.")
            return

        c1, c2, c3 = st.columns(3)
        c1.metric("الجهة", ctx.get("issuing_entity") or "—")
        c2.metric("الموعد النهائي", ctx.get("submission_deadline") or "—")
        c3.metric("الشهادات المطلوبة", len(ctx.get("required_certifications") or []))

        st.markdown(f"**{ctx.get('project_title', '')}**")
        if ctx.get("scope_summary"):
            st.write(ctx["scope_summary"])

        lists = [
            ("🎯 التسليمات الرئيسية", "key_deliverables"),
            ("⚙️ القيود الفنية", "technical_constraints"),
            ("⚠️ الغرامات التعاقدية", "contractual_penalties"),
            ("📜 الشهادات المطلوبة", "required_certifications"),
        ]
        for label, key in lists:
            values = ctx.get(key) or []
            if values:
                st.markdown(f"**{label}**")
                for v in values:
                    st.markdown(f"- {v}")

        if ctx.get("local_content_requirements"):
            st.info(f"🇸🇦 **المحتوى المحلي:** {ctx['local_content_requirements']}")


def render():
    _render_upload()

    if not st.session_state.get("rfp_raw_text"):
        st.info("ارفع مرفقات المنافسة واضغط **استخراج النصوص** للبدء.")
        return

    _render_attachment_roles()
    st.divider()
    _render_project_context()

    # ── Section 1: Go/No-Go ────────────────────────────────────────────────────
    with st.expander("1️⃣ قرار الملاءمة والجدوى (Go / No-Go)", expanded=True):
        ai_generate_button(
            label="توليد تقرير Go/No-Go",
            key="gonogo",
            model_key="m1",
            on_generate=lambda model, report: ai_generate(
                build_prompt("gonogo", _language()),
                model_choice=model,
                rfp_context=st.session_state["rfp_raw_text"],
                on_progress=report,
                language=_language(),
            ),
            result_state_key="analysis_gonogo",
            summary_state_key="sum_gonogo",
            summary_label="✍️ قرار المهندس المعتمد (يُمرَّر للـ AI لاحقاً):",
            result_style="info",
        )

    # ── Section 2: Evaluation Matrix ──────────────────────────────────────────
    with st.expander("2️⃣ مصفوفة معايير التقييم والأوزان"):
        ai_generate_button(
            label="استخراج الأوزان",
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
            summary_label="✍️ الأوزان المعتمدة (توجيه لكتابة المنهجية):",
            result_style="success",
        )

    # ── Section 3: Compliance Check ───────────────────────────────────────────
    with st.expander("3️⃣ الشروط الحاكمة وفجوات الامتثال"):
        ai_generate_button(
            label="فحص الشروط الإلزامية",
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
            summary_label="✍️ الشهادات والفجوات المعتمدة للمعالجة:",
            result_style="warning",
        )

    # ── Raw Text Preview ───────────────────────────────────────────────────────
    with st.expander("👁️ معاينة النص المستخرج من الكراسة"):
        raw = st.session_state["rfp_raw_text"]
        st.code(raw[:5000] + ("\n\n... [تم الاختصار]" if len(raw) > 5000 else ""), language=None)
