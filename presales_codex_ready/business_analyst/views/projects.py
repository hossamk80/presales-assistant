"""
views/projects.py — إدارة المنافسات المحفوظة

كل منافسة مشروع مستقل: كراسته وتحليلاته وأقسامه وجداوله وملاحظات مراجعته.
التبديل بين المنافسات يحفظ الحالية أولاً حتى لا يضيع عمل.
"""
import json
import streamlit as st

from utils import audit, auth, db, history
from components import theme
from utils.i18n import t
from utils.state import (
    STATE_SCHEMA,
    DEFAULT_COMPLIANCE_DF,
    DEFAULT_BOQ_DF,
    PIPELINE_STAGES as STATE_SCHEMA_PIPELINE_STAGES,
    get_project_snapshot,
    get_sections,
    load_state_snapshot,
    reset_sections,
)


def current_project_id() -> int | None:
    return st.session_state.get("_project_id")


def current_project_name() -> str:
    return st.session_state.get("_project_name", "")


def save_current(show_toast: bool = False) -> bool:
    """يحفظ المنافسة المفتوحة. يُرجع False إن لم تكن هناك واحدة أو لم يُصرَّح."""
    pid = current_project_id()
    if pid is None or not auth.can("projects.edit"):
        return False
    snapshot = get_project_snapshot()
    _audit_section_edits(snapshot)
    _write(pid, snapshot)
    if show_toast:
        st.toast(t("proj.saved"))
    return True


# ─── تعارض الحفظ التلقائي (13-7) ──────────────────────────────────────────────
#
# كان الحفظ غير مشروط: جلستان على منافسة واحدة تكتبان بالتناوب، فآخر كاتب يمحو
# عمل الأول بلا أن يعلم أحدهما. الآن لكل منافسة رقم مراجعة، والجلسة تحمل الرقم
# الذي رأته آخر مرة. عند اختلافهما نُدمج بدل أن ندهس:
#
#   · حقل غيّرته أنا وحدي            ← يُكتب كما لديّ
#   · حقل غيّره الآخر وحده           ← يبقى كما لديه
#   · حقل غيّرناه كلانا إلى قيمتين   ← تعارض حقيقي: تُعتمد نسخته (فهي المحفوظة
#                                       بالفعل) ويُحفظ نصّي نسخةً في سجل النسخ
#                                       (13-6) وأُبلَّغ به. لا شيء يضيع.


# محاولات الدمج قبل الاستسلام — الدوران بلا حدّ يُعلّق الواجهة
_MERGE_ATTEMPTS = 3


def _revision() -> int | None:
    return st.session_state.get("_project_revision")


def _write(project_id: int, snapshot: dict):
    """يحفظ حفظاً مشروطاً، ويدمج إن سبقته جلسة أخرى."""
    # 14-7: القطاع يعيش في الحمولة (فيعود مع فتح المنافسة) **وفي عمود** يُجمَّع
    # عليه قياس الفوز. العمود يُحدَّث مع كل حفظ فلا ينحرف عن الحمولة.
    new_revision = db.save_project(
        project_id, snapshot, expected_revision=_revision(),
        sector=str(snapshot.get("project_sector", "") or "").strip(),
    )
    if new_revision is None:
        new_revision = _merge_and_write(project_id, snapshot)
    st.session_state["_project_revision"] = new_revision
    st.session_state["_saved_fingerprint"] = _fingerprint(get_project_snapshot())


def _changed_keys(before: dict, after: dict) -> set:
    return {k for k in set(before) | set(after) if before.get(k) != after.get(k)}


