"""
utils/ai_engine/language.py — لغة المخرجات: الخيارات والتعليمة واتجاه الكتابة.
"""


# ─── اللغة ────────────────────────────────────────────────────────────────────

LANGUAGES = {
    "ar": {
        "label": "العربية",
        "rtl": True,
        "instruction": "الرد باللغة العربية فقط.",
    },
    "en": {
        "label": "English",
        "rtl": False,
        "instruction": (
            "Respond in English only. Use professional bid-writing register "
            "suited to Saudi government tenders."
        ),
    },
    "both": {
        "label": "العربية والإنجليزية",
        "rtl": True,
        "instruction": (
            "اكتب المحتوى مرتين: أولاً بالعربية كاملاً، ثم افصل بسطر يحتوي "
            "`---` وحده، ثم اكتب الترجمة الإنجليزية الكاملة لنفس المحتوى "
            "تحت عنوان `## English Version`. يجب أن تتطابق النسختان في "
            "المعنى والبنية."
        ),
    },
}


DEFAULT_LANGUAGE = "ar"


def language_instruction(language: str) -> str:
    return LANGUAGES.get(language, LANGUAGES[DEFAULT_LANGUAGE])["instruction"]


def is_rtl(language: str) -> bool:
    return LANGUAGES.get(language, LANGUAGES[DEFAULT_LANGUAGE])["rtl"]
