"""
اختبارات حزمة `utils/db/` — البنية لا السلوك.

كانت وحدةً واحدة من ٢٬٧٩٢ سطراً، وصارت حزمةً بوحدة لكل مجال. ما تحرسه هذه
الاختبارات هو ما يكسره التقسيم بصمت: واجهةٌ تفقد اسماً، ووحدتان تعرّفان
الاسم نفسه، ودورةُ استيراد، وترقيعٌ للمسار لا يصل إلى من يقرؤه.
"""
import ast
import pathlib
import sqlite3

import pytest

PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "utils" / "db"


def _modules():
    return sorted(p for p in PACKAGE.glob("*.py") if p.name != "__init__.py")


def _definitions(path):
    """الأسماء التي تعرّفها وحدة على مستواها الأعلى."""
    names = set()
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def test_the_package_was_actually_split():
    """مجلّدٌ بوحدةٍ واحدة تقسيمٌ بالاسم فقط."""
    assert len(_modules()) >= 5


def test_no_name_is_defined_in_two_modules():
    """
    اسمان متطابقان في وحدتين: الواجهة تستورد أحدهما ويُطمس الآخر صامتاً،
    فيستدعي المتصل دالّةً غير التي يظنّ.
    """
    seen = {}
    clashes = []
    for path in _modules():
        for name in _definitions(path):
            if name in seen:
                clashes.append(f"{name}: {seen[name]} · {path.name}")
            seen[name] = path.name
    assert clashes == [], clashes


def test_every_public_name_reaches_the_facade():
    """
    `from utils import db` ثم `db.save_project(...)` يجب أن يبقى عاملاً.
    اسمٌ عامٌّ في وحدة فرعية لا تعيد الواجهة تصديره مفقودٌ على كل المتصلين.
    """
    from utils import db

    missing = []
    for path in _modules():
        for name in _definitions(path):
            if name.startswith("_"):
                continue
            if not hasattr(db, name):
                missing.append(f"{path.name}.{name}")
    assert missing == [], missing


def test_the_package_has_no_import_cycle():
    """
    دورةٌ بين وحدتين تُسقط الاستيراد كلّه — أو أسوأ: تنجح بترتيبٍ وتفشل
    بآخر. `_core` أساسٌ لا يستورد من أخواته، وعليه يقوم المنع.
    """
    edges = {}
    for path in _modules():
        deps = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.level and node.module:
                deps.add(node.module)
            elif isinstance(node, ast.ImportFrom) and node.level and not node.module:
                deps |= {a.name for a in node.names}
        edges[path.stem] = deps & {p.stem for p in _modules()}

    assert edges["_core"] == set(), f"النواة تستورد من أخواتها: {edges['_core']}"

    seen, stack = set(), []

    def visit(mod):
        if mod in stack:
            pytest.fail(f"دورة استيراد: {' → '.join(stack + [mod])}")
        if mod in seen:
            return
        stack.append(mod)
        for dep in sorted(edges.get(mod, ())):
            visit(dep)
        stack.pop()
        seen.add(mod)

    for mod in edges:
        visit(mod)


def test_rebindable_globals_are_not_re_exported():
    """
    `_active_company_id` و `_company_resolver` يُسنَدان من جديد داخل `_core`.
    إعادة تصديرهما تنسخ الارتباط لا تتابعه، فيقرأ من يثق بالواجهة قيمةً
    ميتة بلا خطأ يُرفع. القراءة عبر `active_company_id()` وحدها.
    """
    from utils import db

    for name in ("_active_company_id", "_company_resolver"):
        assert not hasattr(db, name), name


def test_the_database_path_is_read_live_not_copied(tmp_path, monkeypatch):
    """
    حارس ارتداد على عطبٍ وقع فعلاً: بعد التقسيم صار
    `monkeypatch.setattr(db, "DB_PATH", ...)` يضبط صفة **الواجهة** بينما
    `_connect` يقرأ أصلها في `_core` — ترقيعٌ صامتٌ بلا أثر، والاختبارات
    تكتب في قاعدة المطوّر الحقيقية بدل المؤقّتة.
    """
    from utils import db

    target = tmp_path / "live.db"
    monkeypatch.setattr(db._core, "DB_PATH", str(target))
    db._local.__dict__.pop("conn", None)
    try:
        db.get_conn().execute("SELECT 1").fetchone()
        assert target.exists(), "الاتصال لم يُفتح على المسار المُرقَّع"
    finally:
        db._local.__dict__.pop("conn", None)


def test_the_temp_db_fixture_really_isolates(temp_db, tmp_path):
    """
    الفخّ نفسه من جهة المستهلك: لو فقد `temp_db` عزله لكتب كل اختبار في
    قاعدة واحدة — فتتسرّب البيانات بين الاختبارات، وتُمحى بيانات من يشغّلها.
    """
    temp_db.create_project("منافسة معزولة", {})

    written = [p for p in tmp_path.rglob("*.db")]
    assert written, "لم تُكتب أي قاعدة داخل مجلّد الاختبار"

    found = False
    for path in written:
        conn = sqlite3.connect(path)
        try:
            rows = conn.execute("SELECT name FROM projects").fetchall()
        except sqlite3.DatabaseError:
            continue
        finally:
            conn.close()
        found = found or any(r[0] == "منافسة معزولة" for r in rows)
    assert found, "المنافسة لم تُكتب في قاعدة الاختبار المؤقّتة"
