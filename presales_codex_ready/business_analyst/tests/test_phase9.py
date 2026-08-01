"""
اختبارات المرحلة 9 — ذاكرة العطاءات: نتائج المنافسات والسوابق المشابهة.
"""
import pytest


@pytest.fixture()
def hist():
    from utils import history
    return history


def _p(pid, name, entity="", outcome="", note=""):
    return {"id": pid, "name": name, "entity": entity,
            "outcome": outcome, "outcome_note": note}


# ─── التخزين ───────────────────────────────────────────────────────────────────


def test_outcome_is_saved_and_listed(temp_db):
    pid = temp_db.create_project("تشغيل وصيانة أجهزة", {}, entity="وزارة الصحة")
    temp_db.set_outcome(pid, "خسر", "نسبة المحتوى المحلي")

    project = next(p for p in temp_db.list_projects() if p["id"] == pid)
    assert project["outcome"] == "خسر"
    assert project["outcome_note"] == "نسبة المحتوى المحلي"


def test_new_project_starts_without_an_outcome(temp_db):
    """غياب النتيجة ليس نتيجة — لا يُفترض "قيد التقييم"."""
    pid = temp_db.create_project("منافسة جديدة", {})
    project = next(p for p in temp_db.list_projects() if p["id"] == pid)
    assert (project["outcome"] or "") == ""


def test_database_created_before_this_feature_is_migrated(tmp_path, monkeypatch):
    """
    CREATE TABLE IF NOT EXISTS لا يُعدّل جدولاً قائماً؛ قاعدة قديمة بلا
    العمودين كانت ستنهار عند أول قراءة.
    """
    import sqlite3
    import sys

    path = tmp_path / "old.db"
    old = sqlite3.connect(str(path))
    old.executescript("""
        CREATE TABLE projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, reference TEXT DEFAULT '', entity TEXT DEFAULT '',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload TEXT NOT NULL
        );
    """)
    old.execute(
        "INSERT INTO projects (name, created_at, updated_at, payload) "
        "VALUES ('منافسة قديمة', '2026-01-01', '2026-01-01', '{}')"
    )
    old.commit()
    old.close()

    monkeypatch.setenv("ANALYST_DB_PATH", str(path))
    for name in [m for m in list(sys.modules) if m.startswith("utils")]:
        monkeypatch.delitem(sys.modules, name, raising=False)
    from utils import db as fresh
    monkeypatch.setattr(fresh, "DB_PATH", str(path))
    fresh._local.__dict__.pop("conn", None)

    projects = fresh.list_projects()
    assert projects[0]["name"] == "منافسة قديمة"
    assert projects[0]["outcome"] == ""
    fresh._local.__dict__.pop("conn", None)


# ─── التشابه ───────────────────────────────────────────────────────────────────


def test_same_entity_is_matched_even_with_a_different_title(hist):
    """سلوك الجهة في التقييم يتكرّر — الجهة أقوى إشارة من تشابه العنوان."""
    projects = [_p(1, "تأثيث مبانٍ إدارية", "وزارة الصحة", "خسر")]
    out = hist.similar_projects(projects, "توريد أجهزة مختبرات", "وزارة الصحة")
    assert len(out) == 1 and out[0]["same_entity"]


@pytest.mark.parametrize("stored,queried", [
    ("وزارة الصحة", "وزاره الصحة "),
    ("وزارة الصحة", "وزارة الصحه"),
    ("الهيئة العامة للإحصاء", "الهيئه العامه للاحصاء"),
])
def test_entity_spelling_variants_are_one_entity(hist, stored, queried):
    """بدون التوحيد تُعدّ الجهة الواحدة جهتين فتضيع أهم إشارة."""
    out = hist.similar_projects([_p(1, "أي مشروع", stored, "فاز")], "آخر", queried)
    assert len(out) == 1


def test_title_overlap_matches_without_the_entity(hist):
    projects = [_p(1, "توريد وتركيب أجهزة أشعة رقمية", "جامعة الملك سعود", "فاز")]
    out = hist.similar_projects(projects, "توريد أجهزة أشعة رقمية للمستشفى", "")
    assert len(out) == 1
    assert "أشعة" in out[0]["shared_terms"]


def test_generic_words_alone_do_not_make_a_match(hist):
    """"توريد" و"مشروع" في كل منافسة — تطابقها يُنتج تشابهاً وهمياً."""
    projects = [_p(1, "مشروع توريد أثاث مكتبي", "جهة أخرى")]
    assert hist.similar_projects(projects, "مشروع توريد برمجيات", "") == []


