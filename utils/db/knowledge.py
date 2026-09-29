"""
utils/db/knowledge.py — المعرفة والمحتوى: مستودع المستندات ومتجهاته · البرومبتات (14-1)
· مكتبة المحتوى المعتمد (14-4) · الأشكال (ب-5) · نماذج الجهات (ب-4).
"""

from datetime import datetime, timedelta
from typing import Any, Optional

from ._core import ANY_COMPANY, _now, _scope, get_conn, transaction


# ─── مستودع المعرفة ───────────────────────────────────────────────────────────


def add_kb_document(name: str, category: str, char_count: int,
                    person: str = "") -> int:
    """`person` (13-10): صاحب السيرة الذاتية — يربط المستند بمن يملك حذفه."""
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO kb_documents (name, category, added_at, char_count, "
            "person, company_id) VALUES (?, ?, ?, ?, ?, ?)",
            (name, category, _now(), char_count, (person or "").strip(), _scope()),
        )
        return cur.lastrowid


def add_kb_chunks(doc_id: int, chunks: list, embed_model: str = ""):
    """chunks: [(ordinal, text, dims, embedding_bytes)]"""
    with transaction() as conn:
        conn.executemany(
            "INSERT INTO kb_chunks (doc_id, ordinal, text, dims, embedding, embed_model) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(doc_id, o, t, d, e, embed_model) for o, t, d, e in chunks],
        )


def list_kb_documents() -> list:
    rows = get_conn().execute(
        "SELECT d.*, COUNT(c.id) AS chunks FROM kb_documents d "
        "LEFT JOIN kb_chunks c ON c.doc_id = d.id "
        "WHERE d.company_id = ? "
        "GROUP BY d.id ORDER BY d.added_at DESC",
        (_scope(),),
    ).fetchall()
    return [dict(r) for r in rows]


def all_kb_chunks(categories: Optional[list] = None) -> list:
    """
    مقاطع مستودع الشركة الفاعلة — **وهذا أخطر ترشيح في ب-8**.

    هذه هي الدالّة التي يُبنى منها سياق النموذج: مقطعٌ من مستودع كيانٍ آخر لا
    يُعرض في شاشة ليُلاحَظ، بل يُكتب في عرضٍ باسم كيان لا يملكه — خبرةٌ ليست
    خبرته وشهادةٌ ليست شهادته.
    """
    sql = (
        "SELECT c.id, c.text, c.dims, c.embedding, c.embed_model, "
        "d.name AS doc_name, d.category "
        "FROM kb_chunks c JOIN kb_documents d ON d.id = c.doc_id "
        "WHERE d.company_id = ?"
    )
    args: list[Any] = [_scope()]
    if categories:
        sql += f" AND d.category IN ({','.join('?' * len(categories))})"
        args += list(categories)
    return [dict(r) for r in get_conn().execute(sql, args).fetchall()]


def delete_kb_document(doc_id: int, company_id: Optional[int] = None):
    """
    يحذف مستنداً ومقاطعه من مستودع الشركة الفاعلة.

    `company_id=ANY_COMPANY` للحذف عبر التثبيت كلّه — لحقّ الشخص في الحذف
    (13-10) وحده. ولولا هذا المسار لصار «حُذفت بياناتك» إقراراً كاذباً:
    الحذف المقيَّد يترك سيرته في مستودع كيانٍ لم يكن المستخدم عليه.
    """
    scope = _scope(company_id)
    if scope == ANY_COMPANY:
        with transaction() as conn:
            conn.execute("DELETE FROM kb_chunks WHERE doc_id = ?", (doc_id,))
            conn.execute("DELETE FROM kb_documents WHERE id = ?", (doc_id,))
        return

    with transaction() as conn:
        conn.execute(
            "DELETE FROM kb_chunks WHERE doc_id IN "
            "(SELECT id FROM kb_documents WHERE id = ? AND company_id = ?)",
            (doc_id, scope),
        )
        conn.execute("DELETE FROM kb_documents WHERE id = ? AND company_id = ?",
                     (doc_id, scope))


def kb_stats() -> dict:
    row = get_conn().execute(
        "SELECT (SELECT COUNT(*) FROM kb_documents WHERE company_id = ?) AS docs, "
        "(SELECT COUNT(*) FROM kb_chunks c JOIN kb_documents d ON d.id = c.doc_id "
        " WHERE d.company_id = ?) AS chunks",
        (_scope(), _scope()),
    ).fetchone()
    return dict(row)


