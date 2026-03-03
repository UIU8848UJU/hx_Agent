from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from hx_agent.app_context import get_ctx
from hx_agent.core.logging import get_logger


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    used_fallback: bool
    error_code: str = ''
    latency_ms: int = 0
    retry_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


def _now() -> float:
    return time.time()


class LLMClient:
    _breaker_open_until: float = 0.0
    _consecutive_failures: int = 0

    def __init__(self) -> None:
        ctx = get_ctx()
        self.cfg = ctx.cfg.llm
        self.provider = self.cfg.provider
        self.model = self.cfg.model
        self.api_key = os.getenv(self.cfg.api_key_env, '')
        self.log = get_logger(__name__)

    def enabled(self) -> bool:
        return bool(self.cfg.enabled) and self.provider != 'none' and bool(self.api_key.strip())

    def answer(self, query: str, context: str, request_id: str = '-', session_id: int | None = None) -> LLMResponse:
        t0 = _now()
        if not self.enabled():
            self.log.info(
                '[llm] fallback disabled or missing key request_id=%s session_id=%s provider=%s model=%s',
                request_id,
                session_id,
                self.provider,
                self.model,
            )
            return LLMResponse(
                text='',
                provider=self.provider,
                model=self.model,
                used_fallback=True,
                error_code='llm_not_enabled',
            )

        if _now() < LLMClient._breaker_open_until:
            return LLMResponse(
                text='',
                provider=self.provider,
                model=self.model,
                used_fallback=True,
                error_code='circuit_open',
                latency_ms=int((_now() - t0) * 1000),
            )

        try:
            rsp = self._call_with_retries(query=query, context=context, request_id=request_id, session_id=session_id)
            LLMClient._consecutive_failures = 0
            return rsp
        except Exception as e:
            LLMClient._consecutive_failures += 1
            if LLMClient._consecutive_failures >= int(self.cfg.circuit_breaker_fail_threshold):
                LLMClient._breaker_open_until = _now() + int(self.cfg.circuit_breaker_reset_sec)
            self.log.error(
                '[llm] request failed request_id=%s session_id=%s provider=%s model=%s err=%s',
                request_id,
                session_id,
                self.provider,
                self.model,
                repr(e),
            )
            return LLMResponse(
                text='',
                provider=self.provider,
                model=self.model,
                used_fallback=True,
                error_code='request_failed',
                latency_ms=int((_now() - t0) * 1000),
            )

    def _call_with_retries(
        self, query: str, context: str, request_id: str, session_id: int | None
    ) -> LLMResponse:
        retries = int(max(0, self.cfg.max_retries))
        for attempt in range(retries + 1):
            t0 = _now()
            try:
                out = self._call_once(query=query, context=context)
                out.retry_count = attempt
                out.latency_ms = int((_now() - t0) * 1000)
                self.log.info(
                    '[llm] ok request_id=%s session_id=%s provider=%s model=%s latency_ms=%s retry_count=%s total_tokens=%s fallback_used=%s',
                    request_id,
                    session_id,
                    out.provider,
                    out.model,
                    out.latency_ms,
                    out.retry_count,
                    out.total_tokens,
                    out.used_fallback,
                )
                return out
            except _RetryableLLMError as e:
                if attempt >= retries:
                    raise
                delay = self._backoff_delay_ms(attempt)
                self.log.warning(
                    '[llm] retry request_id=%s session_id=%s provider=%s model=%s attempt=%s delay_ms=%s code=%s',
                    request_id,
                    session_id,
                    self.provider,
                    self.model,
                    attempt + 1,
                    delay,
                    e.code,
                )
                time.sleep(delay / 1000.0)
            except Exception:
                raise
        raise RuntimeError('unreachable')

    def _backoff_delay_ms(self, attempt: int) -> int:
        base = int(max(50, self.cfg.retry_backoff_ms))
        jitter = random.randint(0, base // 3)
        return base * (2**attempt) + jitter

    def _call_once(self, query: str, context: str) -> LLMResponse:
        payload = self._build_payload(query=query, context=context)
        body = json.dumps(payload).encode('utf-8')
        url = self.cfg.base_url.rstrip('/') + '/chat/completions'
        req = request.Request(
            url=url,
            method='POST',
            data=body,
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            },
        )
        try:
            with request.urlopen(req, timeout=float(self.cfg.timeout_sec)) as resp:
                data = json.loads(resp.read().decode('utf-8', errors='ignore'))
        except error.HTTPError as e:
            code = getattr(e, 'code', 0)
            if int(code) == 429 or int(code) >= 500:
                raise _RetryableLLMError(f'http_{code}') from e
            raise RuntimeError(f'http_{code}') from e
        except error.URLError as e:
            raise _RetryableLLMError('network_error') from e

        text = self._extract_text(data)
        usage = data.get('usage') or {}
        return LLMResponse(
            text=text,
            provider=self.provider,
            model=self.model,
            used_fallback=not bool(text.strip()),
            input_tokens=int(usage.get('prompt_tokens') or 0),
            output_tokens=int(usage.get('completion_tokens') or 0),
            total_tokens=int(usage.get('total_tokens') or 0),
        )

    def _build_payload(self, query: str, context: str) -> dict[str, Any]:
        capped_context = context[:12000]
        capped_query = query[:2000]
        system_prompt = (
            'You are a careful study assistant. Answer only from provided context. '
            'If context is insufficient, say what is missing. Keep output concise.'
        )
        user_prompt = (
            'Question:\n'
            f'{capped_query}\n\n'
            'Context (trusted excerpts):\n'
            '---BEGIN_CONTEXT---\n'
            f'{capped_context}\n'
            '---END_CONTEXT---\n'
        )
        return {
            'model': self.model,
            'temperature': float(self.cfg.temperature),
            'max_tokens': int(self.cfg.max_tokens),
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
        }

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        try:
            return str(data['choices'][0]['message']['content'] or '').strip()
        except Exception:
            return ''


class _RetryableLLMError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code
        return LLMResponse(
            text='',
            provider=self.provider,
            model=self.model,
            used_fallback=True,
        )