def test_the_open_tender_is_not_its_own_precedent(hist):
    projects = [_p(7, "توريد أجهزة أشعة", "وزارة الصحة", "فاز")]
    assert hist.similar_projects(projects, "توريد أجهزة أشعة", "وزارة الصحة",
                                 exclude_id=7) == []


def test_same_entity_outranks_title_overlap(hist):
    projects = [
        _p(1, "توريد أجهزة أشعة رقمية متطورة", "جهة أخرى"),
        _p(2, "تأثيث مكاتب", "وزارة الصحة"),
    ]
    out = hist.similar_projects(projects, "توريد أجهزة أشعة رقمية", "وزارة الصحة")
    assert out[0]["id"] == 2


def test_similar_results_are_capped(hist):
    projects = [_p(i, "توريد أجهزة أشعة رقمية", "وزارة الصحة") for i in range(20)]
    assert len(hist.similar_projects(projects, "توريد أجهزة أشعة", "وزارة الصحة",
                                     limit=3)) == 3


def test_similar_is_safe_on_empty_input(hist):
    assert hist.similar_projects([], "منافسة", "جهة") == []
    assert hist.similar_projects(None, "منافسة", "جهة") == []


# ─── الإحصاء والدروس ───────────────────────────────────────────────────────────


def test_outcome_stats_counts_each_state(hist):
    projects = [
        _p(1, "أ", outcome="فاز"), _p(2, "ب", outcome="خسر"),
        _p(3, "ج", outcome="لم يُقدَّم"), _p(4, "د", outcome="قيد التقييم"),
        _p(5, "هـ"),
    ]
    s = hist.outcome_stats(projects)
    assert (s["won"], s["lost"], s["not_submitted"], s["pending"], s["unset"]) \
        == (1, 1, 1, 1, 1)


def test_lessons_block_carries_outcome_and_reason(hist):
    block = hist.lessons_block([
        _p(1, "توريد أجهزة", "وزارة الصحة", "خسر", "نسبة المحتوى المحلي"),
    ])
    assert "توريد أجهزة" in block
    assert "خسر" in block
    assert "نسبة المحتوى المحلي" in block


@pytest.mark.parametrize("outcome", ["", "قيد التقييم"])
def test_tenders_without_a_settled_outcome_teach_nothing(hist, outcome):
    """
    منافسة بلا نتيجة لا درس فيها، وإدراجها يوهم النموذج بسابقة لا توجد.
    """
    assert hist.lessons_block([_p(1, "أ", "جهة", outcome, "ملاحظة")]) == ""


def test_lessons_block_warns_against_treating_precedent_as_guarantee(hist):
    block = hist.lessons_block([_p(1, "أ", "جهة", "فاز", "عرض قوي")])
    assert "لا تعامل نتيجة سابقة" in block


def test_lessons_block_empty_without_history(hist):
    assert hist.lessons_block([]) == ""
    assert hist.lessons_block(None) == ""


def test_history_reaches_the_gonogo_context(fake_streamlit, monkeypatch):
    """السوابق كانت محفوظة في قاعدة البيانات بلا من يقرأها."""
    from views import analysis

    monkeypatch.setattr(analysis.knowledge, "build_context", lambda *a, **k: "")
    monkeypatch.setattr(analysis.db, "list_projects", lambda: [
        {"id": 1, "name": "توريد أجهزة أشعة", "entity": "وزارة الصحة",
         "outcome": "خسر", "outcome_note": "نسبة المحتوى المحلي"},
        {"id": 2, "name": "توريد أجهزة أشعة رقمية", "entity": "وزارة الصحة",
         "outcome": "", "outcome_note": ""},
    ])
    fake_streamlit.session_state.update({
        "_project_id": 2, "c_name": "شركة", "project_context": {}, "df_boq": None,
    })

    ctx = analysis._qualification_context()
    assert "نسبة المحتوى المحلي" in ctx


def test_gonogo_context_survives_a_database_failure(fake_streamlit, monkeypatch):
    """تعذّر قراءة السجل لا يُسقط التحليل كله."""
    from views import analysis

    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(analysis.knowledge, "build_context", lambda *a, **k: "")
    monkeypatch.setattr(analysis.db, "list_projects", boom)
    fake_streamlit.session_state.update({"_project_id": 1, "c_name": "شركة"})

    assert "شركة" in analysis._qualification_context()