def _merge_and_write(project_id: int, mine: dict, attempt: int = 1) -> int | None:
    """
    يدمج تعديلاتي في نسخة الجلسة الأخرى ويحفظ. يعيد رقم المراجعة الجديد.

    الأساس هو ما حفظتُه أنا آخر مرة (`_saved_fingerprint`): ما اختلف عنه عندي
    هو تعديلي، وما اختلف عنه عندهم هو تعديلهم.
    """
    if attempt > _MERGE_ATTEMPTS:
        # جلسات تكتب أسرع مما ندمج — نتوقف بلا كتابة بدل الدوران، وعملي باقٍ
        # في جلستي وفي سجل النسخ
        st.session_state["_autosave_error"] = t("proj.merge_busy")
        return db.project_revision(project_id)

    record = db.load_project(project_id)
    if record is None:
        return None
    theirs = record["payload"]

    try:
        base = json.loads(st.session_state.get("_saved_fingerprint") or "{}")
    except (TypeError, ValueError):
        base = {}

    my_edits = _changed_keys(base, mine)
    their_edits = _changed_keys(base, theirs)
    clashing = sorted(
        k for k in my_edits & their_edits if mine.get(k) != theirs.get(k)
    )

    merged = dict(theirs)
    for key in my_edits - set(clashing):
        merged[key] = mine[key]

    # التعارض الحقيقي: نصّي لا يُكتب فوق نصّهم، لكنه لا يضيع — يُحفظ نسخةً
    for key in clashing:
        if key.startswith("sec_"):
            audit.snapshot_section(key[4:], str(mine.get(key) or ""),
                                   project_id=project_id)

    revision = db.save_project(project_id, merged,
                               expected_revision=record.get("revision"))
    if revision is None:
        # جلسة ثالثة كتبت أثناء الدمج — نعيد المحاولة على حالتها الجديدة
        return _merge_and_write(project_id, mine, attempt + 1)

    load_state_snapshot(merged)
    audit.record(audit.PROJECT_MERGE, project_id=project_id,
                 detail=",".join(clashing))
    st.session_state["_merge_notice"] = {
        "merged": len(my_edits - set(clashing)),
        "clashing": clashing,
    }
    return revision


def _fingerprint(snapshot: dict) -> str:
    return json.dumps(snapshot, ensure_ascii=False, sort_keys=True, default=str)


def _audit_section_edits(snapshot: dict):
    """
    يسجّل نصوص الأقسام التي تغيّرت منذ آخر حفظ (13-5).

    اللقطة المحفوظة موجودة أصلاً في `_saved_fingerprint` — نقرأها بدل حفظ نسخة
    ثانية من كل شيء لغرض المقارنة وحدها.
    """
    raw = st.session_state.get("_saved_fingerprint")
    if not raw:
        return                      # أول حفظ: لا «قبل» يُقارَن به
    try:
        before = json.loads(raw)
    except (TypeError, ValueError):
        return
    from utils.state import get_sections

    audit.record_section_edits(before, snapshot, [s["key"] for s in get_sections()])


def autosave():
    """
    حفظ تلقائي عند تغيّر الحالة. يُستدعى في نهاية كل دورة رسم، فيبقى العمل
    محفوظاً دون أن يتذكّر المستخدم الضغط على زر.
    """
    if current_project_id() is None:
        return
    # 13-3: المطّلع والمراجع يقرآن ولا يكتبان — الحفظ التلقائي لا يجوز أن
    # يكتب باسمهما ما تغيّر في جلستهما (فتح موسّع أو ترتيب جدول).
    if not auth.can("projects.edit"):
        return
    try:
        snapshot = get_project_snapshot()
        fingerprint = _fingerprint(snapshot)
        if fingerprint != st.session_state.get("_saved_fingerprint"):
            _audit_section_edits(snapshot)
            _write(current_project_id(), snapshot)
    except Exception as e:
        # الحفظ التلقائي لا يجوز أن يُسقط الواجهة
        st.session_state["_autosave_error"] = str(e)


