"""
utils/db/delivery.py — ما بعد الترسية وما قبلها: تحويل الفائز إلى مشروع (14-11)
ووحدة الاستفسارات (14-9).
"""

from typing import Any, Optional

from ._core import _now, get_conn, transaction


# ─── تحويل الفائز إلى مشروع (14-11) ───────────────────────────────────────────

DELIVERABLE_OPEN = "open"


DELIVERABLE_DONE = "done"


DELIVERABLE_DROPPED = "dropped"


DELIVERABLE_STATUSES = (DELIVERABLE_OPEN, DELIVERABLE_DONE, DELIVERABLE_DROPPED)


# مصدر البند — يقول لمدير التنفيذ **لماذا نحن ملزمون به**
SOURCE_MATRIX = "matrix"


SOURCE_SECTION = "section"


SOURCE_MANUAL = "manual"


def get_delivery(project_id: int) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM deliveries WHERE project_id = ?", (int(project_id),)
    ).fetchone()
    return dict(row) if row is not None else None


def list_deliveries() -> list:
    rows = get_conn().execute(
        "SELECT * FROM deliveries ORDER BY created_at DESC, id DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def create_delivery(project_id: int, name: str = "", entity: str = "",
                    created_by: str = "") -> Optional[int]:
    """
    يحوّل منافسة فائزة إلى مشروع تنفيذ. يعيد `None` إن كانت محوَّلة أصلاً.

    التحويل **مرّة واحدة** (فهرس فريد على `project_id`): تحويل ثانٍ يُنشئ قائمة
    تسليمات موازية، فيصير لكل مشروع حقيقتان ويُنفَّذ على إحداهما ويُسلَّم بالأخرى.
    """
    if get_delivery(project_id) is not None:
        return None
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO deliveries (project_id, name, entity, created_at, "
            "created_by) VALUES (?, ?, ?, ?, ?)",
            (int(project_id), name or "", entity or "", _now(), created_by),
        )
        return int(cur.lastrowid)


def delete_delivery(project_id: int) -> bool:
    """يلغي التحويل ببنوده — يستعمله من حوّل منافسةً بالخطأ."""
    delivery = get_delivery(project_id)
    if delivery is None:
        return False
    with transaction() as conn:
        conn.execute("DELETE FROM deliverables WHERE delivery_id = ?",
                     (int(delivery["id"]),))
        conn.execute("DELETE FROM deliveries WHERE id = ?", (int(delivery["id"]),))
    return True


def list_deliverables(delivery_id: int) -> list:
    """
    بنود التسليم: غير المؤكَّد أولاً.

    ما استخرجه النموذج ولم يُقرَّ بعد يتصدّر القائمة — هو ما ينتظر قراراً، وما
    أُقرّ صار عملاً يُتابَع لا قراراً يُتّخذ.
    """
    rows = get_conn().execute(
        "SELECT * FROM deliverables WHERE delivery_id = ? "
        "ORDER BY confirmed ASC, id ASC",
        (int(delivery_id),),
    ).fetchall()
    return [dict(r) for r in rows]


def add_deliverable(delivery_id: int, title: str, source: str = SOURCE_MANUAL,
                    source_ref: str = "", clause_ref: str = "",
                    confirmed: bool = False) -> Optional[int]:
    title = (title or "").strip()
    if not title:
        return None
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO deliverables (delivery_id, title, source, source_ref, "
            "clause_ref, status, confirmed, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (int(delivery_id), title, source, (source_ref or "").strip(),
             (clause_ref or "").strip(), DELIVERABLE_OPEN,
             1 if confirmed else 0, _now()),
        )
        return int(cur.lastrowid)


def update_deliverable(deliverable_id: int, status: Optional[str] = None,
                       owner: Optional[str] = None, due_at: Optional[str] = None,
                       title: Optional[str] = None,
                       confirmed: Optional[bool] = None) -> bool:
    sets, args = [], []
    if status is not None:
        if status not in DELIVERABLE_STATUSES:
            return False
        sets.append("status = ?")
        args.append(status)
    for column, value in (("owner", owner), ("due_at", due_at), ("title", title)):
        if value is not None:
            sets.append(f"{column} = ?")
            args.append(str(value).strip())
    if confirmed is not None:
        sets.append("confirmed = ?")
        args.append(1 if confirmed else 0)
    if not sets:
        return False
    args.append(int(deliverable_id))
    with transaction() as conn:
        cur = conn.execute(
            f"UPDATE deliverables SET {', '.join(sets)} WHERE id = ?", args
        )
        return cur.rowcount > 0


def delete_deliverable(deliverable_id: int) -> bool:
    with transaction() as conn:
        cur = conn.execute(
            "DELETE FROM deliverables WHERE id = ?", (int(deliverable_id),)
        )
        return cur.rowcount > 0


# ─── وحدة الاستفسارات (14-9) ───────────────────────────────────────────────────

CLARIFY_DRAFT = "draft"


CLARIFY_SENT = "sent"


CLARIFY_ANSWERED = "answered"


CLARIFY_CLOSED = "closed"


CLARIFY_STATUSES = (CLARIFY_DRAFT, CLARIFY_SENT, CLARIFY_ANSWERED, CLARIFY_CLOSED)


