"""
views/review.py — مراجعة ما قبل التسليم من ثلاث زوايا: فنية · تجارية · قانونية

تفحص العرض المكتوب مقابل كراسة الشروط، وتُرجع ملاحظات مُهيكلة مرتّبة حسب
الخطورة، مع إمكانية تطبيق التحسين على القسم المعني بنقرة واحدة.
"""
import datetime
import streamlit as st

from utils.ai_engine import (
    DEFAULT_LANGUAGE,
    DEFAULT_MODEL,
    MODEL_NAMES,
    REVIEW_LENSES,
    REVIEW_SCHEMA,
    ai_generate,
    ai_generate_json,
    build_prompt,
)
from utils.i18n import t
from utils.state import get_sections, project_context_block, section_content_key

def _language() -> str:
    return st.session_state.get("output_language", DEFAULT_LANGUAGE)


SEVERITY_ORDER = {"حرجة": 0, "متوسطة": 1, "طفيفة": 2}
SEVERITY_STYLE = {
    "حرجة": ("🔴", "#FEE2E2", "#991B1B"),
    "متوسطة": ("🟡", "#FEF3C7", "#92400E"),
    "طفيفة": ("🔵", "#DBEAFE", "#1E40AF"),
}


def _written_sections() -> list:
    """الأقسام النصية المُدرَجة التي تحمل محتوى فعلياً."""
    out = []
    for sec in get_sections():
        if not sec.get("include") or sec["kind"] not in ("ai", "cover"):
            continue
        if sec["kind"] == "cover":
            content = (
                st.session_state.get("c_cover_template", "")
                if st.session_state.get("sec_cover_use_template", True)
                else st.session_state.get("sec_cover", "")
            )
        else:
            content = st.session_state.get(section_content_key(sec["key"]), "")
        if content.strip():
            out.append({"key": sec["key"], "title": sec["title"], "content": content})
    return out


def _proposal_text(sections: list) -> str:
    return "\n\n".join(f"### القسم: {s['title']}\n{s['content']}" for s in sections)


def _clamp_score(value) -> int:
    """درجة الجاهزية قد تعود خارج المدى أو نصاً."""
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return 0


def _run_lens(lens_key: str, sections: list, model: str, report) -> list:
    """تشغيل وكيل مراجعة واحد وإرجاع ملاحظاته."""
    lens = REVIEW_LENSES[lens_key]
    titles = "\n".join(f"- {s['title']}" for s in sections)

    prompt = (
        f"{lens['prompt']}\n\n"
        f"استخدم في الحقل section أحد هذه العناوين حرفياً ولا تخترع غيرها:\n{titles}\n\n"
        f"لا تُرجع ملاحظات عامة أو إنشائية — كل ملاحظة يجب أن تشير إلى نقص أو خطأ محدد.\n"
        f"إن كان القسم سليماً من زاويتك فلا تضف له ملاحظة.\n"
        f"{project_context_block()}\n\n"
        f"--- نص العرض المراد مراجعته ---\n{_proposal_text(sections)}"
    )

    result = ai_generate_json(
        prompt,
        schema=REVIEW_SCHEMA,
        model_choice=model,
        rfp_context=st.session_state.get("rfp_raw_text", ""),
        merge_key="findings",
        on_progress=report,
    )
    if isinstance(result, dict):
        scores = dict(st.session_state.get("review_scores") or {})
        scores[lens_key] = {
            "label": lens["label"],
            "icon": lens["icon"],
            "score": _clamp_score(result.get("readiness_score")),
            "assessment": str(result.get("assessment", "")).strip(),
            "strengths": [
                str(s).strip() for s in (result.get("strengths") or []) if str(s).strip()
            ],
            "recommendations": [
                str(r).strip() for r in (result.get("recommendations") or []) if str(r).strip()
            ],
        }
        st.session_state["review_scores"] = scores

    findings = (result or {}).get("findings", []) if isinstance(result, dict) else []

    valid_titles = {s["title"] for s in sections}
    enriched = []
    for i, f in enumerate(findings):
        section_title = str(f.get("section", "")).strip()
        if section_title not in valid_titles:
            # النموذج أعاد عنواناً غير مطابق — نحاول مطابقة جزئية
            section_title = next(
                (t for t in valid_titles if t and (t in section_title or section_title in t)),
                "",
            )
        enriched.append({
            "id": f"{lens_key}_{i}",
            "lens": lens_key,
            "lens_label": lens["label"],
            "section": section_title,
            "severity": f.get("severity", "متوسطة"),
            "issue": str(f.get("issue", "")).strip(),
            "impact": str(f.get("impact", "")).strip(),
            "suggested_text": str(f.get("suggested_text", "")).strip(),
            "applied": False,
        })
    return enriched