def _clear_project_state():
    """يعيد حالة المنافسة للقيم الافتراضية دون المساس بملف الشركة."""
    from utils.state import COMPANY_KEYS

    for key, default in STATE_SCHEMA.items():
        if key in COMPANY_KEYS or key.startswith(("api_", "cn_")):
            continue
        st.session_state[key] = default
    for key in [k for k in list(st.session_state) if k.startswith(("sec_ai_", "steer_", "ta_", "de_", "inc_"))]:
        del st.session_state[key]
    st.session_state["df_compliance"] = DEFAULT_COMPLIANCE_DF.copy()
    st.session_state["df_boq"] = DEFAULT_BOQ_DF.copy()
    reset_sections()


def open_project(project_id: int):
    """يحفظ الحالية ثم يفتح المطلوبة."""
    save_current()
    record = db.load_project(project_id)
    if record is None:
        st.error(t("proj.not_found"))
        return
    _clear_project_state()
    load_state_snapshot(record["payload"])
    st.session_state["_project_id"] = project_id
    st.session_state["_project_name"] = record["name"]
    # 13-7: الرقم الذي رأته هذه الجلسة — أساس كشف كتابة جلسة أخرى بعده
    st.session_state["_project_revision"] = record.get("revision")
    st.session_state["_saved_fingerprint"] = _fingerprint(get_project_snapshot())


def close_project():
    save_current()
    _clear_project_state()
    st.session_state.pop("_project_id", None)
    st.session_state.pop("_project_name", None)
    st.session_state.pop("_project_revision", None)
    st.session_state.pop("_saved_fingerprint", None)


def _render_pipeline():
    """
    خطّ الأنابيب واستراتيجية العرض (14-8) للمنافسة المفتوحة.

    الحقول أربعة، و**واحد منها فقط يصل النموذج**: «لماذا نفوز». المرحلة والمالك
    واحتمال الفوز إدارة داخلية — واحتمال الفوز خصوصاً رقم لا يُكتب في عرض أبداً،
    فمنعه بنيوي في `state.strategy_block` لا تعليمة نرجو أن يتبعها النموذج.
    """
    may_edit = auth.can("projects.edit")

    with st.expander(t("pipe.title"), expanded=False):
        st.caption(t("pipe.hint"))

        c_stage, c_owner, c_prob = st.columns(3)
        with c_stage:
            stages = list(STATE_SCHEMA_PIPELINE_STAGES)
            current = st.session_state.get("pipeline_stage", "")
            st.session_state["pipeline_stage"] = st.selectbox(
                t("pipe.stage"), stages,
                index=stages.index(current) if current in stages else 0,
                format_func=lambda s: s or t("common.not_set"),
                disabled=not may_edit,
            )
        with c_owner:
            st.session_state["pipeline_owner"] = st.text_input(
                t("pipe.owner"),
                value=str(st.session_state.get("pipeline_owner", "") or ""),
                disabled=not may_edit,
            )
        with c_prob:
            st.session_state["win_probability"] = st.slider(
                t("pipe.probability"), min_value=0, max_value=100, step=5,
                value=int(st.session_state.get("win_probability", 0) or 0),
                disabled=not may_edit, help=t("pipe.probability_help"),
            )

        st.session_state["why_we_win"] = st.text_area(
            t("pipe.why"),
            value=str(st.session_state.get("why_we_win", "") or ""),
            height=110, placeholder=t("pipe.why_ph"), help=t("pipe.why_help"),
            disabled=not may_edit,
        )
        # يُقال صراحةً أيّ حقل يغادر إلى النموذج وأيّها لا — لئلا يكتب أحد
        # معلومة داخلية في الخانة الوحيدة التي تصل العرض.
        st.caption(t("pipe.only_why_reaches_model"))
        if str(st.session_state.get("why_we_win", "") or "").strip():
            st.success(t("pipe.why_active"))
        else:
            st.info(t("pipe.why_empty"))


