"""
utils/audit.py — سجل التدقيق (13-5)

كل تغيير قابل للتتبّع لشخص ووقت. الطبقة هنا تعرف **من** يفعل و**في أي منافسة**
فتملأهما تلقائياً، فلا يحمل كل موضع استدعاء هذا العبء ولا ينساه.

**السجل يُضاف إليه ولا يُعدَّل**: لا دالة تحديث ولا حذف هنا ولا في `db`. سجل
يُنقّح ليس سجلاً.

**مصدر النص**: الحدث يحمل `source` — `ai` لما ولّده النموذج و `human` لما كتبه
إنسان. `section_source` تجيب عن «هذه الفقرة، مصدرها النموذج أم الكاتب؟» من آخر
حدث على القسم، وهو سؤال لجان الفحص لا سؤال فضول.

**التسجيل لا يُسقط العمل**: فشل الكتابة في السجل يُبتلع. أن يفشل حفظ منافسة
لأن سطر تدقيق تعذّر أسوأ من أثر ناقص.

Audit trail: who changed what, when, and which text came from the model.
"""
from typing import Optional

import streamlit as st

from utils import db

HUMAN = "human"
AI = "ai"

# الأحداث المسجَّلة. النص هنا مفتاح لا رسالة — الترجمة في `i18n` تحت
# `audit.act_<action>`، فسجل مخزَّن لا يتغيّر بتغيّر لغة قارئه.
PROJECT_CREATE = "project.create"
PROJECT_DELETE = "project.delete"
PROJECT_DUPLICATE = "project.duplicate"
PROJECT_OUTCOME = "project.outcome"
PROJECT_MERGE = "project.merge"
SECTION_GENERATE = "section.generate"
SECTION_REFINE = "section.refine"
SECTION_EDIT = "section.edit"
SECTION_RESTORE = "section.restore"
SECTION_ASSIGN = "section.assign"
SECTION_STATUS = "section.status"
OUTLINE_PROPOSE = "outline.propose"
EXPORT_BUILD = "export.build"
APPROVAL_DECISION = "approval.decision"
BACKUP_CREATE = "backup.create"
BACKUP_RESTORE = "backup.restore"
PD_POLICY = "pd.policy"
PD_ERASE = "pd.erase"
USER_ADD = "user.add"
USER_ROLE = "user.role"
USER_ACTIVE = "user.active"
USER_DELETE = "user.delete"
USER_PASSWORD = "user.password"
AUTH_LOGIN = "auth.login"

ACTIONS = (
    PROJECT_CREATE, PROJECT_DELETE, PROJECT_DUPLICATE, PROJECT_OUTCOME,
    PROJECT_MERGE,
    SECTION_GENERATE, SECTION_REFINE, SECTION_EDIT, SECTION_RESTORE, SECTION_ASSIGN,
    SECTION_STATUS, OUTLINE_PROPOSE, EXPORT_BUILD, APPROVAL_DECISION,
    BACKUP_CREATE, BACKUP_RESTORE, PD_POLICY, PD_ERASE,
    USER_ADD, USER_ROLE, USER_ACTIVE, USER_DELETE, USER_PASSWORD, AUTH_LOGIN,
)

# الأحداث التي تُغيّر نص قسم — منها وحدها يُستنتج مصدر الفقرة.
_CONTENT_ACTIONS = (SECTION_GENERATE, SECTION_REFINE, SECTION_EDIT,
                    SECTION_RESTORE)


def _actor() -> tuple:
    """(المعرّف، الاسم الظاهر) للمستخدم الحالي — أو مجهول إن لم توجد جلسة."""
    from utils import auth

    user = auth.current_user()
    if user is None:
        return None, ""
    return user["id"], (user.get("display_name") or user["username"])


def record(action: str, target: str = "", source: str = HUMAN,
           detail: str = "", project_id: Optional[int] = None,
           project_name: str = "") -> bool:
    """
    يسجّل حدثاً. يعيد `True` إن كُتب.

    المنافسة تُقرأ من الجلسة ما لم تُمرَّر صراحةً — الحدث بلا منافسته لا يُقرأ.
    """
    user_id, username = _actor()
    if project_id is None:
        project_id = st.session_state.get("_project_id")
        project_name = project_name or st.session_state.get("_project_name", "")

    try:
        db.add_audit_entry(
            action=action, username=username, user_id=user_id, target=target,
            project_id=project_id, project_name=project_name,
            source=source if source in (HUMAN, AI) else HUMAN, detail=detail,
        )
        return True
    except Exception:
        # أثر ناقص أهون من عمل ضائع
        return False


def entries(limit: int = 200, project_id: Optional[int] = None,
            user_id: Optional[int] = None, action: str = "") -> list:
    return db.list_audit_entries(
        limit=limit, project_id=project_id, user_id=user_id, action=action
    )


def section_target(section_key: str) -> str:
    return f"section:{section_key}"


def section_source(section_key: str, project_id: Optional[int] = None) -> str:
    """
    مصدر نص القسم كما يقوله آخر حدث عليه: `ai` · `human` · `""` إن لم يُسجَّل.

    آخر حدث لا مجموعها: نصٌّ ولّده النموذج ثم حرّره إنسان صار مسؤولية إنسان.
    """
    if project_id is None:
        project_id = st.session_state.get("_project_id")

    for entry in db.list_audit_entries(
        limit=20, project_id=project_id, target=section_target(section_key)
    ):
        if entry["action"] in _CONTENT_ACTIONS:
            return entry["source"]
    return ""


def snapshot_section(section_key: str, content: str, source: str = HUMAN,
                     project_id: Optional[int] = None) -> Optional[int]:
    """
    يحفظ نسخة من نص القسم (13-6).

    هنا لا في وحدة ثالثة: هذه الطبقة تعرف الفاعل والمنافسة أصلاً، والنسخة هي
    **ماذا كان** لحدث تعرف هي **من فعله**. فشلها كفشل التسجيل — يُبتلع.
    """
    user_id, username = _actor()
    if project_id is None:
        project_id = st.session_state.get("_project_id")
    try:
        return db.add_section_version(
            section_key, content or "", project_id=project_id, user_id=user_id,
            username=username, source=source,
        )
    except Exception:
        return None


def record_section_edits(before: dict, after: dict, keys) -> int:
    """
    يسجّل الأقسام التي تغيّر نصّها بين لقطتين — يُستدعى من الحفظ.

    التسجيل عند الحفظ لا عند كل ضغطة: كل دورة رسم في Streamlit تعيد قراءة
    الحقل، فتسجيلها جميعاً يُغرق السجل بما لا يُقرأ.
    """
    written = 0
    for key in keys:
        state_key = f"sec_{key}"
        old = str((before or {}).get(state_key, "") or "")
        new = str((after or {}).get(state_key, "") or "")
        if old == new:
            continue
        # التوليد والتنقيح يُسجّلان عند حدوثهما بمصدر النموذج؛ ما يصل هنا بعدهما
        # هو تحرير إنسان لنصّ صار مسؤوليته
        record(SECTION_EDIT, target=section_target(key), source=HUMAN,
               detail=str(len(new) - len(old)))
        # 13-6: ومعه نسخة من النص الجديد — نقطة الرصد واحدة لكليهما
        snapshot_section(key, new, source=HUMAN)
        written += 1
    return written
