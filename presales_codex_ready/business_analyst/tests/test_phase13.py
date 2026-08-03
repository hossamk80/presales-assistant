"""
tests/test_phase13.py — المرحلة 13: الاستخدام الجماعي.

13-1: جدول الشركة كان مقيَّداً بصف واحد `CHECK (id = 1)`. الاختبارات هنا
تحرس أمرين: أن القاعدة صارت تحتمل أكثر من شركة، وأن قاعدة أُنشئت بالمخطط
القديم تُرقّى بلا فقد بيانات — لا الحمولة ولا القالب ولا الشعار.
"""
import json
import sqlite3


LEGACY_SCHEMA = """
CREATE TABLE company (
    id       INTEGER PRIMARY KEY CHECK (id = 1),
    payload  TEXT NOT NULL,
    template BLOB,
    logo     BLOB
);
"""


def _write_legacy_db(path, payload, template=None, logo=None):
    """يبني ملف قاعدة بالمخطط القديم قبل أن يفتحه `db` لأول مرة."""
    conn = sqlite3.connect(path)
    conn.executescript(LEGACY_SCHEMA)
    conn.execute(
        "INSERT INTO company (id, payload, template, logo) VALUES (1, ?, ?, ?)",
        (json.dumps(payload, ensure_ascii=False), template, logo),
    )
    conn.commit()
    conn.close()


# ─── 13-1: إلغاء قيد الشركة الأحادية ─────────────────────────────────────────


def test_more_than_one_company_can_be_stored(temp_db):
    db = temp_db
    first = db.create_company("الشركة الأمّ", {"c_name": "الأمّ"})
    second = db.create_company("الذراع التنفيذية", {"c_name": "الذراع"})

    assert first != second
    assert [c["name"] for c in db.list_companies()] == [
        "الشركة الأمّ", "الذراع التنفيذية"]
    assert db.load_company(second)[0]["c_name"] == "الذراع"


def test_company_table_has_no_single_row_constraint(temp_db):
    db = temp_db
    db.save_company({"c_name": "شركة"})
    sql = db.get_conn().execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'company'"
    ).fetchone()["sql"]
    assert "CHECK" not in sql.upper()


def test_legacy_database_upgrades_without_data_loss(temp_db):
    """قاعدة بالمخطط القديم: الصف يبقى، والقيد يزول، وتُقبل شركة ثانية."""
    db = temp_db
    _write_legacy_db(db.DB_PATH, {"c_name": "شركة قديمة", "c_phone": "123"},
                     template=b"DOCX-BYTES", logo=b"PNG-BYTES")

    payload, template, logo = db.load_company()
    assert payload == {"c_name": "شركة قديمة", "c_phone": "123"}
    assert template == b"DOCX-BYTES"
    assert logo == b"PNG-BYTES"

    assert [c["id"] for c in db.list_companies()] == [1]
    new_id = db.create_company("شركة ثانية")
    assert new_id != 1
    assert len(db.list_companies()) == 2


def test_legacy_migration_runs_once_and_keeps_added_rows(temp_db):
    """إعادة فتح القاعدة بعد الترحيل لا تُعيد بناء الجدول ولا تمحو ما أُضيف."""
    db = temp_db
    _write_legacy_db(db.DB_PATH, {"c_name": "شركة قديمة"})
    db.create_company("شركة ثانية")

    db._local.__dict__.pop("conn", None)          # اتصال جديد ⇐ ترحيل جديد
    assert [c["id"] for c in db.list_companies()] == [1, 2]
    assert db.load_company(1)[0] == {"c_name": "شركة قديمة"}


# ─── الشركة الفاعلة ──────────────────────────────────────────────────────────


def test_active_company_defaults_to_oldest(temp_db):
    db = temp_db
    first = db.create_company("أ", {"c_name": "أ"})
    db.create_company("ب", {"c_name": "ب"})
    assert db.active_company_id() == first
    assert db.load_company()[0]["c_name"] == "أ"


def test_active_company_switches_reads_and_writes(temp_db):
    db = temp_db
    first = db.create_company("أ", {"c_name": "أ"})
    second = db.create_company("ب", {"c_name": "ب"})

    db.set_active_company(second)
    assert db.load_company()[0]["c_name"] == "ب"

    db.save_company({"c_name": "ب محدَّثة"}, template=b"T")
    assert db.load_company()[0]["c_name"] == "ب محدَّثة"
    assert db.load_company(first)[0]["c_name"] == "أ"   # الأولى لم تُمَسّ
    assert db.load_company(first)[1] is None


def test_active_company_falls_back_when_selection_deleted(temp_db):
    db = temp_db
    first = db.create_company("أ")
    second = db.create_company("ب")
    db.set_active_company(second)

    assert db.delete_company(second) is True
    assert db.active_company_id() == first


def test_last_company_cannot_be_deleted(temp_db):
    """حذف الشركة الأخيرة يمحو ملف الشركة كاملاً — يُرفض."""
    db = temp_db
    only = db.create_company("أ")
    assert db.delete_company(only) is False
    assert db.delete_company(9999) is False
    assert len(db.list_companies()) == 1


def test_rename_company(temp_db):
    db = temp_db
    cid = db.create_company("اسم قديم")
    db.rename_company(cid, "اسم جديد")
    assert db.list_companies()[0]["name"] == "اسم جديد"


def test_save_company_creates_first_company_implicitly(temp_db):
    """السلوك القديم محفوظ: أول حفظ بلا شركة قائمة يُنشئ واحدة."""
    db = temp_db
    assert db.list_companies() == []
    cid = db.save_company({"c_name": "شركة"})
    assert db.active_company_id() == cid
    assert db.load_company()[0] == {"c_name": "شركة"}