# ─── الموصّلات الخارجية: سحب لكل منافسة (14-10) ────────────────────────────────
#
# **التفعيل لكل منافسة على حدة** لا مفتاح عامّ: قناة مفتوحة دائماً تُخرج بيانات
# منافسة لم يقصد أحد ربطها بنظام خارجي، وأول من يعلم بذلك قد يكون مالك البيانات.
#
# و**تحذير خروج البيانات يُعرض عند القرار** لا في صفحة إعدادات تُقرأ مرة وتُنسى.


def _render_connectors(project: dict):
    """سحب من نظام خارجي إلى سجلات الأدلة — سحب فقط، بلا دفع."""
    from utils import connectors

    pid = project["id"]
    may_edit = auth.can("tables.edit")

    with st.expander(t("cn.pull_title"), expanded=False):
        st.caption(t("cn.pull_hint"))

        name = st.selectbox(
            t("cn.connector"), list(connectors.available()),
            format_func=lambda n: n.capitalize(), key=f"cn_pick_{pid}",
        )
        from views.settings import _connector_config

        connector = connectors.build(name, _connector_config(name))
        if connector is None or not connector.configured():
            st.info(t("cn.not_configured"))
            return

        enabled = st.checkbox(
            t("cn.enable_for_tender"),
            value=connectors.enabled_for(name, pid),
            key=f"cn_on_{pid}", disabled=not may_edit,
            help=t("cn.enable_help"),
        )
        if enabled != connectors.enabled_for(name, pid):
            connectors.set_enabled(name, pid, enabled)

        if not enabled:
            st.caption(t("cn.disabled_note"))
            return

        resource = st.selectbox(
            t("cn.resource"), list(connectors.RESOURCES),
            format_func=lambda r: t("cn.res_" + r), key=f"cn_res_{pid}",
        )

        # ما يغادر الجهاز يُعلَن **قبل** خروجه، ووجهته حرفيةً
        notice = connector.egress_notice(resource)
        st.warning(t("cn.egress_now", host=notice["endpoint"] or "—",
                     resource=t("cn.res_" + resource)))
        if notice["personal"]:
            # 13-10: سحب أشخاص يُدخل النظام في نطاق سياسة البيانات الشخصية
            st.error(t("cn.personal_warning"))

        if st.button(t("cn.pull"), type="primary", disabled=not may_edit):
            try:
                rows = connector.fetch(resource)
            except connectors.ConnectorError as e:
                # الفشل يُقال ولا يُبتلع: جدول فارغ بعد فشل يبدو حقيقةً مقيسة
                st.error(t("cn.failed", error=e))
                return

            registry = connectors.RESOURCE_REGISTRY[resource]
            existing = db.list_records(registry)
            # الدمج بالاسم: سحب ثانٍ لا يُضاعف الصفوف، والقائم لا يُدهَس —
            # ما عدّله إنسان أولى ممّا يعيده نظام خارجي
            key = "name" if registry != "vendors" else "vendor"
            seen = {str(r.get(key, "")).strip() for r in existing}
            added = [r for r in rows if str(r.get(key, "")).strip() not in seen]
            db.save_records(registry, existing + added)

            audit.record(audit.CONNECTOR_PULL, project_id=pid,
                         detail=f"{name}:{resource}:{len(added)}")
            st.success(t("cn.pulled", n=len(added), skipped=len(rows) - len(added),
                         registry=t("rec." + registry)))
            st.rerun()

        st.caption(t("cn.pull_only"))


# ─── تحويل الفائز إلى مشروع (14-11) ───────────────────────────────────────────


def _section_text(key: str) -> str:
    from utils.state import section_content_key

    return str(st.session_state.get(section_content_key(key), "") or "")


