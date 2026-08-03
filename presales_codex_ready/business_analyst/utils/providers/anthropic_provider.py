"""
utils/providers/anthropic_provider.py — موفّر Anthropic Claude (SDK الرسمية)

- المخرجات المُهيكلة عبر `output_config.format` بمخطط JSON قياسي.
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

    def _create(self, model_id, prompt, temperature, max_tokens, output_config=None):
        client = self._get_client()
        kwargs = {
            "model": model_id,
            "max_tokens": max_tokens or DEFAULT_MAX_TOKENS,
            "messages": [{"role": "user", "content": prompt}],
        }
        if output_config is not None:
            kwargs["output_config"] = output_config
        if len(prompt) >= CACHE_MIN_CHARS:
            kwargs["cache_control"] = {"type": "ephemeral"}
        response = client.messages.create(**kwargs)
        if getattr(response, "stop_reason", None) == "refusal":
            raise ProviderError("رفض النموذج الطلب (safety refusal)")
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
