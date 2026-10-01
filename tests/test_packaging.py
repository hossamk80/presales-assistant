"""
اختبارات التعبئة — `requirements.txt` و `constraints.txt` و ما يستهلكهما.

الملفّان يفترقان بصمت: تُضاف تبعية إلى `requirements.txt` ولا تُثبَّت نسختها،
فيعود القيد جزئياً ويصير `>=` بلا سقف من جديد لتلك الحزمة وحدها — وهو بالضبط
العطب الذي أُنشئ `constraints.txt` لمنعه.
"""
import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
REQUIREMENTS = REPO / "requirements.txt"
DEV_REQUIREMENTS = REPO / "requirements-dev.txt"
CONSTRAINTS = REPO / "constraints.txt"
CI = REPO / ".github" / "workflows" / "ci.yml"

# `Pillow` و `Pillow-SIMD` وأمثالهما: التطبيع يوحّد الشرطة والشرطة السفلية
# وحالة الأحرف، وهي ثلاثة فروق تكتبها الحزم كما تشاء.
def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).strip().lower()


def _declared(path: pathlib.Path) -> set:
    """أسماء الحزم في ملف متطلبات — بلا تعليقات ولا أسطر فارغة."""
    names = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        name = re.split(r"[<>=!~\[;]", line)[0].strip()
        if name:
            names.add(_normalize(name))
    return names


@pytest.fixture(scope="module")
def constraints_text():
    return CONSTRAINTS.read_text(encoding="utf-8")


def test_the_constraints_file_exists_and_is_not_empty(constraints_text):
    assert _declared(CONSTRAINTS), "constraints.txt بلا قيود"


def test_every_pin_is_exact(constraints_text):
    """
    `>=` في ملف القيود لا يقيّد شيئاً. القيد يعني نسخةً واحدة بالضبط.
    """
    loose = []
    for line in constraints_text.splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        if "==" not in line:
            loose.append(line)
    assert loose == [], f"قيود غير محكمة: {loose}"


def test_every_declared_dependency_is_pinned():
    """
    كل ما في `requirements.txt` له نسخة مثبَّتة. تبعية جديدة بلا قيد تعود
    بنا إلى `>=` المفتوحة — لهذه الحزمة وحدها، وهو أخبث من غياب الملف كلّه
    لأنه لا يظهر.
    """
    declared = _declared(REQUIREMENTS) | _declared(DEV_REQUIREMENTS)
    missing = sorted(declared - _declared(CONSTRAINTS))
    assert missing == [], (
        "تبعيات معلنة بلا نسخة مثبَّتة — أضِفها إلى constraints.txt: "
        f"{missing}"
    )


def test_the_dev_tools_are_declared_in_one_file_and_pinned():
    """
    أدوات الفحص كانت أسماؤها مكتوبةً في ثلاثة مواضع — خطوة CI و `setup.sh`
    و`requirements.txt` معطَّلةً بتعليق — فأداةٌ تُضاف في أحدها وتُنسى في
    الآخرين: نظيفٌ محلياً وأحمرُ في CI أو العكس. الإعلان صار في ملف واحد.
    """
    declared = _declared(DEV_REQUIREMENTS)
    pinned = _declared(CONSTRAINTS)

    for tool in ("pytest", "pytest-timeout", "pyflakes", "pytest-cov",
                 "pytesseract", "pdf2image"):
        assert _normalize(tool) in declared, f"{tool} ليس في requirements-dev.txt"
        assert _normalize(tool) in pinned, f"{tool} بلا نسخة مثبَّتة"

    # ولا تُعلَن أداة فحص في ملف التشغيل: مستخدمٌ يثبّت التشغيل لا يحتاجها
    runtime = _declared(REQUIREMENTS)
    for tool in ("pytest", "pyflakes", "pytest-cov"):
        assert _normalize(tool) not in runtime, f"{tool} في requirements.txt"


