"""
utils/db/reference.py — مراجع وإعدادات: مسرد المصطلحات (14-6) · إعدادات التطبيق
· سياسة البيانات الشخصية (13-10) · تجاوزات الصلاحيات · أوامر البيع (ب-6).
"""

import json
import sqlite3
from typing import Optional

from ._core import _now, get_conn, transaction


# ─── مسرد المصطلحات (14-6) ────────────────────────────────────────────────────


def _glossary_row(row) -> dict:
    """يفكّ قائمة الصيغ المرفوضة. صفٌّ تالف يُقرأ بلا صيغ لا يُسقط المسرد كله."""
    item = dict(row)
    try:
        variants = json.loads(item.get("variants") or "[]")
    except (ValueError, TypeError):
        variants = []
    item["variants"] = [str(v).strip() for v in variants if str(v).strip()]
    return item


def list_glossary() -> list:
    """
    المسرد مرتّباً بالمصطلح.

    الترتيب ثابت لا عشوائي: الكتلة المحقونة في التوليد تُبنى منه، وترتيب متغيّر
    يعني كتلة مختلفة بين عرض وعرض — والغاية من هذا البند عكس ذلك تماماً.
    """
    rows = get_conn().execute(
        "SELECT * FROM glossary ORDER BY term COLLATE NOCASE"
    ).fetchall()
    return [_glossary_row(r) for r in rows]


def glossary_term(term_id: int) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM glossary WHERE id = ?", (int(term_id),)
    ).fetchone()
    return _glossary_row(row) if row is not None else None


def glossary_by_term(term: str) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM glossary WHERE term = ?", ((term or "").strip(),)
    ).fetchone()
    return _glossary_row(row) if row is not None else None


def save_glossary_term(term: str, preferred_ar: str = "", preferred_en: str = "",
                       variants: Optional[list] = None, note: str = "",
                       updated_by: str = "") -> Optional[int]:
    """
    ينشئ مصطلحاً أو يعدّله، ويعيد معرّفه (أو `None` لمصطلح فارغ).

    الصيغة المعتمدة **تُستبعد من الصيغ المرفوضة** ولو كتبها المستخدم فيهما:
    مصطلح يرفض صيغته المعتمدة يجعل كل قسم مخالفاً لنفسه.
    """
    term = (term or "").strip()
    if not term:
        return None

    preferred = {(preferred_ar or "").strip(), (preferred_en or "").strip(), term}
    cleaned = sorted({
        str(v).strip() for v in (variants or [])
        if str(v).strip() and str(v).strip() not in preferred
    })
    payload = json.dumps(cleaned, ensure_ascii=False)
    now = _now()

    existing = glossary_by_term(term)
    with transaction() as conn:
        if existing is None:
            cur = conn.execute(
                "INSERT INTO glossary (term, preferred_ar, preferred_en, variants, "
                "note, created_at, updated_at, updated_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (term, (preferred_ar or "").strip(), (preferred_en or "").strip(),
                 payload, note or "", now, now, updated_by),
            )
            return int(cur.lastrowid)
        conn.execute(
            "UPDATE glossary SET preferred_ar = ?, preferred_en = ?, variants = ?, "
            "note = ?, updated_at = ?, updated_by = ? WHERE id = ?",
            ((preferred_ar or "").strip(), (preferred_en or "").strip(), payload,
             note or "", now, updated_by, int(existing["id"])),
        )
    return int(existing["id"])


def delete_glossary_term(term_id: int) -> bool:
    with transaction() as conn:
        cur = conn.execute("DELETE FROM glossary WHERE id = ?", (int(term_id),))
        return cur.rowcount > 0


def preferred_form(entry: dict, language: str) -> str:
    """
    الصيغة المعتمدة للغة المخرجات، وإلا الأخرى، وإلا المصطلح نفسه.

    السقوط إلى الأخرى مقصود: مسرد نصف مملوء يوحّد ما استطاع بدل أن يصمت.
    """
    order = ("preferred_ar", "preferred_en") if str(language).startswith("ar") \
        else ("preferred_en", "preferred_ar")
    for key in order:
        value = str(entry.get(key) or "").strip()
        if value:
            return value
    return str(entry.get("term") or "").strip()


# ─── سياسة البيانات الشخصية (13-10) ───────────────────────────────────────────
#
# رفع السير الذاتية يُدخل النظام في نطاق نظام حماية البيانات الشخصية: لكل معالجة
# **أساس** معلن، ولكل احتفاظ **مدة**، ولكل شخص **حق الحذف**. الثلاثة هنا.

# أسس المعالجة المعلنة. المفاتيح ثابتة والتسميات في `i18n` تحت `pd.basis_<key>`.
LEGAL_BASES = ("contract", "consent", "legitimate_interest")


DEFAULT_LEGAL_BASIS = "contract"


# مدة الاحتفاظ الافتراضية بالأشهر — تُضبط من الواجهة، و0 تعني بلا حدّ معلن.
DEFAULT_RETENTION_MONTHS = 24


_PD_BASIS_KEY = "pd_legal_basis"


_PD_RETENTION_KEY = "pd_retention_months"


def app_setting(key: str, default: str = "") -> str:
    row = get_conn().execute(
        "SELECT value FROM app_settings WHERE key = ?", (key,)
    ).fetchone()
    return row["value"] if row else default