# ─── البرومبتات (14-1) ────────────────────────────────────────────────────────


def list_prompts(key: str = "") -> list:
    sql = "SELECT * FROM prompts"
    args: list[Any] = []
    if key:
        sql += " WHERE key = ?"
        args.append(key)
    sql += " ORDER BY key, sector, language"
    return [dict(r) for r in get_conn().execute(sql, args).fetchall()]


def prompt_override(key: str, sector: str = "", language: str = "") -> Optional[dict]:
    """
    التجاوز الساري لهذا المفتاح، أو `None`.

    **الأخص يغلب**: (قطاع ولغة) ← (قطاع) ← (لغة) ← (عام). فبرومبت كُتب لقطاع
    الصحة لا يُزيحه عامٌّ كُتب قبله، ولا العكس.
    """
    for candidate in (
        (sector, language), (sector, ""), ("", language), ("", ""),
    ):
        row = get_conn().execute(
            "SELECT * FROM prompts WHERE key = ? AND sector = ? AND language = ? "
            "AND enabled = 1",
            (key, candidate[0], candidate[1]),
        ).fetchone()
        if row is not None:
            return dict(row)
    return None


def save_prompt(key: str, text: str, agent: str = "", sector: str = "",
                language: str = "", updated_by: str = "") -> int:
    """يحفظ تجاوزاً ويعيد رقم إصداره. الإصدار يزيد مع كل حفظ."""
    existing = get_conn().execute(
        "SELECT version FROM prompts WHERE key = ? AND sector = ? AND language = ?",
        (key, sector, language),
    ).fetchone()
    version = (int(existing["version"]) + 1) if existing else 1

    with transaction() as conn:
        conn.execute(
            "INSERT INTO prompts (key, agent, sector, language, version, text, "
            "enabled, updated_at, updated_by) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?) "
            "ON CONFLICT(key, sector, language) DO UPDATE SET "
            "text = excluded.text, agent = excluded.agent, version = excluded.version, "
            "enabled = 1, updated_at = excluded.updated_at, "
            "updated_by = excluded.updated_by",
            (key, agent, sector, language, version, text, _now(), updated_by),
        )
    return version


def set_prompt_enabled(key: str, enabled: bool, sector: str = "",
                       language: str = "") -> bool:
    """تعطيل تجاوز يعيد العمل بالنص الافتراضي بلا فقد ما كُتب."""
    with transaction() as conn:
        cur = conn.execute(
            "UPDATE prompts SET enabled = ? WHERE key = ? AND sector = ? "
            "AND language = ?",
            (1 if enabled else 0, key, sector, language),
        )
        return cur.rowcount > 0


def delete_prompt(key: str, sector: str = "", language: str = "") -> bool:
    """استعادة الافتراضي: يُحذف التجاوز فيعود النص من الشيفرة."""
    with transaction() as conn:
        cur = conn.execute(
            "DELETE FROM prompts WHERE key = ? AND sector = ? AND language = ?",
            (key, sector, language),
        )
        return cur.rowcount > 0


# ─── مكتبة المحتوى المعتمد (14-4) ─────────────────────────────────────────────
#
# كتل جاهزة تُدرَج في أقسام العرض **بلا استدعاء نموذج**. الطبقة هنا لا تعرف
# Streamlit ولا تلمس نص القسم — الإدراج نفسه في `views/doc_builder.py`.

BLOCK_DRAFT = "draft"


BLOCK_APPROVED = "approved"


BLOCK_RETIRED = "retired"


BLOCK_STATUSES = (BLOCK_DRAFT, BLOCK_APPROVED, BLOCK_RETIRED)


# دورة المراجعة الافتراضية بالأشهر. صفر = بلا دورة معلنة فلا تتأخّر الكتلة.
DEFAULT_REVIEW_MONTHS = 12


def _block_row(block_id: int):
    return get_conn().execute(
        "SELECT * FROM content_blocks WHERE id = ?", (int(block_id),)
    ).fetchone()


def get_content_block(block_id: int) -> Optional[dict]:
    row = _block_row(block_id)
    return dict(row) if row is not None else None


def content_block_by_key(key: str) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM content_blocks WHERE key = ?", ((key or "").strip(),)
    ).fetchone()
    return dict(row) if row is not None else None


