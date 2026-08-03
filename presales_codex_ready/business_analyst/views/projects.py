"""
views/projects.py — إدارة المنافسات المحفوظة

كل منافسة مشروع مستقل: كراسته وتحليلاته وأقسامه وجداوله وملاحظات مراجعته.
التبديل بين المنافسات يحفظ الحالية أولاً حتى لا يضيع عمل.
"""
import json
import streamlit as st

from utils import audit, auth, db, history
from utils.i18n import t
from utils.state import (
    STATE_SCHEMA,
    DEFAULT_COMPLIANCE_DF,
    DEFAULT_BOQ_DF,
    get_project_snapshot,
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
    db.save_project(pid, snapshot)
    st.session_state["_saved_fingerprint"] = _fingerprint(snapshot)
    if show_toast:
        st.toast(t("proj.saved"))
    return True


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
            db.save_project(current_project_id(), snapshot)
            st.session_state["_saved_fingerprint"] = fingerprint
    except Exception as e:
        # الحفظ التلقائي لا يجوز أن يُسقط الواجهة
        st.session_state["_autosave_error"] = str(e)


def _clear_project_state():
    """يعيد حالة المنافسة للقيم الافتراضية دون المساس بملف الشركة."""
    from utils.state import COMPANY_KEYS

    for key, default in STATE_SCHEMA.items():
        if key in COMPANY_KEYS or key.startswith("api_"):
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
    st.session_state["_saved_fingerprint"] = _fingerprint(get_project_snapshot())


def close_project():
    save_current()
    _clear_project_state()
    st.session_state.pop("_project_id", None)
    st.session_state.pop("_project_name", None)
    st.session_state.pop("_saved_fingerprint", None)


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
                    + (f"  \n  <span style='color:#64748B;font-size:12px'>"
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
    st.markdown(f"### {t('proj.title')}")
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
                    new_id = db.create_project(
                        name.strip(), get_project_snapshot(), reference.strip(), entity.strip()
                    )
                    st.session_state["_project_id"] = new_id
                    st.session_state["_project_name"] = name.strip()
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
                    f"<br><span style='color:#64748B;font-size:12px'>{meta}</span>",
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
                            db.delete_project(proj["id"])
                            st.session_state.pop(confirm_key, None)
                            st.rerun()
                else:
                    if st.button(t("common.delete"), key=f"del_{proj['id']}",
                                 width="stretch", disabled=not may_delete,
                                 help=None if may_delete else t("role.forbidden")):
                        st.session_state[confirm_key] = True
                        st.rerun()
