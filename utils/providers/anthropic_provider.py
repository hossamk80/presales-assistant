"""
utils/providers/anthropic_provider.py — موفّر Anthropic Claude (SDK الرسمية)

- المخرجات المُهيكلة عبر `output_config.format` بمخطط JSON قياسي.
- البثّ التدريجي (ب-2) عبر `messages.stream` — العدّادات من الرسالة النهائية.
- التخزين المؤقت (11-12): `cache_control` تلقائي على مستوى الطلب حين تكون
  التعليمات كبيرة، وقراءة `cache_read_input_tokens` من الاستهلاك.
"""
import json
import time
from typing import Optional

import streamlit as st

from utils.providers.base import (
    GenResult, Provider, ProviderError, Usage, to_json_schema,
)

# دون هذا الحجم لا تُقبل البادئة في الذاكرة المؤقتة أصلاً فلا معنى للعلامة.
CACHE_MIN_CHARS = 4_000
DEFAULT_MAX_TOKENS = 16_000


class AnthropicProvider(Provider):
    name = "anthropic"

    # ب-2 مكتمل: كان هذا آخر موفّر يسقط إلى استدعاء عادي بلا بثّ.
    streams = True

    def _get_client(self):
        api_key = st.session_state.get("api_claude")
        if not api_key:
            raise ProviderError("missing_key")
        try:
            import anthropic
        except ImportError as e:
            raise ProviderError(f"anthropic SDK غير مثبّتة: {e}") from e
        return anthropic.Anthropic(api_key=api_key)

    @staticmethod
    def _usage(response) -> Usage:
        usage = getattr(response, "usage", None)
        if usage is None:
            return Usage()
        cached = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        return Usage(
            input_tokens=int(getattr(usage, "input_tokens", 0) or 0) + cached,
            cached_tokens=cached,
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
        )

    def _kwargs(self, model_id, prompt, temperature, max_tokens,
                output_config=None) -> dict:
        """
        وسائط الطلب — مشتركة بين الاستدعاء العادي والبثّ.

        **`temperature` كانت تُستقبَل وتُهمَل**: المعامل في التوقيع ولم يدخل
        الوسائط قطّ، فمستخدمٌ يضبط الحرارة في الإعدادات يراها تسري على Gemini
        و OpenAI ولا تسري على Claude — بلا خطأ يُرفع. وقياس التغطية هو ما
        كشفها: الملف كان بلا سطرٍ مفحوص.
        """
        kwargs = {
            "model": model_id,
            "max_tokens": max_tokens or DEFAULT_MAX_TOKENS,
            "messages": [{"role": "user", "content": prompt}],
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if output_config is not None:
            kwargs["output_config"] = output_config
        if len(prompt) >= CACHE_MIN_CHARS:
            kwargs["cache_control"] = {"type": "ephemeral"}
        return kwargs

    @staticmethod
    def _refuse_if_refused(response):
        if getattr(response, "stop_reason", None) == "refusal":
            raise ProviderError("رفض النموذج الطلب (safety refusal)")

    def _create(self, model_id, prompt, temperature, max_tokens, output_config=None):
        client = self._get_client()
        response = client.messages.create(
            **self._kwargs(model_id, prompt, temperature, max_tokens, output_config)
        )
        self._refuse_if_refused(response)
        text = "".join(
            block.text for block in response.content
            if getattr(block, "type", "") == "text"
        )
        return response, text

    def generate(self, model_id, prompt, temperature=None, max_tokens=None) -> GenResult:
        started = time.monotonic()
        response, text = self._create(model_id, prompt, temperature, max_tokens)
        return GenResult(
            text=text or None, provider=self.name, model=model_id,
            usage=self._usage(response),
            elapsed_ms=int((time.monotonic() - started) * 1000),
        )

    def generate_stream(self, model_id, prompt, temperature=None, max_tokens=None):
        """
        بثّ تدريجي عبر `client.messages.stream` (ب-2، آخر موفّر بلا بثّ).

        ثلاثة أشياء تُحسم هنا لا في المستدعي:

        · **العدّادات من الرسالة النهائية** لا من جمعٍ محليّ: Anthropic ترسل
          `input_tokens` في `message_start` و `output_tokens` في
          `message_delta`، و`get_final_message()` تجمعها كما أرسلها الموفّر.
          الفوترة لا تُبنى على تقدير (11-8).

        · **الرفض يُرفع بعد انتهاء الدفق**: `stop_reason == "refusal"` لا يظهر
          إلا في النهاية، فنصٌّ جزئيٌّ قد يكون وصل قبله. يُرفع استثناءً كما في
          الاستدعاء العادي فلا يُسلَّم نصُّ رفضٍ منقوصاً كأنه جواب.

        · **المولِّد يُغلِق الاتصال**: `with` يضمن ذلك ولو رُفع استثناءٌ في
          منتصف الدفق أو تُرك المولِّد بلا استنفاد.
        """
        client = self._get_client()
        started = time.monotonic()
        usage, final = Usage(), None

        with client.messages.stream(
            **self._kwargs(model_id, prompt, temperature, max_tokens)
        ) as stream:
            for event in stream:
                if getattr(event, "type", "") != "content_block_delta":
                    continue
                delta = getattr(event, "delta", None)
                piece = getattr(delta, "text", None) if delta is not None else None
                if piece:
                    yield piece
            # تُقرأ **داخل** `with`: الرسالة النهائية تُجمَّع من أحداث الدفق
            final = stream.get_final_message()

        if final is not None:
            self._refuse_if_refused(final)
            usage = self._usage(final)

        return GenResult(
            provider=self.name, model=model_id, usage=usage,
            elapsed_ms=int((time.monotonic() - started) * 1000),
        )

    def generate_json(self, model_id, prompt, schema,
                      temperature=None, max_tokens=None) -> GenResult:
        started = time.monotonic()
        response, text = self._create(
            model_id, prompt, temperature, max_tokens,
            output_config={
                "format": {"type": "json_schema", "schema": to_json_schema(schema)},
            },
        )
        parsed = None
        if text:
            try:
                parsed = json.loads(text)
            except ValueError:
                parsed = None
        return GenResult(
            text=text or None, parsed=parsed,
            provider=self.name, model=model_id,
            usage=self._usage(response),
            elapsed_ms=int((time.monotonic() - started) * 1000),
        )

    def embed(self, model_id, texts, task_type, dims):
        raise ProviderError("Anthropic لا يوفّر نماذج تضمين — اختر موفّر تضمين آخر")

    def count_tokens(self, model_id, text) -> Optional[int]:
        try:
            client = self._get_client()
            result = client.messages.count_tokens(
                model=model_id, messages=[{"role": "user", "content": text}],
            )
            return result.input_tokens
        except Exception:
            return None