def list_content_blocks(status: str = "", category: str = "", sector: str = "",
                        language: str = "") -> list:
    """
    كتل المكتبة مرشّحة اختيارياً. `sector` و `language` يُطابقان **الموسَّع
    أيضاً**: كتلة بلا قطاع تصلح لكل القطاعات، فحصرها على المطابق التام يُخفي
    عن كاتب قطاع الصحة كل ما كُتب ليصلح للجميع.
    """
    sql = "SELECT * FROM content_blocks WHERE 1 = 1"
    args: list[Any] = []
    if status:
        sql += " AND status = ?"
        args.append(status)
    if category:
        sql += " AND category = ?"
        args.append(category)
    if sector:
        sql += " AND sector IN ('', ?)"
        args.append(sector)
    if language:
        sql += " AND language IN ('', ?)"
        args.append(language)
    sql += " ORDER BY category, title, key"
    return [dict(r) for r in get_conn().execute(sql, args).fetchall()]


def block_review_due(block: dict) -> bool:
    """
    هل تأخّرت الكتلة عن مراجعتها؟

    بلا دورة معلنة (صفر) لا شيء يتأخّر. وكتلة معتمدة بلا تاريخ مراجعة تُعدّ
    متأخّرة: «معتمد ولا نعرف متى» أسوأ من «معتمد ومضى عليه عام».
    """
    try:
        months = int(block.get("review_months") or 0)
    except (TypeError, ValueError):
        months = 0
    if months <= 0:
        return False

    reviewed = str(block.get("reviewed_at") or "").strip()
    if not reviewed:
        return True
    try:
        stamp = datetime.strptime(reviewed[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return True
    return datetime.now() - stamp > timedelta(days=30 * months)


def approved_blocks(sector: str = "", language: str = "") -> list:
    """
    ما يجوز إدراجه: المعتمد وحده. المسودّة والمسحوبة تبقيان في المكتبة للتحرير
    ولا تصلان إلى قسم — وهذا الفرق بين مكتبة معتمدة ومجلّد قصاصات.

    الترتيب يُنزل المتأخّر عن مراجعته إلى الآخر: يُدرَج بتحذير، ولا يُقترَح أولاً.
    """
    blocks = list_content_blocks(status=BLOCK_APPROVED, sector=sector,
                                 language=language)
    return sorted(blocks, key=lambda b: (block_review_due(b), b.get("title", "")))


def save_content_block(key: str, title: str, body: str, category: str = "",
                       sector: str = "", language: str = "",
                       review_months: Optional[int] = None,
                       updated_by: str = "") -> Optional[int]:
    """
    ينشئ كتلة أو يعدّلها، ويعيد معرّفها (أو `None` لمفتاح فارغ).

    **تغيير النصّ يُسقط الاعتماد** ويمسح تاريخ المراجعة: المعتمَد هو النصّ الذي
    قُرئ لا المفتاح الذي يحمله. أمّا تغيير العنوان أو التصنيف فلا يمسّ الاعتماد —
    إسقاطه لتصحيح حرف في عنوان يجعل الكتّاب يتجنّبون التصحيح.
    """
    key = (key or "").strip()
    if not key:
        return None
    body = body or ""
    now = _now()

    existing = content_block_by_key(key)
    if existing is None:
        months = (DEFAULT_REVIEW_MONTHS if review_months is None
                  else max(0, int(review_months)))
        with transaction() as conn:
            cur = conn.execute(
                "INSERT INTO content_blocks (key, title, body, category, sector, "
                "language, status, review_months, created_at, updated_at, updated_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (key, title or "", body, category or "", sector or "",
                 language or "", BLOCK_DRAFT, months, now, now, updated_by),
            )
            return int(cur.lastrowid)

    months = (int(existing["review_months"]) if review_months is None
              else max(0, int(review_months)))
    body_changed = body != (existing["body"] or "")
    status = BLOCK_DRAFT if body_changed else existing["status"]
    reviewed_at = "" if body_changed else existing["reviewed_at"]
    reviewed_by = "" if body_changed else existing["reviewed_by"]

    with transaction() as conn:
        conn.execute(
            "UPDATE content_blocks SET title = ?, body = ?, category = ?, "
            "sector = ?, language = ?, status = ?, reviewed_at = ?, "
            "reviewed_by = ?, review_months = ?, updated_at = ?, updated_by = ? "
            "WHERE id = ?",
            (title or "", body, category or "", sector or "", language or "",
             status, reviewed_at, reviewed_by, months, now, updated_by,
             int(existing["id"])),
        )
    return int(existing["id"])


def set_block_status(block_id: int, status: str, username: str = "") -> bool:
    """
    يغيّر حالة الكتلة. الاعتماد يختم **تاريخ مراجعة** معه: كتلة تُعتمد اليوم
    مراجَعة اليوم، فلا تُولد متأخّرة عن دورتها.
    """
    if status not in BLOCK_STATUSES:
        return False
    row = _block_row(block_id)
    if row is None:
        return False

    reviewed_at = _now() if status == BLOCK_APPROVED else row["reviewed_at"]
    reviewed_by = username if status == BLOCK_APPROVED else row["reviewed_by"]
    with transaction() as conn:
        conn.execute(
            "UPDATE content_blocks SET status = ?, reviewed_at = ?, "
            "reviewed_by = ?, updated_at = ? WHERE id = ?",
            (status, reviewed_at, reviewed_by, _now(), int(block_id)),
        )
    return True


def mark_block_reviewed(block_id: int, username: str = "") -> bool:
    """
    «راجعتُها ولم تتغيّر» — يجدّد التاريخ بلا لمس النصّ ولا الحالة. بدونه كان
    تأكيد صلاحية كتلة يستلزم تعديلاً وهمياً يُسقط اعتمادها.
    """
    if _block_row(block_id) is None:
        return False
    with transaction() as conn:
        conn.execute(
            "UPDATE content_blocks SET reviewed_at = ?, reviewed_by = ?, "
            "updated_at = ? WHERE id = ?",
            (_now(), username, _now(), int(block_id)),
        )
    return True


def record_block_use(block_id: int) -> int:
    """يزيد عدّاد الاستخدام ويعيد قيمته الجديدة (أو صفراً لكتلة غير موجودة)."""
    with transaction() as conn:
        cur = conn.execute(
            "UPDATE content_blocks SET used_count = used_count + 1 WHERE id = ?",
            (int(block_id),),
        )
        if not cur.rowcount:
            return 0
    row = _block_row(block_id)
    return int(row["used_count"]) if row is not None else 0


def delete_content_block(block_id: int) -> bool:
    with transaction() as conn:
        cur = conn.execute(
            "DELETE FROM content_blocks WHERE id = ?", (int(block_id),)
        )
        return cur.rowcount > 0


def content_block_stats() -> dict:
    """عدّاد لكل حالة + كم كتلة تأخّرت عن مراجعتها."""
    blocks = list_content_blocks()
    stats = {status: 0 for status in BLOCK_STATUSES}
    for block in blocks:
        if block["status"] in stats:
            stats[block["status"]] += 1
    stats["total"] = len(blocks)
    stats["due"] = sum(1 for b in blocks
                       if b["status"] == BLOCK_APPROVED and block_review_due(b))
    stats["used"] = sum(int(b["used_count"] or 0) for b in blocks)
    return stats


# ─── الأشكال: مخططات العرض وصوره (ب-5) ────────────────────────────────────────


def list_figures(project_id: Optional[int] = None,
                 with_images: bool = False) -> list:
    """
    أشكال المنافسة مرتّبةً بقسمها ثم بترتيبها داخله.

    الحمولات **لا تُحمَّل افتراضياً**: القائمة تُرسم في كل دورة، وصورة بحجم
    ميغابايت تُقرأ من القرص عبثاً في كل مرة. `with_images` لبنّاء المستند وحده.
    """
    columns = "*" if with_images else (
        "id, project_id, section_key, caption, mime, filename, ordinal, "
        "created_at, LENGTH(image) AS size"
    )
    sql = f"SELECT {columns} FROM figures"
    args: list[Any] = []
    if project_id is not None:
        sql += " WHERE project_id = ?"
        args.append(int(project_id))
    sql += " ORDER BY section_key, ordinal, id"
    return [dict(r) for r in get_conn().execute(sql, args).fetchall()]


def add_figure(project_id: Optional[int], section_key: str, image: bytes,
               caption: str = "", mime: str = "", filename: str = "") -> Optional[int]:
    """
    يضيف شكلاً في آخر قسمه. يعيد `None` لصورة فارغة.

    الترتيب داخل القسم يُحسب من الموجود لا من عدّاد محفوظ: حذف شكل لا يترك
    فجوةً يقع فيها الشكل التالي.
    """
    if not image:
        return None
    row = get_conn().execute(
        "SELECT MAX(ordinal) AS last FROM figures WHERE project_id IS ? "
        "AND section_key = ?",
        (project_id, str(section_key or "")),
    ).fetchone()
    ordinal = int((row["last"] if row and row["last"] is not None else -1)) + 1

    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO figures (project_id, section_key, caption, image, mime, "
            "filename, ordinal, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (project_id, str(section_key or ""), caption or "", image,
             mime or "", filename or "", ordinal, _now()),
        )
        return int(cur.lastrowid)