def _render_delivery(project: dict):
    """
    لوحة التسليم: تحويل المنافسة الفائزة، ثم متابعة التزاماتها.

    الفائزة **وحدها** تُحوَّل: خطة تسليم لعملٍ لم نفز به تُدخل في اللوحة
    التزامات لا تخصّ أحداً.
    """
    from utils import delivery as delivery_utils

    pid = project["id"]
    record = db.get_delivery(pid)
    may_edit = auth.can("projects.edit")

    with st.expander(t("dlv.title"), expanded=record is not None):
        st.caption(t("dlv.hint"))

        if record is None:
            if not delivery_utils.can_convert(project):
                st.info(t("dlv.needs_win"))
                return
            st.success(t("dlv.ready"))
            if st.button(t("dlv.convert"), type="primary", disabled=not may_edit):
                delivery_id = db.create_delivery(
                    pid, project.get("name", ""), project.get("entity", ""),
                    created_by=auth.display_name(),
                )
                if delivery_id is None:
                    st.warning(t("dlv.already"))
                    return
                found = delivery_utils.extract_commitments(
                    st.session_state.get("df_compliance"),
                    get_sections(), _section_text,
                )
                for item in found:
                    db.add_deliverable(
                        delivery_id, item["title"], source=item["source"],
                        source_ref=item["source_ref"], clause_ref=item["clause_ref"],
                        confirmed=item["confirmed"],
                    )
                audit.record(audit.DELIVERY_CONVERT, project_id=pid,
                             project_name=project.get("name", ""),
                             detail=str(len(found)))
                st.success(t("dlv.converted", n=len(found)))
                st.rerun()
            return

        items = db.list_deliverables(record["id"])
        stats = delivery_utils.summary(items)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(t("dlv.m_total"), stats["total"])
        c2.metric(t("dlv.m_unconfirmed"), stats["unconfirmed"])
        c3.metric(t("dlv.m_open"), stats["open"])
        c4.metric(t("dlv.m_done"), stats["done"])

        if stats["unconfirmed"]:
            # المستخرَج من النصّ اقتراح: قائمة يُبنى عليها التنفيذ لا تُملأ
            # بلا مراجعة بشرية
            st.warning(t("dlv.needs_confirm", n=stats["unconfirmed"]))

        if not items:
            st.info(t("dlv.empty"))

        for item in items:
            mark = "⏳" if not item["confirmed"] else (
                "✅" if item["status"] == db.DELIVERABLE_DONE else "🔵"
            )
            with st.expander(f"{mark} {item['title']}"):
                origin = t("dlv.src_" + item["source"])
                ref = " · ".join(filter(None, [item["source_ref"], item["clause_ref"]]))
                st.caption(f"{t('dl.source')}: {origin}"
                           + (f" — {ref}" if ref else f" — {t('dl.no_ref')}"))

                c_own, c_due, c_st = st.columns(3)
                with c_own:
                    owner = st.text_input(t("dlv.owner"), value=item["owner"],
                                          key=f"dl_own_{item['id']}",
                                          disabled=not may_edit)
                with c_due:
                    due = st.text_input(t("dlv.due"), value=item["due_at"],
                                        key=f"dl_due_{item['id']}",
                                        disabled=not may_edit)
                with c_st:
                    statuses = list(db.DELIVERABLE_STATUSES)
                    status = st.selectbox(
                        t("dlv.status"), statuses,
                        index=statuses.index(item["status"])
                        if item["status"] in statuses else 0,
                        format_func=lambda s: t("dlv.st_" + s),
                        key=f"dl_st_{item['id']}", disabled=not may_edit,
                    )

                c_save, c_conf, c_del = st.columns(3)
                with c_save:
                    if st.button(t("common.save_now"), key=f"dl_save_{item['id']}",
                                 width="stretch", disabled=not may_edit):
                        db.update_deliverable(item["id"], status=status,
                                              owner=owner, due_at=due)
                        st.rerun()
                with c_conf:
                    if st.button(t("dlv.confirm"), key=f"dl_conf_{item['id']}",
                                 width="stretch", type="primary",
                                 disabled=not may_edit or bool(item["confirmed"])):
                        db.update_deliverable(item["id"], confirmed=True)
                        st.rerun()
                with c_del:
                    if st.button(t("common.delete"), key=f"dl_del_{item['id']}",
                                 width="stretch", disabled=not may_edit):
                        db.delete_deliverable(item["id"])
                        st.rerun()

        st.divider()
        with st.form("new_deliverable", clear_on_submit=True):
            manual = st.text_input(t("dlv.add"), placeholder=t("dlv.add_ph"))
            if st.form_submit_button(t("dlv.add_btn"), disabled=not may_edit):
                if manual.strip():
                    # ما يُضاف يدوياً مُقَرٌّ بذاته — كتبه إنسان لا نموذج
                    db.add_deliverable(record["id"], manual,
                                       source=db.SOURCE_MANUAL, confirmed=True)
                    st.rerun()

        if st.button(t("dlv.undo_convert"), disabled=not may_edit):
            db.delete_delivery(pid)
            st.rerun()


