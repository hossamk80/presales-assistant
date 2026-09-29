"""
utils/db/accounts.py — المستخدمون (13-2) والشركات: الحسابات وأدوارها، وملف كل كيان.
"""

import json
import sqlite3
from typing import Optional

from ._core import (
    COMPANY_SCOPED_TABLES,
    _active_company_id,
    _backfill_company_scope,
    _now,
    active_company_id,
    get_conn,
    list_companies,
    set_active_company,
    transaction,
)


# ─── المستخدمون (13-2) ────────────────────────────────────────────────────────
# هذه الطبقة تخزّن وتقرأ فقط. التجزئة والتحقق ومنطق الجلسة في `utils/auth.py`.


def count_users(active_only: bool = False) -> int:
    sql = "SELECT COUNT(*) AS n FROM users"
    if active_only:
        sql += " WHERE active = 1"
    return get_conn().execute(sql).fetchone()["n"]


def list_users() -> list:
    rows = get_conn().execute(
        # `company_id` لازم هنا لا في `SELECT *` وحده: حذف شركة يمرّ على كل
        # حساب اختارها لينساها، ولا يعرف من اختارها إن لم يُقرأ العمود
        "SELECT id, username, display_name, role, active, created_at, "
        "last_login, company_id FROM users ORDER BY username"
    ).fetchall()
    return [dict(r) for r in rows]


def get_user(username: str) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM users WHERE username = ?", (username.strip(),)
    ).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    return dict(row) if row else None


def create_user(username: str, password_hash: str, display_name: str = "",
                role: str = "admin", active: bool = True) -> Optional[int]:
    """يعيد معرّف المستخدم، أو `None` إن كان الاسم مستعملاً."""
    try:
        with transaction() as conn:
            cur = conn.execute(
                "INSERT INTO users (username, display_name, password_hash, role, "
                "active, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (username.strip(), display_name.strip(), password_hash, role,
                 1 if active else 0, _now()),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def set_user_password(user_id: int, password_hash: str):
    with transaction() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id)
        )


def set_user_role(user_id: int, role: str):
    with transaction() as conn:
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))


def set_user_active(user_id: int, active: bool):
    with transaction() as conn:
        conn.execute(
            "UPDATE users SET active = ? WHERE id = ?", (1 if active else 0, user_id)
        )


def update_user_profile(user_id: int, display_name: str):
    with transaction() as conn:
        conn.execute(
            "UPDATE users SET display_name = ? WHERE id = ?",
            (display_name.strip(), user_id),
        )


def touch_user_login(user_id: int):
    with transaction() as conn:
        conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (_now(), user_id))


def delete_user(user_id: int):
    with transaction() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def set_user_company(user_id: int, company_id: Optional[int]):
    """يحفظ اختيار المستخدم فيجده كما تركه في دخوله التالي."""
    with transaction() as conn:
        conn.execute("UPDATE users SET company_id = ? WHERE id = ?",
                     (company_id, user_id))


def create_company(name: str = "", payload: Optional[dict] = None) -> int:
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO company (name, created_at, payload) VALUES (?, ?, ?)",
            (name, _now(), json.dumps(payload or {}, ensure_ascii=False)),
        )
        created = cur.lastrowid
        # التبنّي إلى **أقدم** شركة لا إلى هذه: صفوفٌ سبقت التقييد تخصّ من كان
        # يعمل قبلها، لا كياناً أُنشئ الآن.
        _backfill_company_scope(conn)
        return created


def rename_company(company_id: int, name: str):
    with transaction() as conn:
        conn.execute("UPDATE company SET name = ? WHERE id = ?", (name, company_id))


def company_holdings(company_id: int) -> dict:
    """
    ما تملكه الشركة: منافسات · مستندات معرفة · صفوف سجلات (ب-8).

    يُعرض قبل الحذف: ملف شركة يُحذف وحده خسارةُ نموذج، ومعه منافساتٌ ومستودعُ
    معرفةٍ خسارةُ شهور. والرقم يُقال قبل الضغط لا بعده.
    """
    counts = {}
    for table in COMPANY_SCOPED_TABLES:
        row = get_conn().execute(
            f"SELECT COUNT(*) AS n FROM {table} WHERE company_id = ?",
            (int(company_id),),
        ).fetchone()
        counts[table] = int(row["n"]) if row else 0
    return counts


def delete_company(company_id: int) -> bool:
    """
    يحذف شركة. يعيد `False` إن لم تكن موجودة أو كانت الأخيرة الباقية.

    **ولا يحذف شركةً تملك بيانات** (ب-8): حذفٌ يجرّ معه منافسات ومستودع معرفة
    خسارةٌ لا رجعة فيها من ضغطةٍ قصدها «تنظيف قائمة». من أرادها يُفرغها أولاً
    وهو يرى ما يحذف.
    """
    ids = [r["id"] for r in list_companies()]
    if company_id not in ids or len(ids) <= 1:
        return False
    if any(company_holdings(company_id).values()):
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
            created = company_id if company_id is not None else cur.lastrowid
            # ب-8: أول شركة تتبنّى ما أُنشئ قبلها. المستخدم يفتح النظام فينشئ
            # منافسة قبل أن يملأ ملف شركته — ولولا التبنّي اختفت لحظة ملئه.
            _backfill_company_scope(conn)
            return created

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