def list_clarifications(project_id: Optional[int] = None) -> list:
    """
    استفسارات المنافسة، الأحدث موعداً أولاً ثم الأقدم إنشاءً.

    بلا `project_id` تُعاد كلها — تستعملها الأدوات التي تعمل عبر المنافسات.
    """
    sql = "SELECT * FROM clarifications"
    args: list[Any] = []
    if project_id is not None:
        sql += " WHERE project_id = ?"
        args.append(int(project_id))
    sql += " ORDER BY (due_at = '') ASC, due_at ASC, id ASC"
    return [dict(r) for r in get_conn().execute(sql, args).fetchall()]


def get_clarification(clarification_id: int) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM clarifications WHERE id = ?", (int(clarification_id),)
    ).fetchone()
    return dict(row) if row is not None else None


def add_clarification(project_id: Optional[int], question: str, req_id: str = "",
                      due_at: str = "", created_by: str = "") -> Optional[int]:
    """يسجّل استفساراً جديداً كمسودّة. يعيد معرّفه، أو `None` لسؤال فارغ."""
    question = (question or "").strip()
    if not question:
        return None
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO clarifications (project_id, req_id, question, status, "
            "due_at, created_at, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (project_id, (req_id or "").strip(), question, CLARIFY_DRAFT,
             (due_at or "").strip(), _now(), created_by),
        )
        return int(cur.lastrowid)


def update_clarification(clarification_id: int, question: Optional[str] = None,
                         req_id: Optional[str] = None,
                         due_at: Optional[str] = None) -> bool:
    sets, args = [], []
    for column, value in (("question", question), ("req_id", req_id),
                          ("due_at", due_at)):
        if value is not None:
            sets.append(f"{column} = ?")
            args.append(str(value).strip())
    if not sets:
        return False
    args.append(int(clarification_id))
    with transaction() as conn:
        cur = conn.execute(
            f"UPDATE clarifications SET {', '.join(sets)} WHERE id = ?", args
        )
        return cur.rowcount > 0


def mark_clarification_sent(clarification_id: int) -> bool:
    """
    يُسجّل أن السؤال أُرسل فعلاً إلى الجهة، ويثبّت تاريخ إرساله.

    الفرق بين المسودّة والمُرسَل ليس تجميلاً: سؤال لم يُرسَل غيابُ جوابه ذنبنا
    لا ذنب الجهة، ورصده كـ«متأخّر عن الجهة» يُخفي أنّنا لم نسأل بعد.
    """
    with transaction() as conn:
        cur = conn.execute(
            "UPDATE clarifications SET status = ?, asked_at = ? "
            "WHERE id = ? AND status = ?",
            (CLARIFY_SENT, _now(), int(clarification_id), CLARIFY_DRAFT),
        )
        return cur.rowcount > 0


def answer_clarification(clarification_id: int, answer: str) -> bool:
    """
    يسجّل جواب الجهة. جواب فارغ **لا يُغلق** السؤال.

    «أُجيب» حالة تُبنى عليها قرارات امتثال، فتسجيلها بلا نصّ جواب يجعل المتطلب
    يبدو محسوماً بلا شيء يحسمه.
    """
    answer = (answer or "").strip()
    if not answer:
        return False
    with transaction() as conn:
        cur = conn.execute(
            "UPDATE clarifications SET status = ?, answer = ?, answered_at = ? "
            "WHERE id = ?",
            (CLARIFY_ANSWERED, answer, _now(), int(clarification_id)),
        )
        return cur.rowcount > 0


def close_clarification(clarification_id: int) -> bool:
    """يُغلق سؤالاً سقط سببه — بلا ادّعاء جواب لم يأتِ."""
    with transaction() as conn:
        cur = conn.execute(
            "UPDATE clarifications SET status = ? WHERE id = ?",
            (CLARIFY_CLOSED, int(clarification_id)),
        )
        return cur.rowcount > 0


def delete_clarification(clarification_id: int) -> bool:
    with transaction() as conn:
        cur = conn.execute(
            "DELETE FROM clarifications WHERE id = ?", (int(clarification_id),)
        )
        return cur.rowcount > 0


def delete_project_clarifications(project_id: int) -> int:
    with transaction() as conn:
        cur = conn.execute(
            "DELETE FROM clarifications WHERE project_id = ?", (int(project_id),)
        )
        return cur.rowcount


def project_costs() -> dict:
    """
    كلفة إعداد كل منافسة بالدولار: `{project_id: cost}` (14-7).

    تُقرأ من `ai_usage` لا تُقدَّر: كل استدعاء سُجّلت كلفته وقت وقوعه (11-8).
    منافسة بلا استدعاء **لا ترد هنا أصلاً** ولا ترد بصفر — الصفر كلفة مقيسة،
    والغياب غياب قياس، والخلط بينهما يهبط بالمتوسّط بمنافسات لم تُعالَج بعد.
    """
    rows = get_conn().execute(
        "SELECT project_id, SUM(cost) AS cost FROM ai_usage "
        "WHERE project_id IS NOT NULL GROUP BY project_id"
    ).fetchall()
    return {int(r["project_id"]): float(r["cost"] or 0.0) for r in rows}