def test_ci_installs_through_the_constraints_file():
    """
    ملف قيود لا يمرّره أحد ملفٌّ ميت. كل استدعاء `pip install` في CI يمرّ به.
    """
    text = CI.read_text(encoding="utf-8")
    installs = [
        line.strip() for line in text.splitlines()
        if "pip install" in line and "--upgrade pip" not in line
    ]
    assert installs, "لم يُعثر على أي تثبيت في CI"
    for line in installs:
        assert "-c constraints.txt" in line, f"تثبيت بلا قيود: {line}"


def test_ci_installs_the_dev_tools_from_their_file():
    """
    خطوة CI تقرأ `requirements-dev.txt` ولا تكتب أسماء الأدوات بنفسها —
    وإلا عاد الإعلان متفرّقاً ولو بقي الملف موجوداً.
    """
    text = CI.read_text(encoding="utf-8")
    assert "-r requirements-dev.txt" in text

    for tool in ("pytest-timeout", "pyflakes", "pytesseract", "pdf2image"):
        for line in text.splitlines():
            if "pip install" in line:
                assert tool not in line, f"{tool} مكتوب في خطوة CI: {line.strip()}"


def test_ocr_is_optional_at_runtime_and_required_for_the_checks():
    """
    البند 10 من الجرد: كانت `pytesseract` و `pdf2image` معطَّلتين بتعليق في
    ملف التشغيل بوصفهما «اختياريتين» وتُثبَّتهما خطوة CI وتهيئة الحاوية —
    الإعلان يقول شيئاً والتشغيل يقول غيره.

    الحقيقة: اختياريتان للتشغيل (`ocr_available()` ترجع `False` بلا كسر)
    وإلزاميتان للفحص. فمكانهما ملف الفحص وحده.
    """
    from utils import file_handler

    runtime = _declared(REQUIREMENTS)
    dev = _declared(DEV_REQUIREMENTS)
    for tool in ("pytesseract", "pdf2image"):
        assert _normalize(tool) not in runtime, tool
        assert _normalize(tool) in dev, tool

    # والشيفرة تحتمل غيابهما فعلاً لا بالتعليق
    assert isinstance(file_handler.ocr_available(), bool)


# ─── الوثائق مقابل الشيفرة ────────────────────────────────────────────────────
#
# خمسة ادّعاءات في `PLAN.md` و `HANDOFF.md` بقيت تقول «غير منفَّذ» بعد أن
# نُفِّذ ما تصفه. الوثيقة لا يشغّلها أحد فلا يكشف قِدَمها إلا القارئ — وهو
# يثق بها. ما يلي يربط الادّعاءات القابلة للفحص بالشيفرة نفسها.

DOCS = (REPO / "docs" / "PLAN.md", REPO / "docs" / "HANDOFF.md", REPO / "README.md")


def _docs_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS)


def test_no_document_still_claims_the_connector_cannot_push():
    """
    الدفع نُفِّذ في ب-6. جملةٌ تقول إن الطبقة «لا تحمل مساراً له» تجعل من
    يقرأها يبني مساراً ثانياً — بلا البوابات الأربع.
    """
    from utils.connectors import base, odoo

    assert hasattr(base.Connector, "push_order") and odoo.OdooConnector.supports_push

    text = _docs_text()
    for claim in ("لا تحمل\nمساراً له أصلاً",
                  "الطبقة لا تحمل مساراً له",
                  "**الدفع مؤجَّل بقرار المستخدم — والطبقة لا تحمل مساراً له.**"):
        assert claim not in text, claim


def test_no_document_still_claims_prompt_management_is_unbuilt():
    """إدارة البرومبتات (14-1) منفَّذة خلف صلاحية `prompts.manage`."""
    from utils import db

    for name in ("prompt_override", "save_prompt", "set_prompt_enabled"):
        assert hasattr(db, name), name

    settings = (REPO / "views" / "settings.py").read_text(encoding="utf-8")
    assert "_prompts_section" in settings

    assert "الشيفرة) فلم يُنفَّذ بعد." not in _docs_text()


