"""اختبارات طبقة التخزين الدائم."""
import struct


def test_project_crud(temp_db):
    db = temp_db
    pid = db.create_project("منافسة أ", {"rfp_raw_text": "نص"}, "REF-1", "جهة أ")

    rows = db.list_projects()
    assert [r["name"] for r in rows] == ["منافسة أ"]
    assert rows[0]["reference"] == "REF-1"
    assert rows[0]["entity"] == "جهة أ"

    loaded = db.load_project(pid)
    assert loaded["payload"] == {"rfp_raw_text": "نص"}

    db.save_project(pid, {"rfp_raw_text": "محدَّث", "extra": [1, 2]}, name="منافسة ب")
    loaded = db.load_project(pid)
    assert loaded["name"] == "منافسة ب"
    assert loaded["payload"]["extra"] == [1, 2]

    db.delete_project(pid)
    assert db.list_projects() == []
    assert db.load_project(pid) is None


def test_duplicate_project_copies_payload(temp_db):
    db = temp_db
    pid = db.create_project("أصل", {"k": "v"}, "R", "E")
    new_id = db.duplicate_project(pid, "نسخة")
    assert new_id != pid
    assert db.load_project(new_id)["payload"] == {"k": "v"}
    assert db.load_project(new_id)["reference"] == "R"


def test_duplicate_missing_project_returns_none(temp_db):
    assert temp_db.duplicate_project(9999, "x") is None


def test_company_template_survives_profile_update(temp_db):
    """
    حفظ الملف بدون تمرير قالب يجب ألا يمسح القالب المخزَّن — وإلا فقد
    المستخدم قالب شركته بمجرد تعديل رقم هاتف.
    """
    db = temp_db
    db.save_company({"c_name": "شركة"}, template=b"DOCX-BYTES")
    db.save_company({"c_name": "شركة", "c_phone": "123"})

    payload, template, _logo = db.load_company()
    assert payload["c_phone"] == "123"
    assert template == b"DOCX-BYTES"

    db.clear_company_template()
    assert db.load_company()[1] is None


def test_company_empty_when_never_saved(temp_db):
    assert temp_db.load_company() == ({}, None, None)


def test_kb_documents_and_chunks(temp_db):
    db = temp_db
    doc_id = db.add_kb_document("cv.pdf", "cv", 1200)
    db.add_kb_chunks(doc_id, [
        (0, "مقطع أول", 4, struct.pack("4f", 1, 0, 0, 0)),
        (1, "مقطع ثانٍ", 4, struct.pack("4f", 0, 1, 0, 0)),
    ])

    assert db.kb_stats() == {"docs": 1, "chunks": 2}
    docs = db.list_kb_documents()
    assert docs[0]["name"] == "cv.pdf" and docs[0]["chunks"] == 2

    chunks = db.all_kb_chunks()
    assert {c["text"] for c in chunks} == {"مقطع أول", "مقطع ثانٍ"}
    assert chunks[0]["doc_name"] == "cv.pdf"

    assert db.all_kb_chunks(categories=["cert"]) == []
    assert len(db.all_kb_chunks(categories=["cv"])) == 2


def test_deleting_document_removes_its_chunks(temp_db):
    db = temp_db
    doc_id = db.add_kb_document("x.pdf", "cert", 10)
    db.add_kb_chunks(doc_id, [(0, "t", 2, struct.pack("2f", 1, 0))])
    db.delete_kb_document(doc_id)
    assert db.kb_stats() == {"docs": 0, "chunks": 0}


def test_projects_ordered_by_recent_update(temp_db):
    db = temp_db
    a = db.create_project("أ", {}, "", "")
    db.create_project("ب", {}, "", "")
    db.save_project(a, {"touched": True})
    assert db.list_projects()[0]["name"] == "أ"