def update_figure(figure_id: int, caption: Optional[str] = None,
                  section_key: Optional[str] = None,
                  ordinal: Optional[int] = None) -> bool:
    sets, args = [], []
    for column, value in (("caption", caption), ("section_key", section_key)):
        if value is not None:
            sets.append(f"{column} = ?")
            args.append(str(value))
    if ordinal is not None:
        sets.append("ordinal = ?")
        args.append(int(ordinal))
    if not sets:
        return False
    args.append(int(figure_id))
    with transaction() as conn:
        cur = conn.execute(
            f"UPDATE figures SET {', '.join(sets)} WHERE id = ?", args
        )
        return cur.rowcount > 0


def delete_figure(figure_id: int) -> bool:
    with transaction() as conn:
        cur = conn.execute("DELETE FROM figures WHERE id = ?", (int(figure_id),))
        return cur.rowcount > 0


def delete_project_figures(project_id: int) -> int:
    with transaction() as conn:
        cur = conn.execute(
            "DELETE FROM figures WHERE project_id = ?", (int(project_id),)
        )
        return cur.rowcount


# ─── نماذج الجهات (ب-4) ───────────────────────────────────────────────────────


def _entity_key(name: str) -> str:
    """
    مفتاح الجهة مُوحَّداً — نفس توحيد ذاكرة العطاءات (12-7) لا توحيدٌ ثانٍ.

    قاعدتان لتوحيد الاسم تعنيان جهةً واحدة تُطابَق هنا ولا تُطابَق هناك.
    """
    from utils import history

    return history.normalize_entity(name)