def _render_history(projects: list, pid):
    """
    ذاكرة العطاءات: سجل النتائج، والمنافسات السابقة المشابهة للمفتوحة الآن.
    """
    stats = history.outcome_stats(projects)

    with st.expander(t("proj.history"), expanded=False):
        st.caption(t("proj.history_hint"))

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(t("proj.won"), stats["won"])
        c2.metric(t("proj.lost"), stats["lost"])
        c3.metric(t("proj.not_submitted"), stats["not_submitted"])
        c4.metric(t("proj.unset"), stats["unset"])

        if pid is None:
            st.info(t("proj.history_open_first"))
            return

        current = next((p for p in projects if p["id"] == pid), None)
        if current is None:
            return

        similar = history.similar_projects(
            projects, current["name"], current.get("entity", ""), exclude_id=pid
        )
        if not similar:
            st.info(t("proj.no_similar"))
        else:
            st.markdown(f"**{t('proj.similar')}**")
            for item in similar:
                outcome = str(item.get("outcome", "")).strip() or t("proj.unset")
                marks = []
                if item["same_entity"]:
                    marks.append(t("proj.same_entity"))
                if item["shared_terms"]:
                    marks.append(" · ".join(item["shared_terms"][:4]))
                st.markdown(
                    f"- **{item['name']}** — {outcome}"
                    + (f"  \n  <span style='color:{theme.TOKENS['muted']};font-size:12px'>"
                       f"{' | '.join(marks)}</span>" if marks else ""),
                    unsafe_allow_html=True,
                )
                note = str(item.get("outcome_note", "")).strip()
                if note:
                    st.caption(f"↳ {note}")

        st.divider()
        st.markdown(f"**{t('proj.record_outcome')}**")
        col_out, col_note = st.columns([1, 3])
        with col_out:
            outcome = st.selectbox(
                t("proj.outcome"),
                options=history.OUTCOME_OPTIONS,
                index=history.OUTCOME_OPTIONS.index(current.get("outcome") or "")
                if (current.get("outcome") or "") in history.OUTCOME_OPTIONS else 0,
                format_func=lambda v: v or t("proj.unset"),
                key=f"outcome_{pid}",
            )
        with col_note:
            note = st.text_input(
                t("proj.outcome_note"),
                value=current.get("outcome_note") or "",
                placeholder=t("proj.outcome_note_ph"),
                key=f"outcome_note_{pid}",
            )
        if st.button(t("proj.save_outcome"), type="primary", key=f"save_outcome_{pid}",
                     disabled=auth.blocked("projects.edit")):
            db.set_outcome(pid, outcome, note.strip())
            audit.record(audit.PROJECT_OUTCOME, project_id=pid, detail=outcome)
            st.success(t("proj.outcome_saved"))
            st.rerun()


