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

CREATE TABLE IF NOT EXISTS company (
    id       INTEGER PRIMARY KEY CHECK (id = 1),
    payload  TEXT NOT NULL,
    template BLOB,
    logo     BLOB
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
"""


# أعمدة أُضيفت بعد أول إصدار. CREATE TABLE IF NOT EXISTS لا يُعدّل جدولاً
# قائماً، فقواعد البيانات الموجودة تحتاج إضافتها صراحةً.
_ADDED_COLUMNS = (
    ("projects", "outcome", "TEXT DEFAULT ''"),
    ("projects", "outcome_note", "TEXT DEFAULT ''"),
)


def _migrate(conn: sqlite3.Connection):
    """يضيف الأعمدة الناقصة إلى قاعدة بيانات أُنشئت بإصدار أقدم."""
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


def load_company() -> tuple[dict, Optional[bytes], Optional[bytes]]:
    row = get_conn().execute("SELECT * FROM company WHERE id = 1").fetchone()
    if row is None:
        return {}, None, None
    return json.loads(row["payload"]), row["template"], row["logo"]


def save_company(payload: dict, template: Optional[bytes] = None,
                 logo: Optional[bytes] = None):
    """يحفظ ملف الشركة. القالب والشعار يُحدَّثان فقط عند تمرير قيمة صريحة."""
    existing = get_conn().execute("SELECT * FROM company WHERE id = 1").fetchone()
    if existing is None:
        with transaction() as conn:
            conn.execute(
                "INSERT INTO company (id, payload, template, logo) VALUES (1, ?, ?, ?)",
                (json.dumps(payload, ensure_ascii=False), template, logo),
            )
        return

    with transaction() as conn:
        conn.execute(
            "UPDATE company SET payload = ?, template = ?, logo = ? WHERE id = 1",
            (
                json.dumps(payload, ensure_ascii=False),
                existing["template"] if template is None else template,
                existing["logo"] if logo is None else logo,
            ),
        )


def clear_company_template():
    with transaction() as conn:
        conn.execute("UPDATE company SET template = NULL WHERE id = 1")


# ─── مستودع المعرفة ───────────────────────────────────────────────────────────


def add_kb_document(name: str, category: str, char_count: int) -> int:
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO kb_documents (name, category, added_at, char_count) "
            "VALUES (?, ?, ?, ?)",
            (name, category, _now(), char_count),
        )
        return cur.lastrowid


def add_kb_chunks(doc_id: int, chunks: list):
    """chunks: [(ordinal, text, dims, embedding_bytes)]"""
    with transaction() as conn:
        conn.executemany(
            "INSERT INTO kb_chunks (doc_id, ordinal, text, dims, embedding) "
            "VALUES (?, ?, ?, ?, ?)",
            [(doc_id, o, t, d, e) for o, t, d, e in chunks],
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
        "SELECT c.id, c.text, c.dims, c.embedding, d.name AS doc_name, "
        "d.category FROM kb_chunks c JOIN kb_documents d ON d.id = c.doc_id"
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