def list_entity_templates() -> list:
    """النماذج المحفوظة بلا حمولاتها — القائمة تُعرض ولا تُحمَّل الملفات لها."""
    rows = get_conn().execute(
        "SELECT id, entity_key, entity_label, filename, updated_at, updated_by, "
        "LENGTH(template) AS size FROM entity_templates "
        "ORDER BY entity_label COLLATE NOCASE"
    ).fetchall()
    return [dict(r) for r in rows]


def entity_template(entity: str) -> Optional[dict]:
    """نموذج هذه الجهة بحمولته، أو `None`."""
    key = _entity_key(entity)
    if not key:
        return None
    row = get_conn().execute(
        "SELECT * FROM entity_templates WHERE entity_key = ?", (key,)
    ).fetchone()
    return dict(row) if row is not None else None


def save_entity_template(entity: str, template: bytes, filename: str = "",
                         updated_by: str = "") -> Optional[int]:
    """يحفظ نموذج جهة (أو يستبدله). يعيد `None` لاسم فارغ أو ملف فارغ."""
    key = _entity_key(entity)
    if not key or not template:
        return None
    label = str(entity or "").strip()
    with transaction() as conn:
        conn.execute(
            "INSERT INTO entity_templates (entity_key, entity_label, filename, "
            "template, updated_at, updated_by) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(entity_key) DO UPDATE SET entity_label = excluded.entity_label, "
            "filename = excluded.filename, template = excluded.template, "
            "updated_at = excluded.updated_at, updated_by = excluded.updated_by",
            (key, label, filename or "", template, _now(), updated_by),
        )
    row = entity_template(entity)
    return int(row["id"]) if row else None


def delete_entity_template(entity: str) -> bool:
    key = _entity_key(entity)
    if not key:
        return False
    with transaction() as conn:
        cur = conn.execute(
            "DELETE FROM entity_templates WHERE entity_key = ?", (key,)
        )
        return cur.rowcount > 0
