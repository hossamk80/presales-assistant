"""
utils/db/projects.py — المنافسات: حفظها وتحميلها · سير الاعتماد (13-8) · نسخ الأقسام (13-6) · سجل التدقيق (13-5).
"""

import json
from typing import Any, Optional

from ._core import _now, _scope, get_conn, transaction


# ─── المنافسات ────────────────────────────────────────────────────────────────


def list_projects(company_id: Optional[int] = None) -> list:
    """
    منافسات الشركة الفاعلة (ب-8).

    الترشيح هنا لا في الواجهة: قائمةٌ تُرشَّح في الشاشة تبقى كاملةً في كل
    استعلام آخر يمرّ من تحتها — والتقييد يجب أن يكون في الطبقة التي تُقرأ منها.
    """
    scope = _scope(company_id)
    rows = get_conn().execute(
        "SELECT id, name, reference, entity, sector, created_at, updated_at, "
        "outcome, outcome_note FROM projects WHERE company_id = ? "
        "ORDER BY updated_at DESC",
        (scope,),
    ).fetchall()
    return [dict(r) for r in rows]


def set_outcome(project_id: int, outcome: str, note: str = ""):
    """يسجّل نتيجة المنافسة وسببها — مصدر ذاكرة العطاءات الوحيد."""
    with transaction() as conn:
        conn.execute(
            "UPDATE projects SET outcome = ?, outcome_note = ? "
            "WHERE id = ? AND company_id = ?",
            (outcome, note, project_id, _scope()),
        )


def create_project(name: str, payload: dict, reference: str = "", entity: str = "",
                   sector: str = "", company_id: Optional[int] = None) -> int:
    scope = _scope(company_id)
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO projects (name, reference, entity, sector, created_at, "
            "updated_at, payload, company_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (name, reference, entity, sector, _now(), _now(),
             json.dumps(payload, ensure_ascii=False), scope),
        )
        return cur.lastrowid


def load_project(project_id: int) -> Optional[dict]:
    """
    منافسة بمعرّفها — **من الشركة الفاعلة وحدها**.

    المعرّفات تأتي من قائمة مرشَّحة، لكن الجلسة تحمل معرّف المنافسة المفتوحة
    عبر تبديل الشركة: بلا هذا الشرط يبقى عرض الكيان الأول مفتوحاً تحت اسم
    الكيان الثاني، ويُحفظ عليه.
    """
    row = get_conn().execute(
        "SELECT * FROM projects WHERE id = ? AND company_id = ?",
        (project_id, _scope()),
    ).fetchone()
    if row is None:
        return None
    data = dict(row)
    data["payload"] = json.loads(data["payload"])
    return data


def project_revision(project_id: int) -> Optional[int]:
    row = get_conn().execute(
        "SELECT revision FROM projects WHERE id = ? AND company_id = ?",
        (project_id, _scope()),
    ).fetchone()
    return None if row is None else int(row["revision"] or 0)


def save_project(project_id: int, payload: dict, name: Optional[str] = None,
                 reference: Optional[str] = None, entity: Optional[str] = None,
                 expected_revision: Optional[int] = None,
                 sector: Optional[str] = None) -> Optional[int]:
    """
    يحفظ المنافسة ويعيد رقم مراجعتها الجديد.

    **حفظ مشروط (13-7)**: عند تمرير `expected_revision` لا تُكتب الحمولة إلا إن
    كانت المراجعة المخزَّنة مطابقة لما رآه المُحرِّر آخر مرة، ويعيد `None` إن
    تغيّرت — أي أن جلسة أخرى كتبت بينهما. الشرط والكتابة في جملة `UPDATE`
    واحدة، فلا فجوة بين الفحص والكتابة تمرّ منها جلسة ثالثة.

    بلا `expected_revision` يبقى السلوك القديم: كتابة غير مشروطة.
    """
    sets = ["updated_at = ?", "payload = ?", "revision = revision + 1"]
    args: list[Any] = [_now(), json.dumps(payload, ensure_ascii=False)]
    for column, value in (("name", name), ("reference", reference),
                          ("entity", entity), ("sector", sector)):
        if value is not None:
            sets.append(f"{column} = ?")
            args.append(value)
    args.append(project_id)
    args.append(_scope())

    # ب-8: الكتابة مقيَّدة كالقراءة. الجلسة تحمل معرّف المنافسة المفتوحة عبر
    # تبديل الشركة، والحفظ التلقائي يعمل بلا سؤال — فبلا هذا الشرط يُكتب في
    # منافسة كيانٍ آخر من جلسةٍ انتقلت عنه.
    where = "id = ? AND company_id = ?"
    if expected_revision is not None:
        where += " AND revision = ?"
        args.append(expected_revision)

    with transaction() as conn:
        cur = conn.execute(f"UPDATE projects SET {', '.join(sets)} WHERE {where}", args)
        if cur.rowcount == 0:
            return None
    return project_revision(project_id)


