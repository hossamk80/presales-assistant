"""
views/projects.py — إدارة المنافسات المحفوظة

كل منافسة مشروع مستقل: كراسته وتحليلاته وأقسامه وجداوله وملاحظات مراجعته.
التبديل بين المنافسات يحفظ الحالية أولاً حتى لا يضيع عمل.
"""
import json
import streamlit as st

from utils import db
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
    """يحفظ المنافسة المفتوحة. يُرجع False إن لم تكن هناك واحدة."""
    pid = current_project_id()
    if pid is None:
        return False
    snapshot = get_project_snapshot()
    db.save_project(pid, snapshot)
    st.session_state["_saved_fingerprint"] = _fingerprint(snapshot)
    if show_toast:
        st.toast(t("proj.saved"))
    return True


def _fingerprint(snapshot: dict) -> str:
    return json.dumps(snapshot, ensure_ascii=False, sort_keys=True, default=str)


def autosave():
    """
    حفظ تلقائي عند تغيّر الحالة. يُستدعى في نهاية كل دورة رسم، فيبقى العمل
    محفوظاً دون أن يتذكّر المستخدم الضغط على زر.
    """
    if current_project_id() is None:
        return
    try:
        snapshot = get_project_snapshot()
        fingerprint = _fingerprint(snapshot)
        if fingerprint != st.session_state.get("_saved_fingerprint"):
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
    for key in [k for k in list(st.session_state) if k.startswith(("sec_ai_", "ta_", "de_", "inc_"))]:
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
            if st.form_submit_button(t("proj.create"), type="primary"):
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
                    st.success(t("proj.created", name=name.strip()))
                    st.rerun()

    # ── قائمة المنافسات ───────────────────────────────────────────────────────
    projects = db.list_projects()
    if not projects:
        return

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
                if st.button(t("common.copy"), key=f"dup_{proj['id']}", width="stretch"):
                    db.duplicate_project(proj["id"], f"{proj['name']} {t('proj.copy_suffix')}")
                    st.rerun()
            with c_del:
                confirm_key = f"confirm_del_{proj['id']}"
                if st.session_state.get(confirm_key):
                    if st.button(t("common.confirm"), key=f"del2_{proj['id']}", width="stretch", type="primary"):
                        if is_open:
                            close_project()
                        db.delete_project(proj["id"])
                        st.session_state.pop(confirm_key, None)
                        st.rerun()
                else:
                    if st.button(t("common.delete"), key=f"del_{proj['id']}", width="stretch"):
                        st.session_state[confirm_key] = True
                        st.rerun()