def test_the_plan_does_not_reopen_what_its_own_inventory_closed():
    """
    كانت الخطة تناقض نفسها: سطرٌ يقول «يبقى دفع الموصّل» وآخر بعده بثلاثين
    سطراً يقول إنه نُفِّذ. المتناقضان معاً أسوأ من أحدهما خطأً، إذ لا يُعرف
    أيّهما المعتمد.
    """
    plan = (REPO / "docs" / "PLAN.md").read_text(encoding="utf-8")

    assert "يبقى من الخطة: **دفع** الموصّل حين يُقرَّر" not in plan
    assert "**ما بقي مفتوحاً من المرحلة 13**" not in plan
    # والجرد نفسه لا يزال يعلن إغلاقه
    assert "ب-8 أُنجز، ولا بند مفتوح في النظام كلّه" in plan


# ─── قياس التغطية (البند 9) ───────────────────────────────────────────────────

COVERAGERC = REPO / ".coveragerc"
COV_SCRIPT = REPO / "scripts" / "check_coverage.py"


def test_coverage_is_configured_in_one_place():
    """
    بلا `.coveragerc` يقيس CI شيئاً والتشغيل المحلي شيئاً آخر لنفس الشيفرة،
    فلا يُعرف أيّ الرقمين يُقارَن بالأرضية.
    """
    assert COVERAGERC.exists()
    text = COVERAGERC.read_text(encoding="utf-8")

    for layer in ("app", "utils", "views", "components"):
        assert layer in text, layer
    assert "tests/*" in text, "الاختبارات تُقاس وترفع النسبة بلا معنى"

    # `app.py` بالمسار يجعل coverage يستورد الملف وقت الجمع فيُحمَّل numpy
    # مرّتين — وقع فعلاً. الاسم `app` وحده.
    assert "\n    app.py\n" not in text


