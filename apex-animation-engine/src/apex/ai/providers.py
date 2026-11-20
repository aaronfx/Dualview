"""Interchangeable LLM providers. The engine never depends on a specific vendor; providers only return text.

Credentials are read from the backend environment (never from requests, never committed):
  APEX_AI_PROVIDER = openrouter | openai | anthropic
  APEX_AI_MODEL    = model id for that provider
  OPENROUTER_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY
  APEX_AI_BASE_URL (optional, any OpenAI-compatible endpoint)
"""
from __future__ import annotations

import os
from typing import Optional, Protocol

import httpx


class Provider(Protocol):
    name: str

    def complete(self, system: str, user: str, max_tokens: int = 8000) -> str: ...


class ProviderError(RuntimeError):
    pass


class OpenAICompatibleProvider:
    """OpenRouter, OpenAI and any server implementing POST {base}/chat/completions."""

    def __init__(self, base_url: str, api_key: str, model: str, name: str = "openai-compatible", timeout: float = 120.0):
        self.base_url, self.api_key, self.model, self.name, self.timeout = base_url.rstrip("/"), api_key, model, name, timeout

    def complete(self, system: str, user: str, max_tokens: int = 8000) -> str:
        body = {"model": self.model, "max_tokens": max_tokens, "temperature": 0.2,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "response_format": {"type": "json_object"}}
        r = httpx.post(f"{self.base_url}/chat/completions", json=body, timeout=self.timeout,
                       headers={"Authorization": f"Bearer {self.api_key}", "X-Title": "APEX Animation Engine"})
        if r.status_code >= 400:
            raise ProviderError(f"{self.name} HTTP {r.status_code}: {r.text[:300]}")
        return r.json()["choices"][0]["message"]["content"]


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: str, timeout: float = 120.0):
        self.api_key, self.model, self.timeout = api_key, model, timeout

    def complete(self, system: str, user: str, max_tokens: int = 8000) -> str:
        r = httpx.post("https://api.anthropic.com/v1/messages", timeout=self.timeout,
                       headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                       json={"model": self.model, "max_tokens": max_tokens, "system": system,
                             "messages": [{"role": "user", "content": user}]})
        if r.status_code >= 400:
            raise ProviderError(f"anthropic HTTP {r.status_code}: {r.text[:300]}")
        return "".join(b.get("text", "") for b in r.json()["content"])


def provider_from_env() -> Optional[Provider]:
    kind = os.environ.get("APEX_AI_PROVIDER", "").lower()
    model = os.environ.get("APEX_AI_MODEL", "")
    if kind == "openrouter" and os.environ.get("OPENROUTER_API_KEY"):
        return OpenAICompatibleProvider(os.environ.get("APEX_AI_BASE_URL", "https://openrouter.ai/api/v1"), os.environ["OPENROUTER_API_KEY"],
                                        model or "anthropic/claude-sonnet-5.5", "openrouter")
    if kind == "openai" and os.environ.get("OPENAI_API_KEY"):
        return OpenAICompatibleProvider(os.environ.get("APEX_AI_BASE_URL", "https://api.openai.com/v1"), os.environ["OPENAI_API_KEY"],
                                        model or "gpt-4.1", "openai")
    if kind == "anthropic" and os.environ.get("ANTHROPIC_API_KEY"):
        return AnthropicProvider(os.environ["ANTHROPIC_API_KEY"], model or "claude-sonnet-5-5")
    return None