def _apply_finding(finding: dict, sections: list, model: str) -> bool:
    """يعيد كتابة القسم المعني بحيث يعالج الملاحظة. يُرجع True عند النجاح."""
    sec = next((s for s in sections if s["title"] == finding["section"]), None)
    if sec is None:
        st.error(t("rv.apply_blocked"))
        return False

    ckey = section_content_key(sec["key"])
    with st.spinner(t("rv.improving", title=sec["title"])):
        revised = ai_generate(
            build_prompt(
                "apply_finding", _language(),
                title=sec["title"],
                lens=finding["lens_label"],
                severity=finding["severity"],
                issue=finding["issue"],
                impact=finding["impact"],
                suggestion=finding["suggested_text"] or "لا توجد صياغة مقترحة — عالج الملاحظة باجتهادك.",
                content=sec["content"],
            ),
            model_choice=model,
            rfp_context=st.session_state.get("rfp_raw_text", ""),
            language=_language(),
        )

    if not revised:
        return False

    # نحفظ النص السابق ليتمكن المستخدم من التراجع
    st.session_state[f"_undo_{ckey}"] = st.session_state.get(ckey, "")
    st.session_state[ckey] = revised
    st.session_state.pop(f"ta_{sec['key']}", None)

    for f in st.session_state.get("review_findings", []):
        if f["id"] == finding["id"]:
            f["applied"] = True
    return True


def _render_finding(finding: dict, sections: list, model: str):
    icon, bg, fg = SEVERITY_STYLE.get(finding["severity"], SEVERITY_STYLE["متوسطة"])
    lens_icon = REVIEW_LENSES[finding["lens"]]["icon"]

    st.markdown(
        f"""<div style="background:{bg};border-radius:8px;padding:10px 14px;margin-top:10px;
                    font-family:Tajawal,sans-serif;">
            <span style="color:{fg};font-weight:700;">{icon} {finding['severity']}</span>
            <span style="color:#475569;"> · {lens_icon} {t("rv.review_of")} {finding['lens_label']}</span>
            <span style="color:#475569;"> · 📄 {finding['section'] or t("rv.section_unknown")}</span>
            {f'<span style="color:#065F46;font-weight:700;"> · {t("rv.applied")}</span>' if finding['applied'] else ''}
        </div>""",
        unsafe_allow_html=True,
    )
    st.markdown(f"{t('rv.issue')} {finding['issue']}")
    st.caption(f"{t('rv.impact')} {finding['impact']}")

    if finding["suggested_text"]:
        with st.expander(t("rv.suggestion")):
            st.write(finding["suggested_text"])

    can_apply = bool(finding["section"]) and not finding["applied"]
    c1, c2 = st.columns([1, 4])
    with c1:
        if st.button(
            t("rv.apply"),
            key=f"apply_{finding['id']}",
            disabled=not can_apply,
            width="stretch",
            help=None if can_apply else t("rv.apply_blocked"),
        ):
            if _apply_finding(finding, sections, model):
                st.rerun()
    with c2:
        if finding["applied"]:
            sec = next((s for s in sections if s["title"] == finding["section"]), None)
            if sec:
                ukey = f"_undo_{section_content_key(sec['key'])}"
                if st.session_state.get(ukey) and st.button(f"↩️ {t('common.undo')}", key=f"undo_{finding['id']}"):
                    st.session_state[section_content_key(sec["key"])] = st.session_state.pop(ukey)
                    st.session_state.pop(f"ta_{sec['key']}", None)
                    for f in st.session_state.get("review_findings", []):
                        if f["id"] == finding["id"]:
                            f["applied"] = False
                    st.rerun()
    st.divider()


def _overall_readiness(scores: dict) -> int:
    """
    الجاهزية الإجمالية أضعف زاوية لا متوسطها — زاوية واحدة ساقطة تكفي لرفض
    العرض (تحفظ جوهري، ضمان ابتدائي ناقص)، والمتوسط يخفي ذلك خلف زاويتين قويتين.
    """
    values = [s["score"] for s in scores.values()]
    return min(values) if values else 0