def test_the_floors_cover_every_measured_layer():
    """
    طبقةٌ لا تذكرها `FLOORS` تمرّ بلا أرضية. السكربت يرفضها، وهذا يتأكّد أن
    الطبقات المعلَنة هي طبقات المستودع فعلاً لا أسماء قديمة.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("check_coverage", COV_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    declared = {name for name, *_ in module.FLOORS}
    assert declared == {"utils", "utils/db", "app.py", "components",
                        "views", "utils/providers"}, declared

    # وكل أرضية دون المقيس وقت الضبط: أرضيةٌ تساويه تُسقط البناء بأول تذبذب
    for name, floor, measured, _why in module.FLOORS:
        assert floor < measured, f"{name}: الأرضية {floor} لا تحتمل تذبذباً"
        assert floor > 0, name


def test_ci_enforces_the_coverage_floors():
    """ملفُّ أرضياتٍ لا يشغّله أحد لا يمنع انحداراً."""
    text = CI.read_text(encoding="utf-8")
    assert "--cov" in text
    assert "scripts/check_coverage.py" in text


def test_no_document_still_claims_anthropic_cannot_stream():
    """
    ب-2 اكتمل: الموفّرون الثلاثة كلهم يبثّون. جملةٌ تقول إن Anthropic «لم
    يُنفَّذ بعد» تدفع من يقرؤها إلى تنفيذٍ ثانٍ لما هو قائم.
    """
    from utils.providers.anthropic_provider import AnthropicProvider
    from utils.providers.gemini import GeminiProvider
    from utils.providers.openai_compat import OpenAICompatProvider

    for provider in (AnthropicProvider, GeminiProvider, OpenAICompatProvider):
        assert provider.streams is True, provider.__name__
        assert "generate_stream" in provider.__dict__, provider.__name__

    assert "**Anthropic لم يُنفَّذ بعد**" not in _docs_text()


# ─── الترخيص ونسخ الإجراءات (البندان 11 و12) ─────────────────────────────────

LICENCE = REPO / "LICENSE"
WORKFLOWS = sorted((REPO / ".github" / "workflows").glob("*.yml"))


def test_the_repository_declares_its_licence():
    """
    مستودعٌ عامٌّ بلا ملف ترخيص يُقرأ على وجهين: من يراه يفترض الإباحة، ومن
    يملكه يظنّ حقّه محفوظاً. والملف هو ما يحسم.
    """
    assert LICENCE.is_file(), "لا ملف LICENSE"
    text = LICENCE.read_text(encoding="utf-8")

    assert "All rights reserved" in text
    assert "جميع الحقوق محفوظة" in text
    assert "No licence is granted" in text
    assert "لا يُمنح أيّ ترخيص" in text


def test_the_licence_does_not_point_at_a_file_that_is_not_there():
    """
    الترخيص يحيل إلى رخصة الخطّ المُضمَّن. إحالةٌ إلى مسارٍ غير موجود تُسقط
    الاستثناء الذي تَعِد به: الخطّ تحت OFL، وإعادة توزيعه مشروطة بمرافقة نصّه.
    """
    import re

    text = LICENCE.read_text(encoding="utf-8")
    # الامتداد صريح حتى لا تُبتلع نقطة نهاية الجملة جزءاً من المسار
    referenced = set(re.findall(r"(static/fonts/[A-Za-z0-9_-]+\.[A-Za-z0-9]+)", text))

    assert referenced, "الترخيص لا يذكر رخصة الخطّ أصلاً"
    for path in sorted(referenced):
        assert (REPO / path).is_file(), path


def test_the_readme_points_at_the_licence():
    """ترخيصٌ لا يذكره الملفّ الأول لا يراه أحد."""
    readme = (REPO / "README.md").read_text(encoding="utf-8")

    assert "(LICENSE)" in readme
    assert "جميع الحقوق محفوظة" in readme


def test_no_workflow_runs_an_action_on_a_retired_node():
    """
    البند 12: `checkout@v4` و `setup-python@v5` على Node 20 المهجور — يعملان
    اليوم لأن الرانر يُجبرهما على Node 24، ويكسران يوم يُسحب الإجبار **بلا
    تغييرٍ منّا**. النسخ المحظورة أدناه مُتحقَّق من زمن تشغيلها من `action.yml`
    في مستودع كل إجراء، لا من الذاكرة.
    """
    import re

    retired = {
        "actions/checkout": 4,          # v4 node20 · v5+ node24
        "actions/setup-python": 5,      # v5 node20 · v6+ node24
        "actions/configure-pages": 5,   # v5 node20 · v6 node24
        "actions/deploy-pages": 4,      # v4 node20 · v5 node24
    }

    found = 0
    for workflow in WORKFLOWS:
        for line in workflow.read_text(encoding="utf-8").splitlines():
            match = re.search(r"uses:\s*(actions/[\w-]+)@v(\d+)", line)
            if not match:
                continue
            action, major = match.group(1), int(match.group(2))
            found += 1
            limit = retired.get(action)
            if limit is not None:
                assert major > limit, (
                    f"{workflow.name}: {action}@v{major} على Node مهجور — "
                    f"ارفعها فوق v{limit}"
                )
    assert found >= 5, f"لم يُعثر إلا على {found} إجراءات — هل تغيّر الشكل؟"


def test_every_action_is_pinned_to_a_major_version():
    """
    `@main` أو `@master` يعني أن بناءنا يتغيّر بتغيير مستودعٍ لا نملكه —
    وهو نفس العطب الذي عالجه `constraints.txt` في حزم Python.
    """
    import re

    for workflow in WORKFLOWS:
        for line in workflow.read_text(encoding="utf-8").splitlines():
            if "uses:" not in line:
                continue
            ref = line.split("uses:")[1].strip()
            assert "@" in ref, f"{workflow.name}: إجراء بلا وسم: {ref}"
            tag = ref.split("@")[1]
            assert re.fullmatch(r"v\d+(\.\d+)*|[0-9a-f]{40}", tag), \
                f"{workflow.name}: وسم غير مثبَّت: {ref}"
