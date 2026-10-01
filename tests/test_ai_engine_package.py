"""
اختبارات حزمة `utils/ai_engine/` — البنية لا السلوك.

كانت وحدةً واحدة من ١٬٧٩٨ سطراً تخلط النصوص بالمخططات بالمنطق. وما يحرسه
هذا الملف هو ما يكسره التقسيم بصمت: واجهةٌ تفقد اسماً، ووحدتان تعرّفان الاسم
نفسه، ودورةُ استيراد — و**ترقيعٌ يُعيد ربط اسم على الواجهة فلا يصل إلى من
يقرؤه**، وهو العطب الذي أسقط أربعة اختبارات فعلاً عند التقسيم.
"""
import ast
import pathlib

import pytest

PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "utils" / "ai_engine"
TESTS = pathlib.Path(__file__).resolve().parent


def _modules():
    return sorted(p for p in PACKAGE.glob("*.py") if p.name != "__init__.py")


def _definitions(path):
    names = set()
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _owner_map():
    owner = {}
    for path in _modules():
        for name in _definitions(path):
            owner[name] = path.stem
    return owner


def test_the_package_was_actually_split():
    assert len(_modules()) >= 5


def test_no_name_is_defined_in_two_modules():
    """الواجهة تستورد أحدهما ويُطمس الآخر صامتاً."""
    seen, clashes = {}, []
    for path in _modules():
        for name in _definitions(path):
            if name in seen:
                clashes.append(f"{name}: {seen[name]} · {path.stem}")
            seen[name] = path.stem
    assert clashes == [], clashes


def test_every_public_name_reaches_the_facade():
    """`from utils import ai_engine` ثم `ai_engine.ai_generate(...)` يبقى عاملاً."""
    from utils import ai_engine

    missing = [f"{path.stem}.{name}"
               for path in _modules()
               for name in sorted(_definitions(path))
               if not name.startswith("_") and not hasattr(ai_engine, name)]
    assert missing == [], missing


def test_the_package_has_no_import_cycle():
    """`models` و `language` و `schemas` و `library` و `review` أوراق."""
    stems = {p.stem for p in _modules()}
    edges = {}
    for path in _modules():
        deps = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.level:
                deps.add(node.module) if node.module else deps.update(
                    a.name for a in node.names)
        edges[path.stem] = deps & stems

    for leaf in ("models", "language", "schemas", "library", "review"):
        assert edges.get(leaf) == set(), f"{leaf} لم تعد ورقة: {edges.get(leaf)}"

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


def test_only_the_engine_module_calls_the_model():
    """
    **مَعبرٌ واحد إلى النموذج.** `providers.run` و `run_stream` في `engine`
    وحدها، لأن هناك تُلحق القواعد الثابتة (14-2) — استدعاءٌ من وحدة أخرى
    يذهب إلى الموفّر **بلا قواعد**، ومنها منع التسعير وشرط القرار البشري.

    وقراءة سجلّ النماذج ليست استدعاءً: `models.resolve_model` تسأل
    `providers.model_options()` عن الأسماء المتاحة ولا تُنفق توكناً.
    """
    import re

    offenders = []
    for path in _modules():
        if path.stem == "engine":
            continue
        for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\bproviders\.run(_stream)?\s*\(", line):
                offenders.append(f"{path.stem}:{number}: {line.strip()}")
    assert offenders == [], offenders


def test_no_test_patches_a_rebound_name_on_the_facade():
    """
    **حارس الصنف كلّه.** `monkeypatch.setattr(ai_engine, "_call_json", …)`
    يُعيد ربط الاسم على الواجهة بينما `engine.ai_generate_json` يقرؤه من
    فضائه هو — فيمرّ الاختبار وهو **لا يرقّع شيئاً**: الدالّة الحقيقية تُستدعى
    ويُحسب نجاحها نجاحاً للمحاكاة. أسقط هذا أربعة اختبارات عند التقسيم،
    ولولا سقوطها لمرّت كاذبة.

    الصواب: رقّع الوحدة التي **تقرأ** الاسم — `ai_engine.engine` غالباً.

    ووحدةٌ مستورَدة (`providers` · `time`) ليست من هذا الباب: ما يُعدَّل
    صفةٌ عليها لا ارتباط اسمها، والكائن واحد.
    """
    owner = _owner_map()
    aliases = {"ae", "ai_engine"}
    offenders = []

    for path in sorted(TESTS.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "setattr"
                    and len(node.args) >= 2):
                continue
            target, attr = node.args[0], node.args[1]
            if not (isinstance(target, ast.Name) and target.id in aliases):
                continue
            if not (isinstance(attr, ast.Constant) and isinstance(attr.value, str)):
                continue
            if attr.value in owner:
                offenders.append(
                    f"{path.name}:{node.lineno} setattr({target.id}, "
                    f"{attr.value!r}) — رقّع {target.id}.{owner[attr.value]}"
                )
    assert offenders == [], offenders