def _render_entities():
    """
    ملف الجهات (12-7): سلوك الجهة في التقييم يتكرّر، فيُسجَّل مرة ويُستدعى
    تلقائياً عند فتح منافسة لها — المطابقة بتوحيد الإملاء لا بالحرف.
    """
    import pandas as pd

    from utils import records

    rows = db.list_records("entities")
    with st.expander(f"{t('rec.entities')} ({len(rows)})", expanded=False):
        st.caption(t("rec.entities_hint"))

        # الجهة المفتوحة الآن: إن كان لها ملف نعرضه، وإلا نعرض زر إضافتها
        current = str(st.session_state.get("_project_entity", "")).strip() or str(
            (st.session_state.get("project_context") or {}).get("issuing_entity", "")
        ).strip()
        if current:
            profile = db.find_entity(current)
            if profile:
                st.success(t("rec.entity_matched", name=current))
            else:
                st.info(t("rec.entity_unknown", name=current))

        frame = pd.DataFrame(
            rows or [records.blank_row("entities")],
            columns=records.column_keys("entities"),
        )
        edited = st.data_editor(
            frame,
            column_config={
                c["key"]: st.column_config.TextColumn(
                    t(c["label_key"]),
                    width="large" if c["kind"] == records.LONGTEXT else "medium",
                )
                for c in records.columns_of("entities")
            },
            num_rows="dynamic",
            width="stretch",
            key="rec_editor_entities",
        )
        if st.button(t("rec.save"), key="rec_save_entities", type="primary",
                     disabled=auth.blocked("company.edit")):
            cleaned = [
                records.normalize_row("entities", row)
                for row in edited.to_dict(orient="records")
            ]
            dropped = records.partial_rows("entities", cleaned)
            cleaned = [r for r in cleaned if not records.is_blank("entities", r)]
            if dropped:
                st.warning(t("rec.dropped_partial", n=dropped))
            db.save_records("entities", cleaned)
            st.success(t("rec.saved", n=len(cleaned)))
            st.rerun()


