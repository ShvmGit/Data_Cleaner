"""Groq LLM client with model fallback chain and retry logic."""

from __future__ import annotations

import json
from typing import Any

from groq import Groq, AsyncGroq
from groq import APIError, RateLimitError, APITimeoutError

from core.config import get_settings
from core.logging import get_logger
from core.circuit_breaker import circuit_breaker

logger = get_logger(__name__)

# Model fallback chain (fastest to slowest, largest to smallest)
MODEL_CHAIN = [
    "llama-3.3-70b-versatile",
    "mixtral-8x7b-32768",
    "llama-3.1-8b-instant",
]


class GroqClient:
    """Async Groq client with fallback chain, retry, and circuit breaker."""

    def __init__(self):
        settings = get_settings()
        self._client = AsyncGroq(
            api_key=settings.groq_api_key,
            timeout=settings.groq_timeout,
        )
        self._primary_model = settings.groq_model
        self._fallback_model = settings.groq_fallback_model

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """
        Send a chat completion request with automatic model fallback.

        Returns:
            Dict with 'content', 'tool_calls', 'model', 'usage'
        """
        if circuit_breaker.is_open:
            logger.warning("circuit_breaker_open", action="skip_llm")
            raise ConnectionError("Circuit breaker is open — LLM unavailable")

        models_to_try = [self._primary_model, self._fallback_model]
        last_error = None

        for model in models_to_try:
            try:
                return await self._try_model(model, messages, tools, tool_choice, temperature, max_tokens)
            except (APIError, RateLimitError, APITimeoutError) as e:
                last_error = e
                logger.warning("model_failed", model=model, error=str(e))
                continue
            except Exception as e:
                last_error = e
                logger.error("unexpected_llm_error", model=model, error=str(e))
                circuit_breaker.record_failure()
                break

        circuit_breaker.record_failure()
        raise ConnectionError(f"All LLM models failed: {last_error}")

    async def _try_model(
        self,
        model: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None,
        tool_choice: str,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Attempt a single model call."""
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        response = await self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        circuit_breaker.record_success()

        result: dict[str, Any] = {
            "content": choice.message.content or "",
            "tool_calls": [],
            "model": model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
        }

        # Parse tool calls
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                result["tool_calls"].append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments) if tc.function.arguments else {},
                })

        logger.info(
            "llm_response",
            model=model,
            tokens=result["usage"]["total_tokens"],
            tool_calls=len(result["tool_calls"]),
            has_content=bool(result["content"]),
        )

        return result

    async def close(self):
        """Close the client."""
        await self._client.close()


# Global client instance
groq_client = GroqClient()
