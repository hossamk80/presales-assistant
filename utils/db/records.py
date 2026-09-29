"""
utils/db/records.py — سجلات الأدلة (المرحلة 12): الشهادات والخبرات والكوادر ومرجعها.
"""

import json
from typing import Any, Optional

from ._core import ANY_COMPANY, _scope, get_conn, transaction


# ─── سجلات الأدلة (المرحلة 12) ───────────────────────────────────────────────


def list_records(registry: str, company_id: Optional[int] = None) -> list:
    """
    صفوف السجل بترتيبها المحفوظ — لشركة واحدة (ب-8).

    `company_id=ANY_COMPANY` يتجاوز التقييد، ولا يُمرَّر إلا حيث يكون التجاوز
    هو الصواب: حذف بيانات شخص عبر التثبيت كلّه (13-10).
    """
    scope = _scope(company_id)
    sql = ("SELECT payload FROM company_records WHERE registry = ? "
           "ORDER BY ordinal, id")
    args: list[Any] = [registry]
    if scope != ANY_COMPANY:
        sql = ("SELECT payload FROM company_records "
               "WHERE registry = ? AND company_id = ? ORDER BY ordinal, id")
        args.append(scope)
    rows = get_conn().execute(sql, args).fetchall()
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
    scope = _scope()
    with transaction() as conn:
        # الحذف مقيَّد كالإدراج: استبدالٌ غير مقيَّد يمحو سجلّ كيانٍ آخر
        # بالكامل لأن مستخدماً حرّر جدوله هو.
        conn.execute(
            "DELETE FROM company_records WHERE registry = ? AND company_id = ?",
            (registry, scope),
        )
        conn.executemany(
            "INSERT INTO company_records (registry, ordinal, payload, company_id) "
            "VALUES (?, ?, ?, ?)",
            [(registry, i, json.dumps(row, ensure_ascii=False), scope)
             for i, row in enumerate(rows or [])],
        )


def _replace_records(registry: str, rows: list, company_id: int):
    """استبدال صفوف سجلّ شركة بعينها — مسار داخلي للحذف عبر الشركات."""
    with transaction() as conn:
        conn.execute(
            "DELETE FROM company_records WHERE registry = ? AND company_id = ?",
            (registry, company_id),
        )
        conn.executemany(
            "INSERT INTO company_records (registry, ordinal, payload, company_id) "
            "VALUES (?, ?, ?, ?)",
            [(registry, i, json.dumps(row, ensure_ascii=False), company_id)
             for i, row in enumerate(rows or [])],
        )


def record_counts() -> dict:
    """عدد الصفوف في كل سجل — لمؤشرات الاكتمال."""
    rows = get_conn().execute(
        "SELECT registry, COUNT(*) AS n FROM company_records "
        "WHERE company_id = ? GROUP BY registry",
        (_scope(),),
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
