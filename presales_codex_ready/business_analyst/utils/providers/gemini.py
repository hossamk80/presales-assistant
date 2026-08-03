"""
utils/providers/gemini.py — موفّر Google Gemini (google-genai SDK)

التخزين المؤقت للسياق (11-12) ضمني في Gemini 2.5+‏: البادئة المتكررة بين
الاستدعاءات تُخدم من الذاكرة المؤقتة تلقائياً، ويظهر أثرها في
`cached_content_token_count` الذي نسجّله مع كل استدعاء.
"""
import time
from typing import Optional

import streamlit as st

from utils.providers.base import GenResult, Provider, ProviderError, Usage


@st.cache_resource(show_spinner=False)
def _client(api_key: str):
    from google import genai

    return genai.Client(api_key=api_key)


class GeminiProvider(Provider):
    name = "gemini"

    def _get_client(self):
        api_key = st.session_state.get("api_gemini")
        if not api_key:
            raise ProviderError("missing_key")
        try:
            return _client(api_key)
        except ImportError as e:
            raise ProviderError(f"google-genai SDK غير مثبّتة: {e}") from e

    @staticmethod
    def _usage(response) -> Usage:
        meta = getattr(response, "usage_metadata", None)
        if meta is None:
            return Usage()
        return Usage(
            input_tokens=int(getattr(meta, "prompt_token_count", 0) or 0),
            cached_tokens=int(getattr(meta, "cached_content_token_count", 0) or 0),
            output_tokens=int(getattr(meta, "candidates_token_count", 0) or 0),
        )

    def _config(self, temperature, max_tokens, schema=None):
        from google.genai import types

        kwargs = {}
        if schema is not None:
            kwargs["response_mime_type"] = "application/json"
            kwargs["response_schema"] = schema
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens:
            kwargs["max_output_tokens"] = max_tokens
        return types.GenerateContentConfig(**kwargs) if kwargs else None

    def generate(self, model_id, prompt, temperature=None, max_tokens=None) -> GenResult:
        client = self._get_client()
        started = time.monotonic()
        response = client.models.generate_content(
            model=model_id, contents=prompt,
            config=self._config(temperature, max_tokens),
        )
        return GenResult(
            text=response.text, provider=self.name, model=model_id,
            usage=self._usage(response),
            elapsed_ms=int((time.monotonic() - started) * 1000),
        )

    def generate_json(self, model_id, prompt, schema,
                      temperature=None, max_tokens=None) -> GenResult:
        client = self._get_client()
        started = time.monotonic()
        response = client.models.generate_content(
            model=model_id, contents=prompt,
            config=self._config(temperature, max_tokens, schema=schema),
        )
        parsed = getattr(response, "parsed", None)
        return GenResult(
            text=getattr(response, "text", None),
            parsed=parsed if isinstance(parsed, (dict, list)) else None,
            provider=self.name, model=model_id,
            usage=self._usage(response),
            elapsed_ms=int((time.monotonic() - started) * 1000),
        )

    def embed(self, model_id, texts, task_type, dims):
        from google.genai import types

        client = self._get_client()
        response = client.models.embed_content(
            model=model_id, contents=texts,
            config=types.EmbedContentConfig(
                task_type=task_type, output_dimensionality=dims,
            ),
        )
        vectors = [list(e.values) for e in response.embeddings]
        meta = getattr(response, "usage_metadata", None) if response else None
        usage = Usage(input_tokens=int(getattr(meta, "prompt_token_count", 0) or 0)) \
            if meta else Usage()
        return vectors, usage

    def count_tokens(self, model_id, text) -> Optional[int]:
        try:
            client = self._get_client()
            result = client.models.count_tokens(model=model_id, contents=text)
            return result.total_tokens
        except Exception:
            return None
