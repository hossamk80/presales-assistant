"""
utils/db.py — التخزين الدائم (SQLite)

قبل هذه الطبقة كان كل شيء في session_state ويضيع بإغلاق المتصفح. الآن:
  · كل منافسة مشروع مستقل له تحليلاته وأقسامه وجداوله وملاحظات مراجعته.
  · ملف الشركة يُحفظ مرة واحدة ويُشارَك بين كل المنافسات.
  · مستودع المعرفة (مستندات + متجهات التضمين) يُحفظ للشركة كذلك.

قاعدة البيانات ملف واحد على القرص — لا خادم ولا خدمة خارجية، اتساقاً مع كون
النظام يعمل محلياً وبيانات العطاءات لا تغادر الجهاز.
"""
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Optional

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(APP_DIR, "data")
DB_PATH = os.environ.get("ANALYST_DB_PATH") or os.path.join(DATA_DIR, "analyst.db")

_local = threading.local()


SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    reference   TEXT DEFAULT '',
    entity      TEXT DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    payload     TEXT NOT NULL
);

-- ملف الشركة (13-1): كان الجدول مقيَّداً بصف واحد `CHECK (id = 1)` لأن النظام
-- بُني لفرد يعمل لشركة واحدة. قسم العطاءات قد يخدم أكثر من كيان (شركة أمّ
-- وذراع تنفيذية، أو مكتب استشاري يعدّ عروضاً لعملائه)، وكل ما بعده —
-- المستخدمون والأدوار وإسناد الأقسام — يفترض قاعدة تحتمل أكثر من شركة.
-- القيد أُلغي، وقاعدة قديمة تُرقّى في `_migrate_company` بلا فقد بيانات.
CREATE TABLE IF NOT EXISTS company (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT '',
    payload    TEXT NOT NULL,
    template   BLOB,
    logo       BLOB
);

