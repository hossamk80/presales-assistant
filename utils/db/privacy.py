"""
utils/db/privacy.py — حقّ المحو ونسخ المرفقات: أثر الشخص في كل كيان، ومحوه منها جميعاً.

**الوحدة الوحيدة التي تتجاوز تقييد الشركة عمداً** — وتُعلنه بـ `ANY_COMPANY`:
حذفٌ مقيَّد يجعل «حُذفت بياناتك» جملةً غير صحيحة.
"""

import json
from datetime import datetime, timedelta
from typing import Optional

from ._core import (
    ANY_COMPANY,
    UNSCOPED_COMPANY,
    _now,
    _scope,
    get_conn,
    list_companies,
    transaction,
)
from .knowledge import delete_kb_document
from .records import _replace_records, list_records
from .reference import personal_data_policy


def expired_cv_documents(months: Optional[int] = None) -> list:
    """
    السير التي تجاوزت مدة الاحتفاظ المعلنة. مدة صفر تعني بلا حدّ فلا يُعدّ شيء
    منتهياً — إعلان «نحتفظ بلا حدّ» أصدق من حذف صامت.
    """
    if months is None:
        months = personal_data_policy()["retention_months"]
    if not months:
        return []

    cutoff = datetime.now() - timedelta(days=30 * int(months))
    limit = cutoff.strftime("%Y-%m-%d %H:%M:%S")
    rows = get_conn().execute(
        "SELECT d.*, COUNT(c.id) AS chunks FROM kb_documents d "
        "LEFT JOIN kb_chunks c ON c.doc_id = d.id "
        "WHERE d.category = 'cv' AND d.added_at < ? AND d.company_id = ? "
        "GROUP BY d.id ORDER BY d.added_at",
        (limit, _scope()),
    ).fetchall()
    return [dict(r) for r in rows]


def person_footprint(name: str) -> dict:
    """
    ما يخصّ هذا الشخص في النظام — يُعرض قبل الحذف لا بعده.

    **يُحصى على التثبيت كلّه** لا على الشركة الفاعلة، لأن `forget_person` يحذف
    كذلك: عددٌ يقول «صفّ واحد» ثم يُحذف صفّان يجعل ما عُرض قبل فعلٍ لا رجعة
    فيه كاذباً — وهو أسوأ من ألّا يُعرض.
    """
    name = (name or "").strip()
    if not name:
        return {"records": 0, "documents": 0, "chunks": 0}

    records = [r for r in list_records("people", company_id=ANY_COMPANY)
               if str(r.get("name", "")).strip() == name]
    docs = _person_documents(name)
    return {
        "records": len(records),
        "documents": len(docs),
        "chunks": sum(d["chunks"] for d in docs),
    }


def _person_documents(name: str) -> list:
    """
    مستندات الشخص: ما رُبط به صراحةً، وما سمّاه صفّه في سجل الكوادر.

    الاثنان معاً لأن الربط الصريح أُضيف في 13-10: سيرة رُفعت قبله لا تحمل ربطاً،
    وحقّ الشخص في حذفها لا ينتظر ترقية.
    """
    # ب-8 — **استثناء مقصود من التقييد بالشركة**: حقّ الشخص في حذف بياناته
    # (13-10) لا يقف عند حدود كيانٍ اختاره مستخدم في جلسته. سيرةٌ تبقى في
    # مستودع كيان آخر بعد «حُذفت بياناتك» تجعل الإقرار كاذباً — والبحث هنا
    # على التثبيت كلّه عمداً، وكذلك `list_records` أدناه.
    linked_names = {
        str(r.get("cv_document", "")).strip()
        for r in list_records("people", company_id=ANY_COMPANY)
        if str(r.get("name", "")).strip() == name and str(r.get("cv_document", "")).strip()
    }
    rows = get_conn().execute(
        "SELECT d.*, COUNT(c.id) AS chunks FROM kb_documents d "
        "LEFT JOIN kb_chunks c ON c.doc_id = d.id "
        "GROUP BY d.id"
    ).fetchall()
    return [
        dict(r) for r in rows
        if (r["person"] or "").strip() == name or r["name"] in linked_names
    ]


def forget_person(name: str) -> dict:
    """
    حقّ الحذف عند الطلب: يمحو صفّ الشخص في سجل الكوادر وسيرته ومقاطعها.

    المقاطع أخطر ما في الباب: نصّ السيرة يعيش فيها مُقطَّعاً، فحذف المستند
    وحده يترك بيانات الشخص في المستودع تُسترجَع في كل توليد.
    """
    name = (name or "").strip()
    if not name:
        return {"records": 0, "documents": 0, "chunks": 0}

    removed = {"records": 0, "documents": 0, "chunks": 0}

    documents = _person_documents(name)
    for doc in documents:
        # ANY_COMPANY: الحذف يشمل التثبيت كلّه — انظر `_person_documents`
        delete_kb_document(doc["id"], company_id=ANY_COMPANY)
        removed["documents"] += 1
        removed["chunks"] += doc["chunks"]

    # سجلّ الكوادر يُنقّى **في كل شركة**: صفٌّ باسمه في كيانٍ آخر يبقى بعد
    # الحذف فيصير الإقرار كاذباً — والمرور على الشركات هنا مقصود لا سهو.
    for company in list_companies() or [{"id": UNSCOPED_COMPANY}]:
        people = list_records("people", company_id=company["id"])
        kept = [r for r in people if str(r.get("name", "")).strip() != name]
        if len(kept) != len(people):
            removed["records"] += len(people) - len(kept)
            _replace_records("people", kept, company["id"])

    return removed


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
