"""
utils/db/snapshots.py — النسخ الاحتياطي والاسترجاع (13-9): الملف كاملاً بايتاتٍ موثَّقة.
"""

import os
import sqlite3

from . import _core
from ._core import _local, _bump_generation, get_conn


# ─── النسخ الاحتياطي والاسترجاع (13-9) ────────────────────────────────────────

# ترويسة ملف SQLite — أول ما يُفحص في أي ملف يُقدَّم للاسترجاع.
SQLITE_MAGIC = b"SQLite format 3\x00"


# جداول لا تكون النسخة نسخةً بدونها. الفحص قبل الاستبدال لا بعده.
REQUIRED_TABLES = ("projects", "company", "kb_documents", "kb_chunks", "users")


def snapshot_bytes() -> bytes:
    """
    نسخة متّسقة من القاعدة كاملةً (المنافسات · الشركة · المعرفة · المستخدمون).

    عبر `sqlite3.Connection.backup` لا بنسخ الملف نسخاً خاماً: الاتصال مفتوح
    وقد تكون هناك كتابة جارية، فنسخ الملف حينها يُنتج نسخة ممزّقة تُستعاد
    بأخطاء لا تظهر إلا بعد فوات الأوان.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as folder:
        target = os.path.join(folder, "snapshot.db")
        destination = sqlite3.connect(target)
        try:
            get_conn().backup(destination)
        finally:
            destination.close()
        with open(target, "rb") as handle:
            return handle.read()


def validate_snapshot(data: bytes) -> bool:
    """هل هذه بايتات قاعدة صالحة تحمل جداول النظام؟"""
    import tempfile

    if not data or not data.startswith(SQLITE_MAGIC):
        return False
    with tempfile.TemporaryDirectory() as folder:
        probe = os.path.join(folder, "probe.db")
        with open(probe, "wb") as handle:
            handle.write(data)
        try:
            conn = sqlite3.connect(probe)
            names = {
                row[0] for row in
                conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
            conn.close()
        except sqlite3.DatabaseError:
            return False
    return all(table in names for table in REQUIRED_TABLES)


def restore_bytes(data: bytes) -> bool:
    """
    يستبدل القاعدة بنسخة احتياطية. يعيد `False` إن كانت النسخة غير صالحة.

    الفحص **قبل** الاستبدال، والاستبدال بـ `os.replace` (ذرّي على المنصة
    الواحدة) — فملف نصفه قديم ونصفه جديد أسوأ من استرجاع فاشل.

    المسار يُقرأ `_core.DB_PATH` لا اسماً مستورَداً: الاختبارات تبدّله وقت
    التشغيل، والاستيراد بالقيمة ينسخ الارتباط مرّةً واحدة فيكتب الاسترجاع
    فوق قاعدة المطوّر الحقيقية بدل القاعدة المؤقّتة.
    """
    if not validate_snapshot(data):
        return False

    os.makedirs(os.path.dirname(_core.DB_PATH) or ".", exist_ok=True)
    staging = f"{_core.DB_PATH}.restoring"
    with open(staging, "wb") as handle:
        handle.write(data)

    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except sqlite3.Error:
            pass
        _local.__dict__.pop("conn", None)

    os.replace(staging, _core.DB_PATH)
    _bump_generation()       # كل خيط آخر يُسقط اتصاله عند أول استعمال
    return True
