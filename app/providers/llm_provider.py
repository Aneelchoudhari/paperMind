"""Abstract LLM provider interface + OpenAI and Gemini implementations."""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class LLMProvider(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    def complete(self, system: str, user: str, json_mode: bool = True) -> str:
        """Send a completion request and return the text response."""
        ...

    def complete_json(self, system: str, user: str) -> dict:
        """Send a completion request and parse JSON from the response."""
        raw = self.complete(system, user, json_mode=True)
        # Strip markdown code fences if present
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        return json.loads(raw)


# ── OpenAI Implementation ─────────────────────────────────────────────────────

class OpenAIProvider(LLMProvider):
    def __init__(self):
        from openai import OpenAI
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.llm_model or "gpt-4o-mini"

    def complete(self, system: str, user: str, json_mode: bool = True) -> str:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""


# ── Gemini Implementation ─────────────────────────────────────────────────────

class GeminiProvider(LLMProvider):
    def __init__(self):
        import google.generativeai as genai
        genai.configure(api_key=settings.gemini_api_key)
        self._model = genai.GenerativeModel("gemini-1.5-flash")

    def complete(self, system: str, user: str, json_mode: bool = True) -> str:
        prompt = f"{system}\n\n{user}"
        response = self._model.generate_content(
            prompt,
            generation_config={"temperature": 0},
        )
        return response.text


# ── NVIDIA NIM Implementation ──────────────────────────────────────────────────

class NvidiaProvider(LLMProvider):
    def __init__(self):
        from openai import OpenAI
        self._client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=settings.nvidia_api_key,
        )
        self._model = settings.nvidia_model or "meta/llama-3.1-405b-instruct"

    def complete(self, system: str, user: str, json_mode: bool = True) -> str:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
        }
        # Note: NVIDIA NIM hosts support JSON mode depending on the specific model,
        # but usually passing system prompts specifying JSON is safer if the model doesn't support json response_format.
        # However, for llama-3.1-405b and modern models, response_format is often supported.
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""


# ── Groq Implementation ────────────────────────────────────────────────────────

class GroqProvider(LLMProvider):
    def __init__(self):
        from openai import OpenAI
        self._client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=settings.groq_api_key,
        )
        self._model = settings.groq_model or "llama-3.3-70b-specdec"

    def complete(self, system: str, user: str, json_mode: bool = True) -> str:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""


# ── Factory ──────────────────────────────────────────────────────────────────

_provider: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    """Return the configured LLM provider (cached singleton)."""
    global _provider
    if _provider is None:
        if settings.llm_provider == "gemini":
            if not settings.gemini_api_key:
                raise ValueError(
                    "GEMINI_API_KEY is not set. "
                    "Set it in .env or switch LLM_PROVIDER to openai or nvidia."
                )
            _provider = GeminiProvider()
            logger.info("LLM provider: Gemini 1.5 Flash")
        elif settings.llm_provider == "nvidia":
            if not settings.nvidia_api_key:
                raise ValueError(
                    "NVIDIA_API_KEY is not set. "
                    "Set it in .env or switch LLM_PROVIDER to openai or gemini."
                )
            _provider = NvidiaProvider()
            logger.info("LLM provider: NVIDIA NIM (%s)", settings.nvidia_model)
        elif settings.llm_provider == "groq":
            if not settings.groq_api_key:
                raise ValueError(
                    "GROQ_API_KEY is not set. "
                    "Set it in .env or switch LLM_PROVIDER to openai, gemini, or nvidia."
                )
            _provider = GroqProvider()
            logger.info("LLM provider: Groq (%s)", settings.groq_model)
        else:
            if not settings.openai_api_key:
                raise ValueError(
                    "OPENAI_API_KEY is not set. "
                    "Set it in .env or switch LLM_PROVIDER to gemini or nvidia."
                )
            _provider = OpenAIProvider()
            logger.info("LLM provider: OpenAI (%s)", settings.llm_model)
    return _provider