def set_app_setting(key: str, value: str):
    with transaction() as conn:
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )


def personal_data_policy() -> dict:
    """السياسة المعلنة: أساس المعالجة ومدة الاحتفاظ."""
    basis = app_setting(_PD_BASIS_KEY, DEFAULT_LEGAL_BASIS)
    try:
        months = int(app_setting(_PD_RETENTION_KEY, str(DEFAULT_RETENTION_MONTHS)))
    except ValueError:
        months = DEFAULT_RETENTION_MONTHS
    return {
        "legal_basis": basis if basis in LEGAL_BASES else DEFAULT_LEGAL_BASIS,
        "retention_months": max(0, months),
    }


def set_personal_data_policy(legal_basis: str, retention_months: int) -> bool:
    if legal_basis not in LEGAL_BASES or int(retention_months) < 0:
        return False
    set_app_setting(_PD_BASIS_KEY, legal_basis)
    set_app_setting(_PD_RETENTION_KEY, str(int(retention_months)))
    return True


# ─── تجاوزات مصفوفة الصلاحيات ─────────────────────────────────────────────────
#
# القراءة والكتابة هنا **بلا تفسير**: القاعدة لا تعرف ما الصلاحيات ولا الأدوار،
# ولا تعرف الافتراض. `utils/auth.py` وحده يجمع بين الافتراض والتجاوز.


def permission_override(permission: str, role: str) -> Optional[bool]:
    """التجاوز المخزَّن لهذا الزوج، أو `None` إن لم يُغيَّر فيُتبع الافتراض."""
    row = get_conn().execute(
        "SELECT allowed FROM role_permissions WHERE permission = ? AND role = ?",
        (permission, role),
    ).fetchone()
    return None if row is None else bool(row["allowed"])


def permission_overrides() -> dict:
    """كل التجاوزات: `{(صلاحية، دور): مسموح}` — للعرض في شاشة الإعدادات."""
    rows = get_conn().execute(
        "SELECT permission, role, allowed FROM role_permissions"
    ).fetchall()
    return {(r["permission"], r["role"]): bool(r["allowed"]) for r in rows}


def set_permission_override(permission: str, role: str, allowed: bool):
    with transaction() as conn:
        conn.execute(
            "INSERT INTO role_permissions (permission, role, allowed) "
            "VALUES (?, ?, ?) ON CONFLICT(permission, role) "
            "DO UPDATE SET allowed = excluded.allowed",
            (permission, role, 1 if allowed else 0),
        )


def clear_permission_override(permission: str, role: str):
    """يحذف التجاوز فيعود الزوج إلى افتراض الشيفرة."""
    with transaction() as conn:
        conn.execute(
            "DELETE FROM role_permissions WHERE permission = ? AND role = ?",
            (permission, role),
        )


def clear_all_permission_overrides():
    with transaction() as conn:
        conn.execute("DELETE FROM role_permissions")


# ─── أوامر البيع المدفوعة (ب-6) ────────────────────────────────────────────────


def connector_order(project_id: int, connector: str) -> Optional[dict]:
    row = get_conn().execute(
        "SELECT * FROM connector_orders WHERE project_id = ? AND connector = ?",
        (int(project_id), connector),
    ).fetchone()
    return dict(row) if row is not None else None


def record_connector_order(project_id: int, connector: str, reference: str,
                           remote_id: str, fingerprint: str,
                           pushed_by: str = "") -> bool:
    """
    يسجّل أمراً دُفع. يعيد `False` إن كان لهذه المنافسة أمرٌ في هذا النظام.

    `INSERT` بلا `ON CONFLICT`: التكرار **يفشل** ولا يُحدَّث. أمرٌ ثانٍ في
    دفاتر العميل ليس تحديثاً للأول، وكتابته فوق سجلّه تُخفي الأول ولا تلغيه.
    """
    try:
        with transaction() as conn:
            conn.execute(
                "INSERT INTO connector_orders (project_id, connector, reference, "
                "remote_id, fingerprint, pushed_at, pushed_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (int(project_id), connector, reference, str(remote_id),
                 fingerprint, _now(), pushed_by),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def set_connector_order_remote(project_id: int, connector: str, remote_id: str):
    """
    يملأ معرّف الأمر البعيد بعد نجاح الإرسال.

    السجلّ يُحجز **قبل** الإرسال بمعرّف فارغ فلا تمرّ ضغطتان بأمرين، ويُملأ
    بعده. والحجز ثم التحديث أسلم من الحذف ثم الإدراج: بينهما نافذةٌ تمرّ منها
    ضغطة ثانية.
    """
    with transaction() as conn:
        conn.execute(
            "UPDATE connector_orders SET remote_id = ? "
            "WHERE project_id = ? AND connector = ?",
            (str(remote_id), int(project_id), connector),
        )


def forget_connector_order(project_id: int, connector: str):
    """
    يمحو سجلّ الدفع عندنا — **ولا يمسّ نظام العميل**.

    يُستعمل حين يُحذف الأمر هناك يدوياً فيصير سجلّنا كاذباً يمنع دفعاً مشروعاً.
    والفصل مقصود: لا نحذف من دفاتر أحد، ولا ندّعي أننا فعلنا.
    """
    with transaction() as conn:
        conn.execute(
            "DELETE FROM connector_orders WHERE project_id = ? AND connector = ?",
            (int(project_id), connector),
        )