def delete_project(project_id: int):
    with transaction() as conn:
        conn.execute("DELETE FROM projects WHERE id = ? AND company_id = ?",
                     (project_id, _scope()))


def duplicate_project(project_id: int, new_name: str) -> Optional[int]:
    src = load_project(project_id)
    if src is None:
        return None
    return create_project(new_name, src["payload"], src["reference"], src["entity"])


# ─── سير الاعتماد (13-8) ──────────────────────────────────────────────────────

# ثلاث مراحل بترتيبها. المفاتيح ثابتة لا تُترجم — التسميات في `i18n` تحت
# `ap.stage_<key>`، فقرار مخزَّن لا يتغيّر بتغيّر لغة قارئه.
APPROVAL_STAGES = ("bid_manager", "finance", "final")


APPROVED = "approved"


REJECTED = "rejected"


def record_approval(project_id: int, stage: str, decision: str, revision: int,
                    user_id: Optional[int] = None, username: str = "",
                    note: str = "") -> Optional[int]:
    """يسجّل قراراً على مرحلة. القرار السابق يُنقض بهذا لا يُحذف."""
    if stage not in APPROVAL_STAGES or decision not in (APPROVED, REJECTED):
        return None
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO approvals (project_id, stage, decision, revision, "
            "created_at, user_id, username, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (project_id, stage, decision, int(revision or 0), _now(), user_id,
             username, note),
        )
        return cur.lastrowid


