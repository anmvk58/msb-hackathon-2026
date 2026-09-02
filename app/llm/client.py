import json
from typing import Any, Protocol, TypeVar

import httpx
from pydantic import BaseModel


StructuredT = TypeVar("StructuredT", bound=BaseModel)


class LLMNotConfiguredError(RuntimeError):
    pass


class LLMAuthenticationError(RuntimeError):
    pass


class LLMTimeoutError(RuntimeError):
    pass


class LLMStructuredOutputError(RuntimeError):
    pass


class LLMRequestError(RuntimeError):
    pass


class LLMClient(Protocol):
    def generate(self, *, system_prompt: str, user_prompt: str) -> str: ...

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[StructuredT],
        context: dict[str, Any],
    ) -> StructuredT: ...


class MockLLMClient:
    """Test/development client that validates pre-grounded structured content."""

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        return "MockLLMClient only returns deterministic development content."

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[StructuredT],
        context: dict[str, Any],
    ) -> StructuredT:
        candidate = context.get("grounded_candidate")
        if candidate is not None:
            return response_model.model_validate(candidate)
        plan = context.get("candidate_plan")
        if plan is None:
            raise ValueError("MockLLMClient requires candidate_plan context")
        return response_model.model_validate(
            {
                "summary": plan["summary_hint"],
                "recommended_option_id": plan["default_option_id"],
                "reasoning_summary": plan["reasoning_hint"],
            }
        )


class UnconfiguredLLMClient:
    """Fail-fast implementation used when a real provider has not been selected."""

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        raise LLMNotConfiguredError(
            "No LLM provider configured. Use MockLLMClient for development or set "
            "an explicitly documented provider integration."
        )

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[StructuredT],
        context: dict[str, Any],
    ) -> StructuredT:
        raise LLMNotConfiguredError(
            "No LLM provider configured. Structured generation is unavailable."
        )


class GreenNodeLLMClient:
    """OpenAI-compatible GreenNode MaaS Chat Completions adapter."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str,
        timeout_seconds: int = 60,
        structured_retries: int = 2,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not base_url or not model or not api_key:
            raise LLMNotConfiguredError(
                "GreenNode MaaS requires LLM_BASE_URL, LLM_MODEL, and LLM_API_KEY"
            )
        self.model = model
        self.structured_retries = max(structured_retries, 0)
        self._client = httpx.Client(
            base_url=base_url.rstrip("/") + "/",
            timeout=timeout_seconds,
            transport=transport,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def _chat(self, payload: dict[str, Any]) -> str:
        try:
            response = self._client.post("chat/completions", json=payload)
        except httpx.TimeoutException as error:
            raise LLMTimeoutError("GreenNode MaaS request timed out") from error
        except httpx.HTTPError as error:
            raise LLMRequestError("GreenNode MaaS request failed") from error
        if response.status_code in {401, 403}:
            raise LLMAuthenticationError(
                f"GreenNode MaaS authentication failed (HTTP {response.status_code})"
            )
        if response.is_error:
            raise LLMRequestError(
                f"GreenNode MaaS returned HTTP {response.status_code}"
            )
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise LLMStructuredOutputError(
                "GreenNode MaaS returned an unexpected Chat Completions response"
            ) from error
        if not isinstance(content, str):
            raise LLMStructuredOutputError("GreenNode MaaS response content is not text")
        return content

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        return self._chat(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
        )

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[StructuredT],
        context: dict[str, Any],
    ) -> StructuredT:
        schema = response_model.model_json_schema()
        structured_prompt = (
            user_prompt
            + "\n\nValidated business context (do not modify candidate parameters):\n"
            + json.dumps(context, ensure_ascii=False, default=str)
            + "\n\nReturn one JSON object matching this schema:\n"
            + json.dumps(schema, ensure_ascii=False)
        )
        last_error: Exception | None = None
        for attempt in range(self.structured_retries + 1):
            content = self._chat(
                {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": structured_prompt},
                    ],
                    "temperature": 0,
                }
            )
            try:
                return response_model.model_validate(json.loads(content))
            except (json.JSONDecodeError, ValueError) as error:
                last_error = error
                structured_prompt += (
                    "\nThe prior response failed schema validation. Return corrected JSON only."
                )
                if attempt == self.structured_retries:
                    break
        raise LLMStructuredOutputError(
            "GreenNode MaaS returned malformed structured output after retries"
        ) from last_error
