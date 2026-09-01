from typing import Any, Protocol, TypeVar

from pydantic import BaseModel


StructuredT = TypeVar("StructuredT", bound=BaseModel)


class LLMNotConfiguredError(RuntimeError):
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
        if candidate is None:
            raise ValueError("MockLLMClient requires grounded_candidate context")
        return response_model.model_validate(candidate)


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