def list_approvals(project_id: int, limit: int = 100) -> list:
    rows = get_conn().execute(
        "SELECT * FROM approvals WHERE project_id = ? ORDER BY id DESC LIMIT ?",
        (project_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def approval_state(project_id: int, revision: Optional[int] = None) -> dict:
    """
    حالة كل مرحلة الآن: آخر قرار عليها، وهل سقط لأن العرض تغيّر بعده.

    `stale` هو بيت القصيد: اعتماد على مراجعة أقدم ليس اعتماداً لما يُصدَّر اليوم.
    """
    if revision is None:
        revision = project_revision(project_id) or 0

    state = {}
    for stage in APPROVAL_STAGES:
        row = get_conn().execute(
            "SELECT * FROM approvals WHERE project_id = ? AND stage = ? "
            "ORDER BY id DESC LIMIT 1",
            (project_id, stage),
        ).fetchone()
        if row is None:
            state[stage] = {"decision": "", "username": "", "created_at": "",
                            "note": "", "revision": None, "stale": False}
            continue
        entry = dict(row)
        entry["stale"] = (entry["decision"] == APPROVED
                          and int(entry["revision"] or 0) != int(revision))
        state[stage] = entry
    return state


def approvals_complete(project_id: int, revision: Optional[int] = None) -> bool:
    """المراحل الثلاث معتمَدة على المراجعة الحالية — شرط التصدير النهائي."""
    state = approval_state(project_id, revision)
    return all(
        state[stage]["decision"] == APPROVED and not state[stage]["stale"]
        for stage in APPROVAL_STAGES
    )


def next_approval_stage(project_id: int, revision: Optional[int] = None) -> Optional[str]:
    """المرحلة التالية المطلوبة، أو `None` إن اكتملت كلها."""
    state = approval_state(project_id, revision)
    for stage in APPROVAL_STAGES:
        if state[stage]["decision"] != APPROVED or state[stage]["stale"]:
            return stage
    return None


def delete_approvals(project_id: int) -> int:
    """تُستدعى عند حذف المنافسة — قراراتها تذهب معها."""
    with transaction() as conn:
        cur = conn.execute("DELETE FROM approvals WHERE project_id = ?", (project_id,))
        return cur.rowcount


# ─── نسخ الأقسام (13-6) ───────────────────────────────────────────────────────

# أقصى عدد نسخ محفوظة لكل قسم. الأقدم يسقط تلقائياً — سجل بلا حدّ يُثقل القاعدة
# بنص لا يعود إليه أحد، والحاجة العملية هي الرجوع خطوات لا أشهراً.
SECTION_VERSION_LIMIT = 30


def add_section_version(section_key: str, content: str,
                        project_id: Optional[int] = None, user_id: Optional[int] = None,
                        username: str = "", source: str = "human") -> Optional[int]:
    """
    يحفظ نسخة من نص القسم. يعيد `None` إن كان النص مطابقاً لأحدث نسخة.

    التكرار مرفوض عمداً: دورة رسم تعيد الحفظ بلا تغيير لا يجوز أن تُنتج نسخة
    تُزحزح نسخة حقيقية خارج الحدّ.
    """
    latest = list_section_versions(section_key, project_id, limit=1)
    if latest and latest[0]["content"] == content:
        return None

    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO section_versions (project_id, section_key, created_at, "
            "user_id, username, source, content) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (project_id, section_key, _now(), user_id, username,
             source if source in ("human", "ai") else "human", content),
        )
        new_id = cur.lastrowid

    prune_section_versions(section_key, project_id)
    return new_id


def list_section_versions(section_key: str, project_id: Optional[int] = None,
                          limit: int = SECTION_VERSION_LIMIT) -> list:
    """أحدث النسخ أولاً."""
    rows = get_conn().execute(
        "SELECT * FROM section_versions WHERE section_key = ? "
        "AND project_id IS ? ORDER BY id DESC LIMIT ?",
        (section_key, project_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def get_section_version(version_id: int) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM section_versions WHERE id = ?", (version_id,)
    ).fetchone()
    return dict(row) if row else None


def prune_section_versions(section_key: str, project_id: Optional[int] = None,
                           keep: int = SECTION_VERSION_LIMIT) -> int:
    """يُسقط أقدم النسخ فوق الحدّ. يعيد عدد ما أُسقط."""
    with transaction() as conn:
        cur = conn.execute(
            "DELETE FROM section_versions WHERE id IN ("
            "  SELECT id FROM section_versions WHERE section_key = ? "
            "  AND project_id IS ? ORDER BY id DESC LIMIT -1 OFFSET ?)",
            (section_key, project_id, keep),
        )
        return cur.rowcount


def delete_section_versions(project_id: int) -> int:
    """تُستدعى عند حذف المنافسة — نسخ أقسامها تذهب معها."""
    with transaction() as conn:
        cur = conn.execute(
            "DELETE FROM section_versions WHERE project_id = ?", (project_id,)
        )
        return cur.rowcount


# ─── سجل التدقيق (13-5) ───────────────────────────────────────────────────────
# إضافة وقراءة فقط. لا تحديث ولا حذف — عمداً.


def add_audit_entry(action: str, username: str = "", user_id: Optional[int] = None,
                    target: str = "", project_id: Optional[int] = None,
                    project_name: str = "", source: str = "human",
                    detail: str = "") -> int:
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO audit_log (created_at, user_id, username, action, target, "
            "project_id, project_name, source, detail) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (_now(), user_id, username, action, target, project_id, project_name,
             source, detail),
        )
        return cur.lastrowid


def list_audit_entries(limit: int = 200, project_id: Optional[int] = None,
                       user_id: Optional[int] = None, action: str = "",
                       target: str = "") -> list:
    """أحدث الأحداث أولاً. المرشّحات تُجمَع بـ AND، وأيّها فارغ يُتجاهل."""
    clauses, args = [], []
    if project_id is not None:
        clauses.append("project_id = ?")
        args.append(project_id)
    if user_id is not None:
        clauses.append("user_id = ?")
        args.append(user_id)
    if action:
        clauses.append("action = ?")
        args.append(action)
    if target:
        clauses.append("target = ?")
        args.append(target)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    args.append(limit)
    rows = get_conn().execute(
        f"SELECT * FROM audit_log {where} ORDER BY id DESC LIMIT ?", args
    ).fetchall()
    return [dict(r) for r in rows]


def count_audit_entries() -> int:
    return get_conn().execute("SELECT COUNT(*) AS n FROM audit_log").fetchone()["n"]


def latest_audit_entry(target: str, project_id: Optional[int] = None) -> Optional[dict]:
    """آخر حدث على هدف بعينه — مصدر جواب «من كتب هذا القسم آخر مرة»."""
    rows = list_audit_entries(limit=1, project_id=project_id, target=target)
    return rows[0] if rows else None
