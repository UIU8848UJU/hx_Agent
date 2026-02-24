from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    used_fallback: bool


class LLMClient:
    """
    v0.2 skeleton client.
    If no API key/provider is configured, caller should use rule-based fallback.
    """

    def __init__(self) -> None:
        self.provider = os.getenv('HX_AGENT_LLM_PROVIDER', 'none')
        self.model = os.getenv('HX_AGENT_LLM_MODEL', 'none')
        self.api_key = os.getenv('HX_AGENT_LLM_API_KEY', '')

    def enabled(self) -> bool:
        return self.provider != 'none' and bool(self.api_key.strip())

    def answer(self, query: str, context: str) -> LLMResponse:
        if not self.enabled():
            return LLMResponse(
                text='',
                provider='none',
                model='none',
                used_fallback=True,
            )

        # Real provider adapters can be added here in v0.2+.
        # Keep a stable return shape for service layer.
        _ = (query, context)
        return LLMResponse(
            text='',
            provider=self.provider,
            model=self.model,
            used_fallback=True,
        )