CREATE TABLE IF NOT EXISTS kb_documents (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    category   TEXT NOT NULL,
    added_at   TEXT NOT NULL,
    char_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS kb_chunks (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id    INTEGER NOT NULL REFERENCES kb_documents(id) ON DELETE CASCADE,
    ordinal   INTEGER NOT NULL,
    text      TEXT NOT NULL,
    dims      INTEGER NOT NULL,
    embedding BLOB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_kb_chunks_doc ON kb_chunks(doc_id);

-- نسخ المرفقات: الجهات تُصدر تعديلات بعد نشر الكراسة، وكانت الرفعة الجديدة
-- تمحو القديمة بلا أثر — فلا يُعرف ما الذي تغيّر ولا أي متطلب صار على شرط
-- ملغى. كل رفعة تُحفظ نسخةً لتُقارَن بما قبلها.
CREATE TABLE IF NOT EXISTS attachment_versions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    label      TEXT DEFAULT '',
    payload    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_attachment_versions_project
    ON attachment_versions(project_id);

-- قياس الاستهلاك (11-7): كل استدعاء نموذج يُسجَّل من عدّادات الموفّر نفسه
-- لا من تقدير محلي. بدونه لا يمكن إثبات نجاح أي من تحسينات الكلفة.
CREATE TABLE IF NOT EXISTS ai_usage (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    TEXT NOT NULL,
    month         TEXT NOT NULL,
    project_id    INTEGER,
    project_name  TEXT DEFAULT '',
    task          TEXT NOT NULL,
    provider      TEXT NOT NULL,
    model         TEXT NOT NULL,
    input_tokens  INTEGER NOT NULL DEFAULT 0,
    cached_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost          REAL NOT NULL DEFAULT 0,
    elapsed_ms    INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'ok'
);

CREATE INDEX IF NOT EXISTS idx_ai_usage_month ON ai_usage(month);

-- ذاكرة نتائج الاستدعاءات (11-13): بصمة (تعليمات + سياق + نموذج) ← النتيجة.
-- إعادة الضغط على زرّ بلا تغيير معطيات لا تُنفق توكن.
CREATE TABLE IF NOT EXISTS ai_cache (
    fingerprint TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    provider    TEXT NOT NULL,
    model       TEXT NOT NULL,
    result      TEXT NOT NULL
);

-- سجلات الأدلة (المرحلة 12): الكوادر · سابقة الأعمال · الشهادات · الموردون ·
-- الجهات. صفوف تُطابَق بها متطلبات الكراسة بدل نص حر لا يصمد أمام لجنة فحص.
--
-- جدول واحد بحمولة JSON لا خمسة جداول: الأعمدة معلنة في `utils/records.py`،
-- وإضافة حقل هناك لا تستلزم ترحيل قاعدة. السجلات صغيرة (عشرات الصفوف) فلا
-- حاجة إلى فهرسة داخل الحمولة.
CREATE TABLE IF NOT EXISTS company_records (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    registry TEXT NOT NULL,
    ordinal  INTEGER NOT NULL DEFAULT 0,
    payload  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_company_records_registry
    ON company_records(registry);
"""


# أعمدة أُضيفت بعد أول إصدار. CREATE TABLE IF NOT EXISTS لا يُعدّل جدولاً
# قائماً، فقواعد البيانات الموجودة تحتاج إضافتها صراحةً.
_ADDED_COLUMNS = (
    ("projects", "outcome", "TEXT DEFAULT ''"),
    ("projects", "outcome_note", "TEXT DEFAULT ''"),
    # 11-6: تغيير نموذج التضمين يُبطل المتجهات المخزَّنة. نحفظ اسم النموذج
    # مع كل مقطع حتى نعدّ المقاطع المعطَّلة صراحةً بدل إهمالها صامتةً.
    ("kb_chunks", "embed_model", "TEXT DEFAULT ''"),
    # 13-1: الشركة صارت صفاً من صفوف لا صفاً وحيداً، فلها اسم وتاريخ إنشاء.
    ("company", "name", "TEXT NOT NULL DEFAULT ''"),
    ("company", "created_at", "TEXT NOT NULL DEFAULT ''"),
)

# أعمدة جدول الشركة بترتيبها في المخطط الحالي — يستعملها الترحيل لنقل ما
# يوجد منها في القاعدة القديمة ويترك الباقي لقيمته الافتراضية.
_COMPANY_COLUMNS = ("id", "name", "created_at", "payload", "template", "logo")


def _migrate_company(conn: sqlite3.Connection):
    """
    يُلغي قيد الصف الواحد `CHECK (id = 1)` من قاعدة أُنشئت قبل 13-1.

    SQLite لا يُسقط قيداً بـ ALTER TABLE، فالسبيل الوحيد إعادة بناء الجدول:
    جدول جديد بالمخطط الحالي ← نسخ الصفوف الموجودة ← إسقاط القديم ← تسمية.
    كل ذلك داخل معاملة واحدة، فإن فشل شيء بقيت القاعدة القديمة كما هي.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'company'"
    ).fetchone()
    if row is None or "CHECK" not in (row["sql"] or "").upper():
        return

    old = {r["name"] for r in conn.execute("PRAGMA table_info(company)")}
    carried = [c for c in _COMPANY_COLUMNS if c in old]
    columns = ", ".join(carried)
    conn.execute("""
        CREATE TABLE company_migrated (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            payload    TEXT NOT NULL,
            template   BLOB,
            logo       BLOB
        )
    """)
    conn.execute(
        f"INSERT INTO company_migrated ({columns}) SELECT {columns} FROM company"
    )
    conn.execute("DROP TABLE company")
    conn.execute("ALTER TABLE company_migrated RENAME TO company")


def _migrate(conn: sqlite3.Connection):
    """يُرقّي قاعدة بيانات أُنشئت بإصدار أقدم إلى المخطط الحالي."""
    _migrate_company(conn)
    for table, column, decl in _ADDED_COLUMNS:
        existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
    conn.commit()


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def get_conn() -> sqlite3.Connection:
    """اتصال لكل خيط — Streamlit يعيد التشغيل على خيوط مختلفة."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = _local.conn = _connect()
    return conn


@contextmanager
def transaction():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ─── المنافسات ────────────────────────────────────────────────────────────────


def list_projects() -> list:
    rows = get_conn().execute(
        "SELECT id, name, reference, entity, created_at, updated_at, "
        "outcome, outcome_note FROM projects ORDER BY updated_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def set_outcome(project_id: int, outcome: str, note: str = ""):
    """يسجّل نتيجة المنافسة وسببها — مصدر ذاكرة العطاءات الوحيد."""
    with transaction() as conn:
        conn.execute(
            "UPDATE projects SET outcome = ?, outcome_note = ? WHERE id = ?",
            (outcome, note, project_id),
        )


def create_project(name: str, payload: dict, reference: str = "", entity: str = "") -> int:
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO projects (name, reference, entity, created_at, updated_at, payload) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, reference, entity, _now(), _now(),
             json.dumps(payload, ensure_ascii=False)),
        )
        return cur.lastrowid


def load_project(project_id: int) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    if row is None:
        return None
    data = dict(row)
    data["payload"] = json.loads(data["payload"])
    return data


def save_project(project_id: int, payload: dict, name: Optional[str] = None,
                 reference: Optional[str] = None, entity: Optional[str] = None):
    sets = ["updated_at = ?", "payload = ?"]
    args: list[Any] = [_now(), json.dumps(payload, ensure_ascii=False)]
    for column, value in (("name", name), ("reference", reference), ("entity", entity)):
        if value is not None:
            sets.append(f"{column} = ?")
            args.append(value)
    args.append(project_id)
    with transaction() as conn:
        conn.execute(f"UPDATE projects SET {', '.join(sets)} WHERE id = ?", args)


def delete_project(project_id: int):
    with transaction() as conn:
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))


def duplicate_project(project_id: int, new_name: str) -> Optional[int]:
    src = load_project(project_id)
    if src is None:
        return None
    return create_project(new_name, src["payload"], src["reference"], src["entity"])


# ─── ملف الشركة ───────────────────────────────────────────────────────────────


# الشركة الفاعلة: النظام يعرض ملف شركة واحدة في كل لحظة. حتى تصل المستخدمون
# (13-2) يبقى الاختيار على مستوى العملية، وقيمته الافتراضية أقدم شركة مسجَّلة —
# فقاعدة بها شركة واحدة تتصرّف تماماً كما كانت قبل إلغاء القيد.
_active_company_id: Optional[int] = None


def list_companies() -> list:
    rows = get_conn().execute(
        "SELECT id, name, created_at FROM company ORDER BY id"
    ).fetchall()
    return [dict(r) for r in rows]


def active_company_id() -> Optional[int]:
    """الشركة المختارة إن كانت لا تزال موجودة، وإلا أقدم شركة، وإلا `None`."""
    row = get_conn().execute(
        "SELECT id FROM company WHERE id = ?", (_active_company_id,)
    ).fetchone() if _active_company_id is not None else None
    if row is not None:
        return row["id"]
    row = get_conn().execute("SELECT MIN(id) AS id FROM company").fetchone()
    return row["id"] if row and row["id"] is not None else None


def set_active_company(company_id: Optional[int]):
    global _active_company_id
    _active_company_id = company_id


def create_company(name: str = "", payload: Optional[dict] = None) -> int:
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO company (name, created_at, payload) VALUES (?, ?, ?)",
            (name, _now(), json.dumps(payload or {}, ensure_ascii=False)),
        )
        return cur.lastrowid


def rename_company(company_id: int, name: str):
    with transaction() as conn:
        conn.execute("UPDATE company SET name = ? WHERE id = ?", (name, company_id))


def delete_company(company_id: int) -> bool:
    """يحذف شركة. يعيد `False` إن لم تكن موجودة أو كانت الأخيرة الباقية."""
    ids = [r["id"] for r in list_companies()]
    if company_id not in ids or len(ids) <= 1:
        return False
    with transaction() as conn:
        conn.execute("DELETE FROM company WHERE id = ?", (company_id,))
    if _active_company_id == company_id:
        set_active_company(None)
    return True


def _company_row(company_id: Optional[int]):
    target = active_company_id() if company_id is None else company_id
    if target is None:
        return None
    return get_conn().execute(
        "SELECT * FROM company WHERE id = ?", (target,)
    ).fetchone()


def load_company(company_id: Optional[int] = None) -> tuple[dict, Optional[bytes],
                                                            Optional[bytes]]:
    row = _company_row(company_id)
    if row is None:
        return {}, None, None
    return json.loads(row["payload"]), row["template"], row["logo"]


def save_company(payload: dict, template: Optional[bytes] = None,
                 logo: Optional[bytes] = None,
                 company_id: Optional[int] = None) -> int:
    """
    يحفظ ملف الشركة ويعيد معرّفها. القالب والشعار يُحدَّثان فقط عند تمرير قيمة
    صريحة — وإلا فقد المستخدم قالب شركته بمجرد تعديل رقم هاتف.
    """
    existing = _company_row(company_id)
    if existing is None:
        with transaction() as conn:
            cur = conn.execute(
                "INSERT INTO company (id, name, created_at, payload, template, logo) "
                "VALUES (?, '', ?, ?, ?, ?)",
                (company_id, _now(), json.dumps(payload, ensure_ascii=False),
                 template, logo),
            )
            return company_id if company_id is not None else cur.lastrowid

    with transaction() as conn:
        conn.execute(
            "UPDATE company SET payload = ?, template = ?, logo = ? WHERE id = ?",
            (
                json.dumps(payload, ensure_ascii=False),
                existing["template"] if template is None else template,
                existing["logo"] if logo is None else logo,
                existing["id"],
            ),
        )
    return existing["id"]


def clear_company_template(company_id: Optional[int] = None):
    row = _company_row(company_id)
    if row is None:
        return
    with transaction() as conn:
        conn.execute("UPDATE company SET template = NULL WHERE id = ?", (row["id"],))


# ─── مستودع المعرفة ───────────────────────────────────────────────────────────


def add_kb_document(name: str, category: str, char_count: int) -> int:
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO kb_documents (name, category, added_at, char_count) "
            "VALUES (?, ?, ?, ?)",
            (name, category, _now(), char_count),
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
        "GROUP BY d.id ORDER BY d.added_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def all_kb_chunks(categories: Optional[list] = None) -> list:
    sql = (
        "SELECT c.id, c.text, c.dims, c.embedding, c.embed_model, "
        "d.name AS doc_name, d.category "
        "FROM kb_chunks c JOIN kb_documents d ON d.id = c.doc_id"
    )
    args: list[Any] = []
    if categories:
        sql += f" WHERE d.category IN ({','.join('?' * len(categories))})"
        args = list(categories)
    return [dict(r) for r in get_conn().execute(sql, args).fetchall()]


def delete_kb_document(doc_id: int):
    with transaction() as conn:
        conn.execute("DELETE FROM kb_chunks WHERE doc_id = ?", (doc_id,))
        conn.execute("DELETE FROM kb_documents WHERE id = ?", (doc_id,))


def kb_stats() -> dict:
    row = get_conn().execute(
        "SELECT (SELECT COUNT(*) FROM kb_documents) AS docs, "
        "(SELECT COUNT(*) FROM kb_chunks) AS chunks"
    ).fetchone()
    return dict(row)


# ─── نسخ المرفقات ─────────────────────────────────────────────────────────────


def add_attachment_version(project_id: int, texts: dict, roles: dict,
                           label: str = "") -> int:
    """يحفظ لقطة من نصوص المرفقات وأدوارها كما هي وقت الرفع."""
    payload = {"texts": texts or {}, "roles": roles or {}}
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO attachment_versions (project_id, created_at, label, payload) "
            "VALUES (?, ?, ?, ?)",
            (project_id, _now(), label, json.dumps(payload, ensure_ascii=False)),
        )
        return cur.lastrowid


def list_attachment_versions(project_id: int) -> list:
    """بيانات النسخ بلا حمولتها — القائمة تُعرض كثيراً والنصوص ضخمة."""
    rows = get_conn().execute(
        "SELECT id, created_at, label, LENGTH(payload) AS size "
        "FROM attachment_versions WHERE project_id = ? ORDER BY id DESC",
        (project_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def load_attachment_version(version_id: int) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM attachment_versions WHERE id = ?", (version_id,)
    ).fetchone()
    if row is None:
        return None
    data = dict(row)
    data["payload"] = json.loads(data["payload"])
    return data


def previous_attachment_version(project_id: int,
                                before_id: Optional[int] = None) -> Optional[dict]:
    """أحدث نسخة قبل المعرّف المعطى — طرف المقارنة الافتراضي."""
    if before_id is None:
        rows = get_conn().execute(
            "SELECT id FROM attachment_versions WHERE project_id = ? "
            "ORDER BY id DESC LIMIT 1 OFFSET 1",
            (project_id,),
        ).fetchone()
    else:
        rows = get_conn().execute(
            "SELECT id FROM attachment_versions WHERE project_id = ? AND id < ? "
            "ORDER BY id DESC LIMIT 1",
            (project_id, before_id),
        ).fetchone()
    return load_attachment_version(rows["id"]) if rows else None


def delete_attachment_version(version_id: int):
    with transaction() as conn:
        conn.execute("DELETE FROM attachment_versions WHERE id = ?", (version_id,))


# ─── سجلات الأدلة (المرحلة 12) ───────────────────────────────────────────────


def list_records(registry: str) -> list:
    """صفوف السجل بترتيبها المحفوظ."""
    rows = get_conn().execute(
        "SELECT payload FROM company_records WHERE registry = ? "
        "ORDER BY ordinal, id",
        (registry,),
    ).fetchall()
    out = []
    for row in rows:
        try:
            out.append(json.loads(row["payload"]))
        except ValueError:
            continue
    return out


def save_records(registry: str, rows: list):
    """
    يستبدل صفوف السجل بالكامل.

    الاستبدال الكامل يطابق محرر الجداول في الواجهة: المستخدم يحرّر الجدول كله
    ثم يحفظ، فالمزامنة صفاً صفاً تُعقّد بلا مكسب على عشرات الصفوف.
    """
    with transaction() as conn:
        conn.execute("DELETE FROM company_records WHERE registry = ?", (registry,))
        conn.executemany(
            "INSERT INTO company_records (registry, ordinal, payload) VALUES (?, ?, ?)",
            [(registry, i, json.dumps(row, ensure_ascii=False))
             for i, row in enumerate(rows or [])],
        )


def record_counts() -> dict:
    """عدد الصفوف في كل سجل — لمؤشرات الاكتمال."""
    rows = get_conn().execute(
        "SELECT registry, COUNT(*) AS n FROM company_records GROUP BY registry"
    ).fetchall()
    return {r["registry"]: r["n"] for r in rows}


def find_entity(name: str) -> Optional[dict]:
    """
    ملف الجهة بالاسم، بمطابقة مُوحَّدة الإملاء.

    «وزارة الصحة» و«وزاره الصحه» جهة واحدة — نفس التوحيد المستعمل في ذاكرة
    العطاءات، وإلا بقي الملف غير مستدعىً لأن الاسم كُتب بصيغة أخرى.
    """
    from utils.history import normalize_entity

    target = normalize_entity(name)
    if not target:
        return None
    for row in list_records("entities"):
        if normalize_entity(row.get("name", "")) == target:
            return row
    return None


# ─── قياس الاستهلاك (11-7 / 11-8) ────────────────────────────────────────────


def log_ai_usage(project_id, project_name: str, task: str, provider: str,
                 model: str, input_tokens: int, cached_tokens: int,
                 output_tokens: int, cost: float, elapsed_ms: int,
                 status: str, month: str):
    with transaction() as conn:
        conn.execute(
            "INSERT INTO ai_usage (created_at, month, project_id, project_name, "
            "task, provider, model, input_tokens, cached_tokens, output_tokens, "
            "cost, elapsed_ms, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (_now(), month, project_id, project_name, task, provider, model,
             input_tokens, cached_tokens, output_tokens, cost, elapsed_ms, status),
        )


def usage_month_cost(month: str) -> float:
    row = get_conn().execute(
        "SELECT COALESCE(SUM(cost), 0) AS total FROM ai_usage WHERE month = ?",
        (month,),
    ).fetchone()
    return float(row["total"])


_USAGE_GROUPS = {
    "project": "COALESCE(NULLIF(project_name, ''), 'بلا منافسة / no tender')",
    "task": "task",
    "model": "provider || ' / ' || model",
    "provider": "provider",
}


def usage_summary(group_by: str = "project", month: str = "") -> list:
    """إجماليات الاستهلاك مجمّعة — لشاشة الاستهلاك (11-8)."""
    expr = _USAGE_GROUPS.get(group_by, _USAGE_GROUPS["project"])
    sql = (
        f"SELECT {expr} AS grp, COUNT(*) AS calls, "
        "SUM(input_tokens) AS input_tokens, SUM(cached_tokens) AS cached_tokens, "
        "SUM(output_tokens) AS output_tokens, SUM(cost) AS cost "
        "FROM ai_usage"
    )
    args: list[Any] = []
    if month:
        sql += " WHERE month = ?"
        args.append(month)
    sql += " GROUP BY grp ORDER BY cost DESC"
    return [dict(r) for r in get_conn().execute(sql, args).fetchall()]


def usage_totals(month: str = "") -> dict:
    sql = (
        "SELECT COUNT(*) AS calls, COALESCE(SUM(input_tokens), 0) AS input_tokens, "
        "COALESCE(SUM(cached_tokens), 0) AS cached_tokens, "
        "COALESCE(SUM(output_tokens), 0) AS output_tokens, "
        "COALESCE(SUM(cost), 0) AS cost, "
        "SUM(CASE WHEN status = 'cache' THEN 1 ELSE 0 END) AS cache_hits "
        "FROM ai_usage"
    )
    args: list[Any] = []
    if month:
        sql += " WHERE month = ?"
        args.append(month)
    return dict(get_conn().execute(sql, args).fetchone())


# ─── ذاكرة نتائج الاستدعاءات (11-13) ─────────────────────────────────────────


def ai_cache_get(fingerprint: str) -> Optional[str]:
    row = get_conn().execute(
        "SELECT result FROM ai_cache WHERE fingerprint = ?", (fingerprint,)
    ).fetchone()
    return row["result"] if row else None


def ai_cache_put(fingerprint: str, provider: str, model: str, result: str):
    with transaction() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO ai_cache (fingerprint, created_at, provider, "
            "model, result) VALUES (?, ?, ?, ?, ?)",
            (fingerprint, _now(), provider, model, result),
        )


def ai_cache_clear():
    with transaction() as conn:
        conn.execute("DELETE FROM ai_cache")


# ─── إبطال متجهات المستودع عند تغيير نموذج التضمين (11-6) ────────────────────


def kb_stale_chunk_count(embed_model: str) -> int:
    """عدد المقاطع المفهرسة بنموذج تضمين مختلف عن النشط — مُعطَّلة عن البحث."""
    row = get_conn().execute(
        "SELECT COUNT(*) AS n FROM kb_chunks "
        "WHERE COALESCE(embed_model, '') != ?",
        (embed_model,),
    ).fetchone()
    return int(row["n"])


def kb_chunk_texts() -> list:
    """كل المقاطع (المعرّف والنص) — لإعادة الفهرسة بالنموذج النشط."""
    rows = get_conn().execute("SELECT id, text FROM kb_chunks ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def update_kb_chunk_embeddings(rows: list, embed_model: str):
    """rows: [(chunk_id, dims, embedding_bytes)] — بعد إعادة التضمين."""
    with transaction() as conn:
        conn.executemany(
            "UPDATE kb_chunks SET dims = ?, embedding = ?, embed_model = ? "
            "WHERE id = ?",
            [(d, e, embed_model, cid) for cid, d, e in rows],
        )