def render():
    st.caption(f"{t('proj.caption')} {t('proj.db_path')} `{db.DB_PATH}`")

    pid = current_project_id()
    if pid is not None:
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            st.success(f"{t('proj.open_now')} **{current_project_name()}**")
        with c2:
            if st.button(f"💾 {t('common.save_now')}", width="stretch"):
                save_current(show_toast=True)
                st.rerun()
        with c3:
            if st.button(f"📕 {t('common.close')}", width="stretch"):
                close_project()
                st.rerun()
    else:
        st.info(t("proj.none_open"))

    # 14-8: خطّ الأنابيب واستراتيجية العرض — للمنافسة المفتوحة وحدها
    if pid is not None:
        _render_pipeline()
        # 14-11: وتحويلها إلى مشروع تنفيذ حين تفوز
        _open = next((p for p in db.list_projects() if p["id"] == pid), None)
        if _open is not None:
            _render_connectors(_open)     # 14-10
            _render_delivery(_open)       # 14-11

    notice = st.session_state.pop("_merge_notice", None)
    if notice:
        # 13-7: الدمج حدث فعلاً — نُبلّغ به ولا نسأل عنه بعد فوات الأوان
        if notice["clashing"]:
            st.warning(t("proj.merged_with_clash",
                         n=notice["merged"], fields=" · ".join(notice["clashing"])))
        else:
            st.info(t("proj.merged_clean", n=notice["merged"]))

    if st.session_state.get("_autosave_error"):
        st.warning(t("proj.autosave_failed", error=st.session_state.pop("_autosave_error")))

    st.divider()
    _render_entities()

    st.divider()

    # ── إنشاء منافسة ──────────────────────────────────────────────────────────
    with st.expander(t("proj.new"), expanded=pid is None):
        with st.form("new_project", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input(t("proj.name"), placeholder="…")
                entity = st.text_input(t("proj.entity"), placeholder="…")
            with c2:
                reference = st.text_input(t("proj.reference"), placeholder="2026-…")
                # 14-7: القطاع يُجمَّع عليه قياس الفوز، و 14-1 يُخصّص به
                # البرومبتات. كان `project_sector` يُقرأ ولا يُكتب في أي مكان.
                sector = st.text_input(t("proj.sector"), placeholder="…",
                                       help=t("proj.sector_help"))
                carry = st.checkbox(
                    t("proj.carry"), value=False,
                )
            if st.form_submit_button(t("proj.create"), type="primary",
                                     disabled=auth.blocked("projects.create")):
                if not name.strip():
                    st.error(t("proj.name_required"))
                else:
                    save_current()
                    if not carry:
                        _clear_project_state()
                    st.session_state["project_sector"] = sector.strip()
                    new_id = db.create_project(
                        name.strip(), get_project_snapshot(), reference.strip(),
                        entity.strip(), sector.strip()
                    )
                    st.session_state["_project_id"] = new_id
                    st.session_state["_project_name"] = name.strip()
                    st.session_state["_project_revision"] = db.project_revision(new_id)
                    st.session_state["_saved_fingerprint"] = _fingerprint(get_project_snapshot())
                    audit.record(audit.PROJECT_CREATE, project_id=new_id,
                                 project_name=name.strip())
                    st.success(t("proj.created", name=name.strip()))
                    st.rerun()

    # ── قائمة المنافسات ───────────────────────────────────────────────────────
    projects = db.list_projects()
    if not projects:
        return

    _render_history(projects, pid)

    st.markdown(t("proj.count", n=len(projects)))
    for proj in projects:
        is_open = proj["id"] == pid
        with st.container(border=True):
            c_info, c_open, c_dup, c_del = st.columns([6, 1.2, 1.2, 1.2])
            with c_info:
                meta = " · ".join(filter(None, [
                    proj["entity"], proj["reference"],
                    f"{t('proj.updated')} {proj['updated_at']}",
                ]))
                st.markdown(
                    f"{'📂' if is_open else '📁'} **{proj['name']}**"
                    f"<br><span style='color:{theme.TOKENS['muted']};font-size:12px'>{meta}</span>",
                    unsafe_allow_html=True,
                )
            with c_open:
                if st.button(t("common.open"), key=f"open_{proj['id']}", width="stretch", disabled=is_open):
                    open_project(proj["id"])
                    st.rerun()
            with c_dup:
                if st.button(t("common.copy"), key=f"dup_{proj['id']}", width="stretch",
                             disabled=auth.blocked("projects.create")):
                    new_id = db.duplicate_project(
                        proj["id"], f"{proj['name']} {t('proj.copy_suffix')}")
                    audit.record(audit.PROJECT_DUPLICATE, project_id=new_id,
                                 project_name=proj["name"], detail=str(proj["id"]))
                    st.rerun()
            with c_del:
                # 13-3: الحذف لمدير العطاءات ومدير النظام. الزر معطَّل، والفحص
                # مُعاد عند التنفيذ — الحارس في المنطق لا في مظهر الزر.
                confirm_key = f"confirm_del_{proj['id']}"
                may_delete = auth.can("projects.delete")
                if st.session_state.get(confirm_key):
                    if st.button(t("common.confirm"), key=f"del2_{proj['id']}",
                                 width="stretch", type="primary", disabled=not may_delete):
                        if not may_delete:
                            st.error(t("role.forbidden"))
                        else:
                            if is_open:
                                close_project()
                            audit.record(audit.PROJECT_DELETE, project_id=proj["id"],
                                         project_name=proj["name"])
                            # 13-6 و 13-8 و 14-9: نسخ الأقسام وقرارات الاعتماد
                            # والاستفسارات تذهب مع منافستها
                            db.delete_section_versions(proj["id"])
                            db.delete_approvals(proj["id"])
                            db.delete_project_clarifications(proj["id"])
                            db.delete_project(proj["id"])
                            st.session_state.pop(confirm_key, None)
                            st.rerun()
                else:
                    if st.button(t("common.delete"), key=f"del_{proj['id']}",
                                 width="stretch", disabled=not may_delete,
                                 help=None if may_delete else t("role.forbidden")):
                        st.session_state[confirm_key] = True
                        st.rerun()
