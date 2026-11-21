"""Interchangeable LLM providers. The engine never depends on a specific vendor; providers only return text.

Credentials are read from the backend environment (never from requests, never committed):
  APEX_AI_PROVIDER = openrouter | openai | anthropic
  APEX_AI_MODEL    = model id for that provider (default: a low-cost model, see budget.py)
  OPENROUTER_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY
  APEX_AI_BASE_URL (optional, any OpenAI-compatible endpoint)

Every paid provider returned by `provider_from_env` is wrapped in `budget.BudgetedProvider`: paid calls are off
unless APEX_AI_PAID_ENABLED=1, premium models need explicit approval, there is no model fallback or escalation,
and each experiment has call and spend caps and is written to the cost ledger (see budget.py).
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional, Protocol

import httpx

from .budget import DEFAULT_MODEL, BudgetedProvider, Experiment


class Provider(Protocol):
    name: str

    def complete(self, system: str, user: str, max_tokens: int = 8000) -> str: ...


class ProviderError(RuntimeError):
    pass


class OpenAICompatibleProvider:
    """OpenRouter, OpenAI and any server implementing POST {base}/chat/completions."""

    def __init__(self, base_url: str, api_key: str, model: str, name: str = "openai-compatible", timeout: float = 120.0,
                 client: Optional[httpx.Client] = None):
        self.base_url, self.api_key, self.model, self.name, self.timeout = base_url.rstrip("/"), api_key, model, name, timeout
        self.client = client
        self.last_usage: Optional[Dict[str, Any]] = None
        self.reasoning_tokens: Optional[int] = None  # set by BudgetedProvider; 0 = ask the provider not to reason

    def complete(self, system: str, user: str, max_tokens: int = 8000) -> str:
        body = {"model": self.model, "max_tokens": max_tokens, "temperature": 0.2,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "response_format": {"type": "json_object"}}
        if self.name == "openrouter":
            body["usage"] = {"include": True}  # OpenRouter reports the actual charged cost per request
            if self.reasoning_tokens is not None:  # hidden reasoning is billed as output tokens
                body["reasoning"] = ({"enabled": False} if self.reasoning_tokens <= 0
                                     else {"max_tokens": int(self.reasoning_tokens), "exclude": True})
        headers = {"Authorization": f"Bearer {self.api_key}", "X-Title": "APEX Animation Engine"}
        post = self.client.post if self.client is not None else httpx.post
        r = post(f"{self.base_url}/chat/completions", json=body, timeout=self.timeout, headers=headers)
        if r.status_code >= 400:
            raise ProviderError(f"{self.name} HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        self.last_usage = data.get("usage")
        return data["choices"][0]["message"]["content"]


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: str, timeout: float = 120.0):
        self.api_key, self.model, self.timeout = api_key, model, timeout
        self.last_usage: Optional[Dict[str, Any]] = None

    def complete(self, system: str, user: str, max_tokens: int = 8000) -> str:
        r = httpx.post("https://api.anthropic.com/v1/messages", timeout=self.timeout,
                       headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                       json={"model": self.model, "max_tokens": max_tokens, "system": system,
                             "messages": [{"role": "user", "content": user}]})
        if r.status_code >= 400:
            raise ProviderError(f"anthropic HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        self.last_usage = data.get("usage")
        return "".join(b.get("text", "") for b in data["content"])


def _raw_provider_from_env():
    kind = os.environ.get("APEX_AI_PROVIDER", "").lower()
    model = os.environ.get("APEX_AI_MODEL", "")
    if kind == "openrouter" and os.environ.get("OPENROUTER_API_KEY"):
        return OpenAICompatibleProvider(os.environ.get("APEX_AI_BASE_URL", "https://openrouter.ai/api/v1"), os.environ["OPENROUTER_API_KEY"],
                                        model or DEFAULT_MODEL, "openrouter")
    if kind == "openai" and os.environ.get("OPENAI_API_KEY"):
        if not model:
            raise ProviderError("APEX_AI_MODEL must name a model for the openai provider (no default paid model)")
        return OpenAICompatibleProvider(os.environ.get("APEX_AI_BASE_URL", "https://api.openai.com/v1"), os.environ["OPENAI_API_KEY"], model, "openai")
    if kind == "anthropic" and os.environ.get("ANTHROPIC_API_KEY"):
        if not model:
            raise ProviderError("APEX_AI_MODEL must name a model for the anthropic provider (no default paid model)")
        return AnthropicProvider(os.environ["ANTHROPIC_API_KEY"], model)
    return None


def provider_from_env(reason: str = "") -> Optional[Provider]:
    """The configured provider, wrapped in a budgeted experiment (raises budget.BudgetError if not allowed)."""
    raw = _raw_provider_from_env()
    if raw is None:
        return None
    return BudgetedProvider(raw, Experiment(model=raw.model, reason=reason))