def _render_agent_scores(findings: list):
    """لوحة الوكلاء الثلاثة: درجة وتقييم ونقاط قوة وثغرات وتوصيات لكل زاوية."""
    scores = st.session_state.get("review_scores") or {}
    if not scores:
        return

    st.markdown(f"### {t('rv.agents')}")
    overall = _overall_readiness(scores)

    cols = st.columns(len(scores) + 1)
    for col, data in zip(cols, scores.values()):
        col.metric(f"{data['icon']} {data['label']}", f"{data['score']} / 100")
    cols[-1].metric(t("rv.overall_readiness"), f"{overall} / 100")

    if overall < 60:
        st.error(t("rv.not_ready"))

    for lens_key, data in scores.items():
        gaps = [f for f in findings if f["lens"] == lens_key]
        strengths = data.get("strengths") or []
        if not (data["assessment"] or strengths or data["recommendations"] or gaps):
            continue
        with st.expander(f"{data['icon']} {data['label']} — {data['score']}/100"):
            if data["assessment"]:
                st.write(data["assessment"])
            if strengths:
                st.markdown(f"**{t('rv.strengths')}**")
                for item in strengths:
                    st.markdown(f"- {item}")
            if gaps:
                st.markdown(f"**{t('rv.gaps')}**")
                for gap in gaps:
                    mark = " ✅" if gap["applied"] else ""
                    st.markdown(f"- {gap['issue']}{mark}")
            if data["recommendations"]:
                st.markdown(f"**{t('rv.recommendations')}**")
                for rec in data["recommendations"]:
                    st.markdown(f"- {rec}")
    st.divider()


def render():
    st.markdown(t("rv.title"))
    st.caption(t("rv.caption"))

    sections = _written_sections()
    if not sections:
        st.info(t("rv.no_content"))
        return

    if not st.session_state.get("rfp_raw_text"):
        st.warning(t("rv.no_rfp"))

    st.caption(t("rv.will_review", n=len(sections)))

    c_lens, c_model, c_btn = st.columns([3, 2, 2])
    with c_lens:
        chosen = st.multiselect(
            t("rv.lenses"),
            options=list(REVIEW_LENSES),
            default=list(REVIEW_LENSES),
            format_func=lambda k: f"{REVIEW_LENSES[k]['icon']} {REVIEW_LENSES[k]['label']}",
            label_visibility="collapsed",
        )
    with c_model:
        current = st.session_state.get("ai_model_preference", DEFAULT_MODEL)
        model = st.selectbox(
            t("common.engine"),
            MODEL_NAMES,
            index=MODEL_NAMES.index(current) if current in MODEL_NAMES else 0,
            key="model_review",
            label_visibility="collapsed",
        )
    with c_btn:
        run = st.button(
            t("rv.run"), type="primary", width="stretch", disabled=not chosen
        )

    if run:
        status = st.empty()
        st.session_state["review_scores"] = {}
        all_findings = []
        progress = st.progress(0.0)
        for i, lens_key in enumerate(chosen):
            lens = REVIEW_LENSES[lens_key]
            status.caption(t("rv.running", lens=lens["label"]))
            all_findings += _run_lens(
                lens_key, sections, model, lambda m: status.caption(f"⏳ {m}")
            )
            progress.progress((i + 1) / len(chosen))
        progress.empty()
        status.empty()

        all_findings.sort(key=lambda f: SEVERITY_ORDER.get(f["severity"], 1))
        st.session_state["review_findings"] = all_findings
        st.session_state["review_ran_at"] = datetime.datetime.now().strftime("%Y/%m/%d %H:%M")
        st.rerun()

    findings = st.session_state.get("review_findings", [])
    if not findings:
        if st.session_state.get("review_ran_at"):
            st.success(t("rv.clean"))
            # مراجعة بلا ملاحظات ما زالت تحمل درجات ونقاط قوة وتوصيات —
            # الخروج المبكر هنا كان يُخفي لوحة الوكلاء كاملةً.
            st.divider()
            _render_agent_scores(findings)
        return

    st.divider()
    _render_agent_scores(findings)
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in SEVERITY_ORDER}
    applied = sum(1 for f in findings if f["applied"])

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(t("rv.critical"), counts.get("حرجة", 0))
    m2.metric(t("rv.medium"), counts.get("متوسطة", 0))
    m3.metric(t("rv.minor"), counts.get("طفيفة", 0))
    m4.metric(t("rv.applied"), f"{applied} / {len(findings)}")
    st.caption(t("rv.last_run", when=st.session_state.get("review_ran_at", "—")))

    hide_applied = st.checkbox(t("rv.hide_applied"), value=False)
    st.divider()

    shown = [f for f in findings if not (hide_applied and f["applied"])]
    if not shown:
        st.success(t("rv.all_applied"))
    for finding in shown:
        _render_finding(finding, sections, model)
