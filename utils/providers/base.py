"""
utils/providers/base.py — الواجهة الموحّدة للموفّرين (11-1)

كل موفّر ينفّذ نفس العمليات الخمس: `generate` · `generate_json` · `embed` ·
`count_tokens` · وإرجاع الاستهلاك ضمن نتيجة كل استدعاء. تبديل الموفّر لا
يمسّ أي ملف في `views/` — الواجهات تستدعي `utils/ai_engine.py` الذي يمرّ
من هذه الطبقة.
"""
from dataclasses import dataclass, field
from typing import Any, Optional


class ProviderError(Exception):
    """فشل استدعاء موفّر — تُعرض رسالته للمستخدم كما هي."""


class BudgetExceeded(ProviderError):
    """تجاوز حدّ الإنفاق الشهري — يمنع الاستدعاء برسالة صريحة (11-9)."""


@dataclass
class Usage:
    """عدّادات التوكن **كما أرجعها الموفّر** لا كما قدّرناها محلياً."""
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0


@dataclass
class GenResult:
    text: Optional[str] = None
    parsed: Any = None
    provider: str = ""
    model: str = ""
    usage: Usage = field(default_factory=Usage)
    elapsed_ms: int = 0


def to_json_schema(schema: dict) -> dict:
    """
    يحوّل مخطط Gemini (أنواع بأحرف كبيرة: OBJECT/ARRAY/STRING…) إلى
    JSON Schema قياسي يفهمه OpenAI و Anthropic.
    """
    if not isinstance(schema, dict):
        return schema

    out: dict = {}
    for key, value in schema.items():
        if key == "type" and isinstance(value, str):
            out["type"] = value.lower()
        elif key == "properties" and isinstance(value, dict):
            out["properties"] = {k: to_json_schema(v) for k, v in value.items()}
        elif key == "items" and isinstance(value, dict):
            out["items"] = to_json_schema(value)
        else:
            out[key] = value

    if out.get("type") == "object":
        out.setdefault("additionalProperties", False)
        # المخططات الصارمة تتطلب إدراج كل الحقول في required
        if "properties" in out:
            out["required"] = list(out["properties"])
    return out


def schema_instruction(schema: dict) -> str:
    """تعليمة احتياطية للموفّرين بلا دعم مخططات: صف الشكل واطلب JSON فقط."""
    import json

    return (
        "\n\nأجب بمستند JSON واحد صالح فقط، بلا أي نص قبله أو بعده، "
        "مطابقاً لهذا المخطط:\n" + json.dumps(to_json_schema(schema), ensure_ascii=False)
    )


class Provider:
    """الواجهة التي ينفّذها كل موفّر. الدوال ترفع ProviderError عند الفشل."""

    name = ""

    # هل يدعم هذا الموفّر البثّ التدريجي؟ (ب-2)
    #
    # موفّر لا يدعمه **لا يُكسَر**: `providers.run_stream` تسقط إلى استدعاء
    # عادي فيرى المستخدم النتيجة دفعةً واحدة كما اليوم. البثّ تحسينٌ في
    # التجربة لا شرطٌ لعمل النظام.
    streams = False

    def generate(self, model_id: str, prompt: str,
                 temperature: Optional[float] = None,
                 max_tokens: Optional[int] = None) -> GenResult:
        raise NotImplementedError

    def generate_stream(self, model_id: str, prompt: str,
                        temperature: Optional[float] = None,
                        max_tokens: Optional[int] = None):
        """
        مولِّد يُخرج مقاطع النصّ تباعاً، **ويُعيد `GenResult` عند انتهائه**
        (عبر `return` في المولِّد — تُلتقط بـ `yield from`).

        النتيجة النهائية تحمل عدّادات الاستهلاك **كما أرجعها الموفّر** في آخر
        الدفق: القياس المحلي تقدير، والفوترة لا تُبنى على تقدير (11-8).
        """
        raise NotImplementedError

    def generate_json(self, model_id: str, prompt: str, schema: dict,
                      temperature: Optional[float] = None,
                      max_tokens: Optional[int] = None) -> GenResult:
        raise NotImplementedError

    def embed(self, model_id: str, texts: list, task_type: str,
              dims: int) -> tuple[list, Usage]:
        raise NotImplementedError

    def count_tokens(self, model_id: str, text: str) -> Optional[int]:
        return None
