"""
utils/ai_engine/ — محرك الذكاء الاصطناعي

منذ المرحلة 11 يمرّ كل استدعاء من طبقة الموفّرين `utils/providers/`:
تعدد الموفّرين والنماذج، قياس الاستهلاك، حدّ الإنفاق، وذاكرة النتائج —
كل ذلك هناك، وهذه الحزمة تحفظ واجهة `ai_generate` / `ai_generate_json`
كما تعرفها الواجهات فلا يمسّها تبديل الموفّر.

كانت وحدةً واحدة من ١٬٧٩٨ سطراً تخلط **النصوص** بالمخططات بالمنطق،
و**الواجهة لم تتغيّر**: `from utils import ai_engine` ثم
`ai_engine.ai_generate(...)` يعمل كما كان.

الترتيب أدناه هو ترتيب الاعتماد **بلا دورات**: أوراقٌ لا تعتمد على شيء
(`models` · `language` · `schemas` · `library` · `review`)، ثم `rules`
و `prompts`، ثم `engine` التي تجمعها — وهي وحدها من يستدعي `providers`.
"""

# وحدتان كانتا في فضاء `ai_engine` حين كان ملفاً واحداً، وتعتمد عليهما
# الاختبارات: `monkeypatch.setattr(ai_engine.providers, "run", …)` و
# `setattr(ai_engine.time, "sleep", …)`.
#
# إعادة تصديرهما **آمنة هنا** لأن ما يُعدَّل صفةٌ **على الوحدة** لا ارتباط
# الاسم: الكائن واحد يراه `engine` كما تراه الواجهة. أمّا إعادة ربط الاسم
# نفسه — `setattr(ai_engine, "providers", بديل)` — فترقيعٌ صامتٌ بلا أثر،
# لأن `engine._call` يقرأ `providers` من فضائه هو. رقّع `ai_engine.engine`
# حين تريد الاستبدال الكامل.
import time  # noqa: F401

from utils import providers  # noqa: F401

from .models import (  # noqa: F401
    CHARS_PER_TOKEN,
    CONTEXT_CHAR_BUDGET,
    CONTEXT_TOKEN_BUDGET,
    DEFAULT_MODEL,
    MODELS,
    MODEL_NAMES,
    default_model_name,
    estimate_tokens,
    model_names,
    resolve_model,
)

from .language import (  # noqa: F401
    DEFAULT_LANGUAGE,
    LANGUAGES,
    is_rtl,
    language_instruction,
)

from .schemas import (  # noqa: F401
    BOQ_SCHEMA,
    COMPLIANCE_CATEGORIES,
    COMPLIANCE_SCHEMA,
    CRITICALITY_LEVELS,
    KEY_PERSONNEL_SCHEMA,
    MANDATORY_OUTLINE_SECTIONS,
    OUTLINE_SCHEMA,
    PROJECT_CONTEXT_SCHEMA,
    REVIEW_SCHEMA,
    SUBMISSION_SCHEMA,
    TIMELINE_SCHEMA,
    TRACEABILITY_SCHEMA,
)

from .library import (  # noqa: F401
    EXTRACT_PROMPTS,
    PROMPTS,
)

from .review import (  # noqa: F401
    REVIEW_LENSES,
)

from .rules import (  # noqa: F401
    FIXED_RULES,
    FIXED_RULES_MARKER,
    GLOSSARY_MARKER,
    GLOSSARY_TOP_N,
    STYLE_MARKER,
    apply_fixed_rules,
    glossary_context_block,
    glossary_instruction,
    has_fixed_rules,
    has_glossary,
    has_style_instruction,
    relevant_terms,
    style_instruction,
)

from .prompts import (  # noqa: F401
    AGENT_EXTRACT,
    AGENT_REVIEW,
    AGENT_WRITE,
    REVIEW_PROMPT_PREFIX,
    active_prompt,
    active_sector,
    build_prompt,
    default_prompt,
    editable_prompts,
    missing_prompt_fields,
    outline_prompt,
    prompt_fields,
    prompt_problem,
)

from .engine import (  # noqa: F401
    RETRY_ATTEMPTS,
    RETRY_BASE_DELAY,
    ai_generate,
    ai_generate_json,
    count_tokens_exact,
    has_credentials,
    trial_cost_estimate,
    trial_field_defaults,
    trial_prompt,
    _call,
    _call_json,
    _is_transient,
    _split_into_chunks,
    _strip_code_fence,
    _with_retry,
)

# `pyflakes` لا يفهم `# noqa`، و`__all__` هو ما يجعل إعادة التصدير
# استعمالاً في نظره — وهي خطوة حاجزة في CI.
__all__ = [
    "providers",
    "time",
    # الستّة الخاصّة أدناه مقصودة: تستدعيها الاختبارات عبر `ai_engine.` أو
    # عبر الوحدة مباشرةً، ووجودها في `__all__` هو ما يجعل إعادة تصديرها
    # استعمالاً عند pyflakes.
    "_call",
    "_call_json",
    "_is_transient",
    "_split_into_chunks",
    "_strip_code_fence",
    "_with_retry",
    "AGENT_EXTRACT",
    "AGENT_REVIEW",
    "AGENT_WRITE",
    "BOQ_SCHEMA",
    "CHARS_PER_TOKEN",
    "COMPLIANCE_CATEGORIES",
    "COMPLIANCE_SCHEMA",
    "CONTEXT_CHAR_BUDGET",
    "CONTEXT_TOKEN_BUDGET",
    "CRITICALITY_LEVELS",
    "DEFAULT_LANGUAGE",
    "DEFAULT_MODEL",
    "EXTRACT_PROMPTS",
    "FIXED_RULES",
    "FIXED_RULES_MARKER",
    "GLOSSARY_MARKER",
    "GLOSSARY_TOP_N",
    "KEY_PERSONNEL_SCHEMA",
    "LANGUAGES",
    "MANDATORY_OUTLINE_SECTIONS",
    "MODELS",
    "MODEL_NAMES",
    "OUTLINE_SCHEMA",
    "PROJECT_CONTEXT_SCHEMA",
    "PROMPTS",
    "RETRY_ATTEMPTS",
    "RETRY_BASE_DELAY",
    "REVIEW_LENSES",
    "REVIEW_PROMPT_PREFIX",
    "REVIEW_SCHEMA",
    "STYLE_MARKER",
    "SUBMISSION_SCHEMA",
    "TIMELINE_SCHEMA",
    "TRACEABILITY_SCHEMA",
    "active_prompt",
    "active_sector",
    "ai_generate",
    "ai_generate_json",
    "apply_fixed_rules",
    "build_prompt",
    "count_tokens_exact",
    "default_model_name",
    "default_prompt",
    "editable_prompts",
    "estimate_tokens",
    "glossary_context_block",
    "glossary_instruction",
    "has_credentials",
    "has_fixed_rules",
    "has_glossary",
    "has_style_instruction",
    "is_rtl",
    "language_instruction",
    "missing_prompt_fields",
    "model_names",
    "outline_prompt",
    "prompt_fields",
    "prompt_problem",
    "relevant_terms",
    "resolve_model",
    "style_instruction",
    "trial_cost_estimate",
    "trial_field_defaults",
    "trial_prompt",
]
