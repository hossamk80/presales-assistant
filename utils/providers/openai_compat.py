"""
utils/providers/openai_compat.py — موفّر OpenAI وكل نقطة متوافقة معه (11-2)

موفّر واحد يخدم ثلاثة أسماء في السجل:
- `openai`: النقطة الرسمية.
- `compat`: أي نقطة متوافقة (OpenRouter · Azure OpenAI · Groq · Mistral ·
  DeepSeek · Together) — الفرق هو الرابط والمفتاح فقط.
- `local`: ‏Ollama / vLLM محلياً — يعمل **بلا مفتاح** وبلا كلفة.

نستخدم HTTP مباشرة (حزمة requests المتوفرة أصلاً) بدل إضافة SDK لكل مزوّد.
"""
import json
import time
import requests
import streamlit as st

from utils.providers import catalog
from utils.providers.base import (
    GenResult, Provider, ProviderError, Usage, schema_instruction, to_json_schema,
)

TIMEOUT = 300


class OpenAICompatProvider(Provider):
    streams = True
    def __init__(self, name: str):
        self.name = name

    def _base_url(self) -> str:
        info = catalog.provider_info(self.name)
        configured = str(st.session_state.get(f"base_url_{self.name}", "")).strip()
        url = configured or info.get("base_url") or ""
        if not url:
            raise ProviderError("base_url غير محدد")
        return url.rstrip("/")

    def _headers(self) -> dict:
        info = catalog.provider_info(self.name)
        headers = {"Content-Type": "application/json"}
        key = st.session_state.get(info.get("key_state", ""), "")
        if key:
            headers["Authorization"] = f"Bearer {key}"
        elif info.get("needs_key", True):
            raise ProviderError("missing_key")
        return headers

    def _post(self, path: str, payload: dict) -> dict:
        try:
            response = requests.post(
                f"{self._base_url()}{path}", headers=self._headers(),
                json=payload, timeout=TIMEOUT,
            )
        except requests.RequestException as e:
            raise ProviderError(f"connection: {e}") from e
        if response.status_code >= 400:
            raise ProviderError(f"HTTP {response.status_code}: {response.text[:400]}")
        try:
            return response.json()
        except ValueError as e:
            raise ProviderError(f"ردّ غير صالح: {e}") from e

    @staticmethod
    def _usage(data: dict) -> Usage:
        usage = data.get("usage") or {}
        details = usage.get("prompt_tokens_details") or {}
        return Usage(
            input_tokens=int(usage.get("prompt_tokens") or 0),
            cached_tokens=int(details.get("cached_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
        )

    def _chat(self, model_id, prompt, temperature, max_tokens, response_format=None):
        payload: dict = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if response_format is not None:
            payload["response_format"] = response_format

        started = time.monotonic()
        data = self._post("/chat/completions", payload)
        choices = data.get("choices") or []
        text = (choices[0].get("message") or {}).get("content") if choices else None
        return data, text, int((time.monotonic() - started) * 1000)

    def generate(self, model_id, prompt, temperature=None, max_tokens=None) -> GenResult:
        data, text, elapsed = self._chat(model_id, prompt, temperature, max_tokens)
        return GenResult(
            text=text or None, provider=self.name, model=model_id,
            usage=self._usage(data), elapsed_ms=elapsed,
        )

    def generate_stream(self, model_id, prompt, temperature=None, max_tokens=None):
        """
        بثّ عبر Server-Sent Events — الصيغة القياسية لنقاط OpenAI والمتوافقة معها.

        `stream_options.include_usage` تطلب عدّادات الاستهلاك في آخر حدث: بدونها
        يصل الدفق بلا أرقام فتُسجَّل المحاسبة أصفاراً، ويبدو استدعاءٌ حقيقي
        مجانياً في لوحة الاستهلاك. ونقطة لا تدعم الخيار تتجاهله بلا ضرر.
        """
        payload: dict = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens:
            payload["max_tokens"] = max_tokens

        started = time.monotonic()
        try:
            response = requests.post(
                f"{self._base_url()}/chat/completions", headers=self._headers(),
                json=payload, timeout=TIMEOUT, stream=True,
            )
        except requests.RequestException as e:
            raise ProviderError(f"connection: {e}") from e
        if response.status_code >= 400:
            raise ProviderError(f"HTTP {response.status_code}: {response.text[:400]}")

        usage = Usage()
        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            body = line[5:].strip()
            if body == "[DONE]":
                break
            try:
                event = json.loads(body)
            except ValueError:
                # حدث مشوّه وسط دفق سليم: يُتخطّى ولا يُسقط ما وصل
                continue
            if event.get("usage"):
                usage = self._usage(event)
            for choice in event.get("choices") or []:
                piece = (choice.get("delta") or {}).get("content")
                if piece:
                    yield piece

        return GenResult(
            provider=self.name, model=model_id, usage=usage,
            elapsed_ms=int((time.monotonic() - started) * 1000),
        )

    def generate_json(self, model_id, prompt, schema,
                      temperature=None, max_tokens=None) -> GenResult:
        info = catalog.model_info(self.name, model_id) or {}
        if info.get("json"):
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": "extraction",
                    "schema": to_json_schema(schema),
                    "strict": True,
                },
            }
        else:
            # نموذج بلا دعم مخططات: نصف الشكل في التعليمات ونحلّل الرد
            prompt = prompt + schema_instruction(schema)
            response_format = None

        data, text, elapsed = self._chat(
            model_id, prompt, temperature, max_tokens, response_format,
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
            usage=self._usage(data), elapsed_ms=elapsed,
        )

    def embed(self, model_id, texts, task_type, dims):
        payload = {"model": model_id, "input": texts, "dimensions": dims}
        data = self._post("/embeddings", payload)
        rows = sorted(data.get("data") or [], key=lambda r: r.get("index", 0))
        vectors = [row.get("embedding") or [] for row in rows]
        usage = data.get("usage") or {}
        return vectors, Usage(input_tokens=int(usage.get("prompt_tokens") or 0))
